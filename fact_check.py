#!/usr/bin/env python3
"""FB 影片事實查核 Pipeline — 五階段架構

基於 ClaimDecomp (UT Austin) + Deep Research 階層式架構：
  1. 轉錄 (Whisper)
  2. 主張提取與拆解 (Claim Decomposition)
  3. 多輪迭代搜尋 (Iterative Deep Search)
  4. 證據摘要與交叉驗證
  5. 判定與報告生成
"""

import sys, os, json, tempfile, subprocess, re
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ── Stage 0: 音訊下載 ──

def download_audio(url: str) -> str:
    out = os.path.join(tempfile.gettempdir(), "fb_audio")
    subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "mp3", "-o", out + ".%(ext)s",
         "--force-overwrites", url],
        check=True, capture_output=True,
    )
    for ext in ("mp3", "m4a", "wav", "webm", "opus"):
        p = f"{out}.{ext}"
        if os.path.exists(p):
            return p
    raise FileNotFoundError("下載失敗，找不到音訊檔")


# ── Stage 1: 語音轉錄 ──

def transcribe(path: str, model_name: str = "small") -> str:
    import whisper
    model = whisper.load_model(model_name)
    return model.transcribe(path)["text"]


# ── Data Models ──

@dataclass
class Claim:
    text: str
    sub_questions: list[str] = field(default_factory=list)

@dataclass
class Evidence:
    query: str
    source_url: str
    snippet: str
    language: str
    stance: str = ""  # support / refute / neutral / insufficient

@dataclass
class ClaimVerdict:
    claim: str
    verdict: str  # true / mostly_true / half_true / mostly_false / false / unverifiable
    confidence: str  # high / medium / low
    evidence_summary: str
    sources: list[str] = field(default_factory=list)
    sub_verdicts: list[dict] = field(default_factory=list)

@dataclass
class FactCheckReport:
    url: str
    transcript: str
    claims: list[ClaimVerdict]
    overall_verdict: str
    methodology_note: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Stage 2: 主張提取與拆解 ──

CLAIM_EXTRACTION_PROMPT = """你是一個事實查核專家。從以下影片逐字稿中，提取所有可查核的事實性主張。

規則：
- 只提取可以用證據驗證的事實性聲明（數據、因果關係、歷史事件、科學宣稱）
- 忽略純粹的意見、情緒表達、修辭問句
- 每個主張獨立成一條，保留原始語境
- 用 JSON 陣列格式輸出：["主張1", "主張2", ...]

逐字稿：
{transcript}"""

CLAIM_DECOMPOSE_PROMPT = """將以下主張拆解為 3-5 個可獨立搜尋驗證的子問題（yes/no 或 wh-question）。
子問題應涵蓋：事實本身、數據來源、因果邏輯、可能的反面證據。

主張：{claim}

用 JSON 陣列格式輸出：["子問題1", "子問題2", ...]"""


def extract_claims(transcript: str) -> list[str]:
    """從逐字稿提取可查核主張（需 LLM — 此處輸出 prompt 供 agent 使用）。"""
    return _llm_json_list(CLAIM_EXTRACTION_PROMPT.format(transcript=transcript))


def decompose_claim(claim: str) -> list[str]:
    """將主張拆解為子問題。"""
    return _llm_json_list(CLAIM_DECOMPOSE_PROMPT.format(claim=claim))


# ── Stage 3: 多輪迭代搜尋 ──

SEARCH_LANGUAGES = {
    "zh": "中文",
    "en": "English",
}

ACADEMIC_SITES = [
    "site:pubmed.ncbi.nlm.nih.gov",
    "site:scholar.google.com",
    "site:pmc.ncbi.nlm.nih.gov",
    "site:researchgate.net",
]

