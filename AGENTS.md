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
- **重要**：同一個概念要用不同關鍵詞組合搜尋，「搜不到」不等於「不存在」

### 3.2 第一輪搜尋 + 全文讀取

執行搜尋，對有價值的結果用 web_fetch 讀取全文。

#### 全文讀取驗證規則

每次 web_fetch 後，必須檢查以下指標判斷是否成功讀到全文：

| 指標 | 成功 | 失敗 |
|------|------|------|
| 內容長度 | ≥1000 字（學術論文通常 5000-30000 字） | <200 字 |
| 結構完整性 | 包含 Abstract/Methods/Results/Conclusion 等段落 | 只有標題或導航選單 |
| 關鍵數據 | 包含你要驗證的具體數字或結論 | 完全沒有相關內容 |
| 錯誤訊號 | 無 | 包含以下任一字樣 |

**失敗訊號關鍵詞**（出現任一即判定讀取失敗）：
- `Access Denied`
- `Cloudflare`
- `Checking your browser`
- `403 Forbidden`
- `Please verify you are a human`
- `blocked for possible abuse`
- `Enable JavaScript`

#### 全文讀取 Fallback Chain

實測結果：學術來源的 web_fetch 成功率約 30%。被擋時依序嘗試：

```
PubMed 被擋 (常見：Cloudflare)
  → PMC 全文版 (pmc.ncbi.nlm.nih.gov/articles/PMCxxxxxxx/)
    → PMC 也被擋 (常見：同樣 Cloudflare)
      → Semantic Scholar (semanticscholar.org) 搜論文標題
        → ResearchGate (常見：403)
          → Google Scholar 搜論文標題，找大學 repository 的公開版
            → 搜新聞媒體/科普網站對該研究的報導（次級來源）
              → 完全無法取得全文
```

**完全無法取得全文時的處理**：
- 如果 web_search 的 snippet 包含足夠資訊（如結論摘要），可作為「僅 snippet」證據使用
- 標註「無法取得原始全文，判定基於搜尋摘要」
- 信心自動降為 low
- 不能僅靠 snippet 給 high confidence 判定

#### 實測成功率參考

| 來源 | web_fetch 成功率 | 常見失敗原因 |
|------|-----------------|-------------|
| PMC/PubMed | ~20% | Cloudflare, Access Denied |
| ResearchGate | ~10% | 403 Forbidden |
| MDPI | ~30% | 403 Forbidden |
| 新聞媒體 (HuffPost, BBC 等) | ~80% | 偶爾 paywall |
| Medical News Today | ~90% | 極少失敗 |
| Wikipedia | ~95% | 極少失敗 |
| Semantic Scholar API | 0% (JSON) | web_fetch 不支援 JSON 回應 |

**策略建議**：優先搜尋有引用學術研究的高品質科普/新聞文章（如 Medical News Today、HuffPost Health），這些網站成功率高且通常會引用原始論文的關鍵數據。

### 3.3 反思與缺口分析 (Reflection)

每輪搜尋後必須回答：
1. 哪些子問題已有充分證據？（至少 1 篇全文或 2 個 snippet）
2. 哪些子問題證據不足？需要什麼追加搜尋？
3. 搜尋結果是否互相矛盾？
4. **「搜不到」是因為不存在，還是搜尋詞不夠精確？**
   - 嘗試不同語言（中/英/日/涉及國語言）
   - 嘗試不同關鍵詞組合
   - 嘗試搜機構名稱的原文（如「日本齒科大學」→「日本歯科大学」→「Nippon Dental University」）

### 3.4 追加搜尋

根據缺口分析生成新查詢，填補知識缺口。至少完成 2 輪搜尋。

### 搜尋優先順序
1. PubMed / PMC（同行評審）
2. Google Scholar / Semantic Scholar
3. 大學官網、政府機構
4. 權威新聞媒體（Reuters, AP, BBC）
5. 高品質科普網站（Medical News Today, Healthline）
6. 一般網頁

## Stage 4: 證據摘要與交叉驗證

### 4.1 Claim-Focused Summarization
- 每篇證據獨立摘要（避免跨文件幻覺）
- 明確標註立場：支持 / 反駁 / 中立
- 區分「同行評審研究」vs「網路文章」vs「僅 snippet」
- 標註證據來源的讀取方式：全文 / snippet / 次級來源

### 4.2 交叉驗證
- 關鍵數據（百分比、倍數、樣本數）至少 2 個獨立來源確認
- 單一來源數據標註「僅單一來源，可信度待確認」
- 矛盾證據需額外搜尋釐清
- **影片中引用的精確數字（如 67%、0.3mm、43%、3.2倍、37%、48%）必須在學術來源中找到原始出處，否則標註為「無法驗證的數字」**

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
| high | ≥3 個獨立來源交叉驗證，至少 1 篇全文讀取成功 |
| medium | 2 個來源，或僅基於 snippet |
| low | 單一來源、僅 snippet、或全文讀取全部失敗 |

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
      "evidence_quality": "full_text / snippet_only / secondary_source",
      "sources": ["來源URL"],
      "sub_verdicts": [
        {"question": "子問題", "answer": "回答", "evidence": "證據"}
      ]
    }
  ],
  "methodology_note": "方法論說明",
  "fetch_stats": {
    "attempted": 7,
    "success_full_text": 2,
    "success_snippet_only": 3,
    "blocked": 4,
    "success_rate": "29%"
  }
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
