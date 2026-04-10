# fb-fact-check

Facebook 影片事實查核工具 — 五階段 Deep Research Pipeline。

## 架構

基於兩個核心研究：
- [ClaimDecomp](https://arxiv.org/abs/2305.11859) (UT Austin) — 主張拆解 + 多階段證據檢索 + 摘要 + 判定
- Gemini Deep Research 概念 — 迭代式搜尋→反思→再搜尋循環

```
影片 → 轉錄 → 主張拆解 → 迭代搜尋 → 交叉驗證 → 判定報告
       Stage1   Stage2      Stage3      Stage4      Stage5
```

### 與一般 fact-check 工具的差異

| 特性 | 一般工具 | 本工具 |
|------|---------|--------|
| 主張處理 | 整段丟給 LLM | 拆解為子問題，逐一驗證 |
| 搜尋策略 | 搜一次就下結論 | 迭代搜尋 ≥2 輪 + 反思缺口 |
| 語言 | 單語 | 多語言（中/英 + 涉及國語言） |
| 來源 | 不區分 | 學術優先：PubMed > Scholar > 媒體 |
| 驗證 | 無 | 關鍵數據 ≥2 獨立來源交叉驗證 |
| 輸出 | 文字回覆 | 結構化 JSON 報告 + 判定等級 |

## 安裝

```bash
pip install -r requirements.txt
```

需要 Python 3.10+ 和 ffmpeg：
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## 使用

### 搭配 AI Agent（推薦）

將 `AGENTS.md` 作為 agent 的指引，搭配具有 web_search + web_fetch 能力的 agent（Kiro CLI、Claude 等）：

```
@agent 請對這個影片進行事實查核：https://www.facebook.com/share/v/xxxxx
按照 AGENTS.md 的五階段 pipeline 執行。
```

### 獨立執行（Stage 1-2）

```bash
# 轉錄 + 主張拆解
python3 fact_check.py https://www.facebook.com/share/v/xxxxx

# 指定 Whisper 模型
python3 fact_check.py https://www.facebook.com/share/v/xxxxx medium

# 直接輸入逐字稿（跳過轉錄）
python3 fact_check.py --transcript "影片中說的內容..."
```

### 轉錄（含時間軸）

```bash
chmod +x transcribe.sh
./transcribe.sh https://www.facebook.com/share/v/xxxxx small
```

## Pipeline 詳細說明

見 [AGENTS.md](AGENTS.md)

## Whisper 模型選擇

| 模型 | 大小 | 最低 RAM | 中文品質 | 速度 |
|------|------|---------|---------|------|
| tiny | 39 MB | 1 GB | ⭐ | 最快 |
| base | 139 MB | 1 GB | ⭐⭐ | 快 |
| small | 461 MB | 2 GB | ⭐⭐⭐ | 中等 |
| medium | 1.5 GB | 5 GB | ⭐⭐⭐⭐ | 慢 |
| large | 2.9 GB | 10 GB | ⭐⭐⭐⭐⭐ | 最慢 |

## 專案結構

```
fb-fact-check/
├── fact_check.py      # 五階段 pipeline 核心
├── transcribe.sh      # 轉錄腳本（含時間軸）
├── AGENTS.md          # Deep Research 查核方法論 v2
├── requirements.txt   # Python 依賴
└── README.md
```

## 參考文獻

- Chen et al. "Complex Claim Verification with Evidence Retrieved in the Wild" (2023) — ClaimDecomp pipeline
- Google Gemini Deep Research — 迭代搜尋→反思→再搜尋的產品概念
- Miranda et al. "Automated Fact Checking in the News Room" (2019) — BBC 新聞室 agentic fact-checking

## License

MIT