def generate_search_queries(claim: str, sub_questions: list[str],
                            extra_langs: list[str] | None = None) -> list[dict]:
    """為每個子問題生成多語言搜尋查詢。"""
    langs = dict(SEARCH_LANGUAGES)
    if extra_langs:
        for lang in extra_langs:
            langs[lang] = lang

    queries = []
    for sq in sub_questions:
        for lang_code, lang_name in langs.items():
            queries.append({
                "question": sq,
                "language": lang_code,
                "query": sq if lang_code == "zh" else f"[translate to {lang_name}] {sq}",
                "type": "general",
            })
    # 加入學術來源搜尋
    queries.append({
        "question": claim,
        "language": "en",
        "query": f"{claim} {ACADEMIC_SITES[0]}",
        "type": "academic",
    })
    return queries


REFLECTION_PROMPT = """你是事實查核研究員。根據目前收集到的證據，評估：

主張：{claim}
子問題：{sub_questions}
已收集證據摘要：{evidence_summary}

請回答：
1. 哪些子問題已有充分證據？
2. 哪些子問題證據不足，需要追加搜尋？
3. 是否有矛盾的證據需要進一步釐清？
4. 建議的追加搜尋查詢（JSON 陣列）

用 JSON 格式輸出：
{{"answered": ["已回答的子問題"], "gaps": ["缺口"], "conflicts": ["矛盾"], "new_queries": ["追加查詢"]}}"""


def reflect_on_evidence(claim: str, sub_questions: list[str],
                        evidence: list[Evidence]) -> dict:
    """反思已收集證據的缺口（需 LLM）。"""
    summary = "\n".join(f"- [{e.language}] {e.snippet[:200]}" for e in evidence)
    prompt = REFLECTION_PROMPT.format(
        claim=claim,
        sub_questions=json.dumps(sub_questions, ensure_ascii=False),
        evidence_summary=summary,
    )
    return _llm_json_dict(prompt)


# ── Stage 4: 證據摘要與交叉驗證 ──

SUMMARIZE_PROMPT = """根據以下證據，針對主張進行摘要。

主張：{claim}
證據：
{evidence_text}

規則：
- 區分「有同行評審的研究」和「網路文章」
- 標註每條證據的立場（支持/反駁/中立）
- 如果關鍵數據只有單一來源，標註「僅單一來源，可信度待確認」

輸出 JSON：
{{"summary": "摘要文字", "stance_counts": {{"support": N, "refute": N, "neutral": N}}, "single_source_warnings": ["..."]}}"""


VERDICT_PROMPT = """你是資深事實查核員。根據所有證據，對以下主張做出判定。

主張：{claim}
證據摘要：{summary}
子問題判定：{sub_verdicts}

判定等級：true / mostly_true / half_true / mostly_false / false / unverifiable
信心等級：high（≥3個獨立來源交叉驗證）/ medium（2個來源）/ low（單一來源或證據不足）

輸出 JSON：
{{"verdict": "判定", "confidence": "信心", "reasoning": "推理過程", "sources": ["關鍵來源URL"]}}"""


# ── Stage 5: 報告生成 ──

def generate_report(url: str, transcript: str,
                    verdicts: list[ClaimVerdict]) -> FactCheckReport:
    overall_scores = {"true": 0, "mostly_true": 0, "half_true": 0,
                      "mostly_false": 0, "false": 0, "unverifiable": 0}
    for v in verdicts:
        overall_scores[v.verdict] = overall_scores.get(v.verdict, 0) + 1

    total = len(verdicts) or 1
    false_ratio = (overall_scores["false"] + overall_scores["mostly_false"]) / total

    if false_ratio > 0.5:
        overall = "mostly_false"
    elif false_ratio > 0.25:
        overall = "mixed"
    elif overall_scores["true"] + overall_scores["mostly_true"] > total * 0.5:
        overall = "mostly_true"
    else:
        overall = "mixed"

    return FactCheckReport(
        url=url,
        transcript=transcript[:500] + "..." if len(transcript) > 500 else transcript,
        claims=verdicts,
        overall_verdict=overall,
        methodology_note=(
            "採用 ClaimDecomp 五階段 pipeline：主張拆解 → 多語言迭代搜尋(≥2輪) → "
            "全文讀取 → 交叉驗證(≥2獨立來源) → 判定。"
            "學術來源優先：PubMed > Scholar > 權威媒體 > 一般網頁。"
        ),
    )


