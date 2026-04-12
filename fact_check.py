#!/usr/bin/env python3
"""Video Fact-Check Pipeline — 5-Stage Architecture

Based on ClaimDecomp (UT Austin) + Gemini Deep Research iterative search concept:
  1. Transcription (Whisper)
  2. Claim Extraction & Decomposition
  3. Multi-Round Iterative Search
  4. Evidence Summarization & Cross-Validation
  5. Verdict & Report Generation
"""

import sys, os, json, tempfile, subprocess, re
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ── Stage 0: Audio Download ──

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
    raise FileNotFoundError("Download failed, audio file not found")


# ── Stage 1: Speech-to-Text (Groq Whisper API — free, fast, no local GPU needed) ──

def transcribe(path: str, model_name: str = "whisper-large-v3-turbo") -> str:
    """Transcribe audio using Groq's free Whisper API.
    Requires GROQ_API_KEY env var. Get one free at https://console.groq.com/keys
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set. Get a free key at https://console.groq.com/keys")

    # Groq accepts up to 25MB; preprocess large files
    file_size = os.path.getsize(path)
    if file_size > 24 * 1024 * 1024:
        compressed = path + ".flac"
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-ar", "16000", "-ac", "1", "-c:a", "flac", compressed],
            check=True, capture_output=True,
        )
        path = compressed

    import urllib.request
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    with open(path, "rb") as f:
        file_data = f.read()
    filename = os.path.basename(path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_data + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"{model_name}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="response_format"\r\n\r\n'
        f"text\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8").strip()


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


# ── Stage 2: Claim Extraction & Decomposition ──

CLAIM_EXTRACTION_PROMPT = """You are a fact-checking expert. Extract all verifiable factual claims from the following video transcript.

Rules:
- Only extract evidence-verifiable factual statements (data, causal relationships, historical events, scientific claims)
- Ignore pure opinions, emotional expressions, rhetorical questions
- Each claim should be independent, preserving original context
- Output as JSON array: ["claim1", "claim2", ...]

Transcript:
{transcript}"""

CLAIM_DECOMPOSE_PROMPT = """Decompose the following claim into 3-5 independently searchable sub-questions (yes/no or wh-questions).
Sub-questions should cover: the fact itself, data sources, causal logic, potential counter-evidence.

Claim: {claim}

Output as JSON array: ["sub-question1", "sub-question2", ...]"""


def extract_claims(transcript: str) -> list[str]:
    """Extract verifiable claims from transcript (requires LLM)."""
    return _llm_json_list(CLAIM_EXTRACTION_PROMPT.format(transcript=transcript))


def decompose_claim(claim: str) -> list[str]:
    """Decompose a claim into sub-questions."""
    return _llm_json_list(CLAIM_DECOMPOSE_PROMPT.format(claim=claim))


# ── Stage 3: Multi-Round Iterative Search ──

SEARCH_LANGUAGES = {
    "zh": "Chinese",
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
    """Generate multilingual search queries for each sub-question."""
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
                "query": sq if lang_code == "en" else f"[translate to {lang_name}] {sq}",
                "type": "general",
            })
    # Add academic source search
    queries.append({
        "question": claim,
        "language": "en",
        "query": f"{claim} {ACADEMIC_SITES[0]}",
        "type": "academic",
    })
    return queries


REFLECTION_PROMPT = """You are a fact-check researcher. Based on the evidence collected so far, evaluate:

Claim: {claim}
Sub-questions: {sub_questions}
Evidence summary: {evidence_summary}

Answer:
1. Which sub-questions have sufficient evidence?
2. Which sub-questions lack evidence and need additional searches?
3. Is there contradictory evidence that needs further clarification?
4. Suggested follow-up search queries (JSON array)

Output as JSON:
{{"answered": ["answered sub-questions"], "gaps": ["gaps"], "conflicts": ["conflicts"], "new_queries": ["follow-up queries"]}}"""


def reflect_on_evidence(claim: str, sub_questions: list[str],
                        evidence: list[Evidence]) -> dict:
    """Reflect on evidence gaps (requires LLM)."""
    summary = "\n".join(f"- [{e.language}] {e.snippet[:200]}" for e in evidence)
    prompt = REFLECTION_PROMPT.format(
        claim=claim,
        sub_questions=json.dumps(sub_questions, ensure_ascii=False),
        evidence_summary=summary,
    )
    return _llm_json_dict(prompt)


# ── Stage 4: Evidence Summarization & Cross-Validation ──

SUMMARIZE_PROMPT = """Based on the following evidence, summarize with respect to the claim.

Claim: {claim}
Evidence:
{evidence_text}

Rules:
- Distinguish "peer-reviewed research" from "web articles"
- Label each piece of evidence's stance (support/refute/neutral)
- If key data has only a single source, label "single source only, credibility pending confirmation"

