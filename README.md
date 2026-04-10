# fb-fact-check

Facebook 影片事實查核工具 — 本地 Whisper 語音轉錄 + AI 驅動的 Deep Research 查核方法論。

## 功能

- **影片音訊下載** — 透過 yt-dlp 從 Facebook（及其他平台）下載影片音訊
- **本地語音轉文字** — 使用 OpenAI Whisper（small 模型），完全離線，無需 API Key
- **Deep Research 查核方法論** — 參考 Gemini Deep Research 架構設計的迭代查核流程（見 [AGENTS.md](AGENTS.md)）

## 查核方法論亮點

| 特性 | 說明 |
|------|------|
| 迭代深度搜尋 | 搜尋 → 閱讀全文 → 反思缺口 → 再搜尋，至少 2 輪 |
| 多語言搜尋 | 中文 + 英文 + 涉及國家語言（如日文） |
| 學術來源優先 | PubMed > Google Scholar > 權威媒體 > 一般網頁 |
| 反爬蟲應對 | PubMed 被擋改走 PMC，論文被擋走 ResearchGate |
| 交叉驗證 | 關鍵數據至少 2 個獨立來源確認 |

## 安裝

```bash
pip install -r requirements.txt
```

需要 Python 3.9+ 和 ffmpeg：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

## 使用

### 轉錄影片

```bash
# 預設使用 small 模型
python3 fact_check.py https://www.facebook.com/share/v/xxxxx

# 指定模型（tiny/base/small/medium/large）
python3 fact_check.py https://www.facebook.com/share/v/xxxxx medium
```

### 轉錄（含時間軸）

```bash
chmod +x transcribe.sh
./transcribe.sh https://www.facebook.com/share/v/xxxxx small
```

### 搭配 AI Agent 查核

將 `AGENTS.md` 作為 AI agent 的 system prompt 或指引文件，搭配具有 web_search 和 web_fetch 能力的 agent 使用（如 Kiro CLI、Claude 等），即可執行完整的 Deep Research 事實查核流程。

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
├── fact_check.py     # 核心轉錄工具（Python）
├── transcribe.sh     # 轉錄腳本（含時間軸輸出）
├── AGENTS.md         # Deep Research 查核方法論
├── requirements.txt  # Python 依賴
└── README.md
```

## License

MIT