# ── LLM Helpers (agent 模式下由 agent 的 LLM 執行) ──

def _llm_json_list(prompt: str) -> list[str]:
    """Placeholder — 在 agent 模式下，這些 prompt 會由 agent 的 LLM 處理。
    獨立執行時，印出 prompt 讓使用者手動處理。"""
    print(f"\n{'='*60}")
    print("📋 LLM PROMPT (需要 AI agent 處理):")
    print(f"{'='*60}")
    print(prompt)
    print(f"{'='*60}\n")
    # 嘗試從 stdin 讀取回應
    if sys.stdin.isatty():
        resp = input("貼上 JSON 陣列回應 (或按 Enter 跳過): ").strip()
        if resp:
            return json.loads(resp)
    return []


def _llm_json_dict(prompt: str) -> dict:
    print(f"\n{'='*60}")
    print("📋 LLM PROMPT (需要 AI agent 處理):")
    print(f"{'='*60}")
    print(prompt)
    print(f"{'='*60}\n")
    if sys.stdin.isatty():
        resp = input("貼上 JSON 物件回應 (或按 Enter 跳過): ").strip()
        if resp:
            return json.loads(resp)
    return {}


# ── CLI Entry Point ──

def main():
    if len(sys.argv) < 2:
        print("用法：python3 fact_check.py <影片網址> [whisper模型]")
        print("      python3 fact_check.py --transcript <逐字稿文字>")
        print("\n模型選項：tiny, base, small (預設), medium, large")
        print("\n五階段 Pipeline：")
        print("  1. 轉錄 → 2. 主張拆解 → 3. 迭代搜尋 → 4. 交叉驗證 → 5. 判定報告")
        sys.exit(1)

    # 支援直接輸入逐字稿
    if sys.argv[1] == "--transcript":
        transcript = " ".join(sys.argv[2:])
    else:
        url = sys.argv[1]
        model_name = sys.argv[2] if len(sys.argv) > 2 else "small"
        print("📥 Stage 0: 下載影片音訊...")
        audio = download_audio(url)
        print(f"  ✓ {audio}")
        print(f"🎙️ Stage 1: 語音轉錄 (Whisper {model_name})...")
        transcript = transcribe(audio, model_name)
        print(f"  ✓ 轉錄完成 ({len(transcript)} 字)")

    print(f"\n📝 逐字稿：\n{transcript[:300]}...\n")

    # Stage 2: 主張提取與拆解
    print("🔍 Stage 2: 主張提取與拆解...")
    claims_text = extract_claims(transcript)
    claims = []
    for ct in claims_text:
        subs = decompose_claim(ct)
        claims.append(Claim(text=ct, sub_questions=subs))
        print(f"  主張: {ct[:80]}...")
        for sq in subs:
            print(f"    └─ {sq}")

    # Stage 3-5: 需要搜尋能力，輸出查詢計畫供 agent 執行
    print("\n🌐 Stage 3: 搜尋查詢計畫")
    all_queries = []
    for c in claims:
        queries = generate_search_queries(c.text, c.sub_questions)
        all_queries.extend(queries)
        print(f"  主張: {c.text[:60]}... → {len(queries)} 個查詢")

    # 輸出結構化結果
    output = {
        "transcript": transcript,
        "claims": [asdict(c) for c in claims],
        "search_plan": all_queries,
        "pipeline_status": "awaiting_search",
        "instructions": (
            "此 pipeline 已完成 Stage 1-2（轉錄+主張拆解）。"
            "Stage 3-5 需要 web_search/web_fetch 能力。"
            "請將此輸出交給具有搜尋能力的 AI agent 繼續執行。"
        ),
    }

    out_path = os.path.join(tempfile.gettempdir(), "fact_check_pipeline.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📁 Pipeline 輸出: {out_path}")


if __name__ == "__main__":
    main()
