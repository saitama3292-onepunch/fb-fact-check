# Fact-Check Agent Methodology — v2

基於 [ClaimDecomp](https://arxiv.org/abs/2305.11859) (UT Austin) 五階段 pipeline，
結合 Gemini Deep Research 的迭代搜尋概念（搜尋→反思→再搜尋）設計。

## Pipeline 架構

```
影片 → [Stage 1] 轉錄
     → [Stage 2] 主張提取 → 主張拆解(子問題)
     → [Stage 3] 多語言迭代搜尋 (≥2 輪)
     → [Stage 4] 證據摘要 + 交叉驗證
     → [Stage 5] 判定 + 報告生成
```

## Stage 1: 語音轉錄

使用 `python3 fact_check.py <URL>` 進行本地 Whisper 轉錄。

## Stage 2: 主張提取與拆解 (Claim Decomposition)

這是整個 pipeline 最關鍵的步驟。參考 ClaimDecomp 論文：

1. **主張提取**：從逐字稿中識別所有可查核的事實性聲明
   - 只提取可用證據驗證的：數據、因果關係、歷史事件、科學宣稱
   - 忽略意見、情緒、修辭
2. **主張拆解**：每個主張拆解為 3-5 個子問題
   - 涵蓋：事實本身、數據來源、因果邏輯、反面證據
   - 子問題格式：yes/no 或 wh-question，可獨立搜尋

## Stage 3: 多輪迭代搜尋 (Iterative Deep Search)

採用「搜尋 → 閱讀 → 反思 → 再搜尋」循環，至少 2 輪。

### 3.1 查詢生成
- 每個子問題生成多語言查詢（中文 + 英文 + 涉及國家語言）
- 加入學術來源限定查詢（PubMed, Scholar, PMC）

### 3.2 第一輪搜尋 + 全文讀取
- 執行搜尋，對有價值的結果用 web_fetch 讀取全文
- **確認讀取完整性**：檢查回傳內容是否包含預期的關鍵段落（如摘要、結論、數據表格）。如果回傳內容明顯不完整（太短、缺少關鍵段落），視為讀取失敗，進入 fallback。
- **全文讀取 Fallback Chain**（依序嘗試）：
  1. PubMed 被擋 → PMC 全文版 (`pmc.ncbi.nlm.nih.gov/articles/PMCxxxxxxx/`)
  2. PMC 也被擋 → Semantic Scholar API (`api.semanticscholar.org`，通常不擋)
  3. Semantic Scholar 也失敗 → Google Scholar 搜論文標題，找 ResearchGate 或大學 repository 的公開版
  4. 都找不到全文 → 搜新聞媒體對該研究的報導作為次級來源
  5. **完全無法取得** → 標註「無法取得原始全文，判定基於摘要/次級來源」，信心降為 low
- 對於關鍵判定，必須至少成功讀取一篇全文來源才能給 high confidence

### 3.3 反思與缺口分析 (Reflection)
評估已收集資訊：
- 哪些子問題已有充分證據？
- 搜尋結果是否互相矛盾？
- 需要換什麼角度搜尋？

### 3.4 追加搜尋
根據缺口分析生成新查詢，填補知識缺口。

### 搜尋優先順序
1. PubMed / PMC（同行評審）
2. Google Scholar / Semantic Scholar
3. 大學官網、政府機構
4. 權威新聞媒體（Reuters, AP, BBC）
5. 一般網頁

### 讀取驗證規則
- 每次 web_fetch 後，檢查回傳內容長度和關鍵詞命中
- 如果回傳 < 200 字且預期是長文，判定為讀取失敗
- 如果回傳包含「Access Denied」「Cloudflare」「403」「Please verify」等字樣，判定為被擋
- 讀取失敗時，立即進入 fallback chain，不要用不完整的內容做判定

## Stage 4: 證據摘要與交叉驗證

### 4.1 Claim-Focused Summarization
- 每篇證據獨立摘要（避免跨文件幻覺）
- 明確標註立場：支持 / 反駁 / 中立
- 區分「同行評審研究」vs「網路文章」

### 4.2 交叉驗證
- 關鍵數據（百分比、倍數、樣本數）至少 2 個獨立來源確認
- 單一來源數據標註「僅單一來源，可信度待確認」
- 矛盾證據需額外搜尋釐清

## Stage 5: 判定與報告

### 判定等級
| 等級 | 定義 |
|------|------|
| true | 完全正確，多個獨立來源確認 |
| mostly_true | 大致正確，細節有小偏差 |
| half_true | 部分正確但有重要遺漏或誇大 |
| mostly_false | 大部分不正確或嚴重誤導 |
| false | 完全錯誤，證據明確反駁 |
| unverifiable | 無法找到足夠證據判定 |

### 信心等級
| 等級 | 條件 |
|------|------|
| high | ≥3 個獨立來源交叉驗證 |
| medium | 2 個來源 |
| low | 單一來源或證據不足 |

### 報告格式
```json
{
  "url": "影片網址",
  "overall_verdict": "整體判定",
  "claims": [
    {
      "claim": "主張文字",
      "verdict": "判定",
      "confidence": "信心",
      "evidence_summary": "證據摘要",
      "sources": ["來源URL"],
      "sub_verdicts": [
        {"question": "子問題", "answer": "回答", "evidence": "證據"}
      ]
    }
  ],
  "methodology_note": "方法論說明"
}
```

## 與 AI Agent 搭配使用

### 自動模式（推薦）
將此文件作為 agent 的 system prompt，搭配具有 web_search + web_fetch 能力的 agent：

```
@agent 請對這個影片進行事實查核：<URL>
按照 AGENTS.md 的五階段 pipeline 執行完整查核。
```

### 半自動模式
```bash
# Step 1-2: 本地轉錄 + 主張拆解
python3 fact_check.py <URL>

# Step 3-5: 將輸出交給 agent 繼續搜尋和判定
```