Output JSON:
{{"summary": "summary text", "stance_counts": {{"support": N, "refute": N, "neutral": N}}, "single_source_warnings": ["..."]}}"""


VERDICT_PROMPT = """You are a senior fact-checker. Based on all evidence, make a verdict on the following claim.

Claim: {claim}
Evidence summary: {summary}
Sub-question verdicts: {sub_verdicts}

Verdict levels: true / mostly_true / half_true / mostly_false / false / unverifiable
Confidence levels: high (≥3 independent sources cross-validated) / medium (2 sources) / low (single source or insufficient evidence)

Output JSON:
{{"verdict": "verdict", "confidence": "confidence", "reasoning": "reasoning process", "sources": ["key source URLs"]}}"""


# ── Stage 5: Report Generation ──

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
            "ClaimDecomp 5-stage pipeline: claim decomposition → multilingual iterative search (≥2 rounds) → "
            "full-text reading (with fallback chain) → cross-validation (≥2 independent sources) → verdict. "
            "Academic sources prioritized: PubMed > Scholar > authoritative media > general web. "
            "Key verdicts without full-text access automatically downgraded to low confidence."
        ),
    )


# ── LLM Helpers (in agent mode, these prompts are handled by the agent's LLM) ──

def _llm_json_list(prompt: str) -> list[str]:
    """Placeholder — in agent mode, prompts are processed by the agent's LLM.
    In standalone mode, prints the prompt for manual processing."""
    print(f"\n{'='*60}")
    print("📋 LLM PROMPT (requires AI agent):")
    print(f"{'='*60}")
    print(prompt)
    print(f"{'='*60}\n")
    if sys.stdin.isatty():
        resp = input("Paste JSON array response (or press Enter to skip): ").strip()
        if resp:
            return json.loads(resp)
    return []


def _llm_json_dict(prompt: str) -> dict:
    print(f"\n{'='*60}")
    print("📋 LLM PROMPT (requires AI agent):")
    print(f"{'='*60}")
    print(prompt)
    print(f"{'='*60}\n")
    if sys.stdin.isatty():
        resp = input("Paste JSON object response (or press Enter to skip): ").strip()
        if resp:
            return json.loads(resp)
    return {}


# ── CLI Entry Point ──

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fact_check.py <video_url> [whisper_model]")
        print("       python3 fact_check.py --transcript <transcript_text>")
        print("\nGroq Whisper models: whisper-large-v3-turbo (default, fast), whisper-large-v3 (best accuracy)")
        print("Requires GROQ_API_KEY env var (free at https://console.groq.com/keys)")
        print("\n5-Stage Pipeline:")
        print("  1. Transcribe → 2. Decompose Claims → 3. Iterative Search → 4. Cross-Validate → 5. Verdict Report")
        sys.exit(1)

    if sys.argv[1] == "--transcript":
        transcript = " ".join(sys.argv[2:])
    else:
        url = sys.argv[1]
        model_name = sys.argv[2] if len(sys.argv) > 2 else "whisper-large-v3-turbo"
        print("📥 Stage 0: Downloading video audio...")
        audio = download_audio(url)
        print(f"  ✓ {audio}")
        print(f"🎙️ Stage 1: Transcribing (Groq Whisper: {model_name})...")
        transcript = transcribe(audio, model_name)
        print(f"  ✓ Transcription complete ({len(transcript)} chars)")

    print(f"\n📝 Transcript:\n{transcript[:300]}...\n")

    print("🔍 Stage 2: Claim extraction & decomposition...")
    claims_text = extract_claims(transcript)
    claims = []
    for ct in claims_text:
        subs = decompose_claim(ct)
        claims.append(Claim(text=ct, sub_questions=subs))
        print(f"  Claim: {ct[:80]}...")
        for sq in subs:
            print(f"    └─ {sq}")

    print("\n🌐 Stage 3: Search query plan")
    all_queries = []
    for c in claims:
        queries = generate_search_queries(c.text, c.sub_questions)
        all_queries.extend(queries)
        print(f"  Claim: {c.text[:60]}... → {len(queries)} queries")

    output = {
        "transcript": transcript,
        "claims": [asdict(c) for c in claims],
        "search_plan": all_queries,
        "pipeline_status": "awaiting_search",
        "instructions": (
            "Pipeline completed Stage 1-2 (transcription + claim decomposition). "
            "Stage 3-5 require web_search/web_fetch capabilities. "
            "Hand off this output to an AI agent with search capabilities to continue."
        ),
    }

    out_path = os.path.join(tempfile.gettempdir(), "fact_check_pipeline.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📁 Pipeline output: {out_path}")


if __name__ == "__main__":
    main()
