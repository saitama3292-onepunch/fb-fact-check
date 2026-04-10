# fb-fact-check

Video fact-checking tool — 5-stage Deep Research Pipeline.

## Architecture

Based on two core references:
- [ClaimDecomp](https://arxiv.org/abs/2305.11859) (UT Austin) — Claim decomposition + multi-stage evidence retrieval + summarization + verdict
- Gemini Deep Research concept — Iterative search → reflect → re-search loop

```
Video → Transcribe → Claim Decomposition → Iterative Search → Cross-Validation → Verdict Report
        Stage 1       Stage 2               Stage 3            Stage 4            Stage 5
```

### How This Differs from Typical Fact-Check Tools

| Feature | Typical Tools | This Tool |
|---------|--------------|-----------|
| Claim handling | Feed entire text to LLM | Decompose into sub-questions, verify each |
| Search strategy | Search once, conclude | Iterative search ≥2 rounds + gap reflection |
| Language | Monolingual | Multilingual (source language + English + relevant country languages) |
| Sources | No distinction | Academic-first: PubMed > Scholar > News media |
| Verification | None | Key data ≥2 independent sources cross-validated |
| Output | Text reply | Structured JSON report + verdict levels |

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+ and ffmpeg:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Usage

### With AI Agent (Recommended)

Use `AGENTS.md` as the agent's methodology guide, paired with an agent that has web_search + web_fetch capabilities (Kiro CLI, Claude, etc.):

```
@agent Please fact-check this video: https://www.facebook.com/share/v/xxxxx
Follow the 5-stage pipeline in AGENTS.md.
```

### Standalone (Stage 1-2)

```bash
# Transcribe + claim decomposition
python3 fact_check.py https://www.facebook.com/share/v/xxxxx

# Specify Whisper model
python3 fact_check.py https://www.facebook.com/share/v/xxxxx medium

# Direct transcript input (skip transcription)
python3 fact_check.py --transcript "Content from the video..."
```

### Transcription (with timestamps)

```bash
chmod +x transcribe.sh
./transcribe.sh https://www.facebook.com/share/v/xxxxx small
```

## Pipeline Details

See [AGENTS.md](AGENTS.md)

## Whisper Model Selection

| Model | Size | Min RAM | Quality | Speed |
|-------|------|---------|---------|-------|
| tiny | 39 MB | 1 GB | ⭐ | Fastest |
| base | 139 MB | 1 GB | ⭐⭐ | Fast |
| small | 461 MB | 2 GB | ⭐⭐⭐ | Medium |
| medium | 1.5 GB | 5 GB | ⭐⭐⭐⭐ | Slow |
| large | 2.9 GB | 10 GB | ⭐⭐⭐⭐⭐ | Slowest |

## Project Structure

```
fb-fact-check/
├── fact_check.py      # 5-stage pipeline core
├── transcribe.sh      # Transcription script (with timestamps)
├── AGENTS.md          # Deep Research fact-check methodology v2
├── requirements.txt   # Python dependencies
└── README.md
```

## References

- Chen et al. "Complex Claim Verification with Evidence Retrieved in the Wild" (2023) — ClaimDecomp pipeline
- Google Gemini Deep Research — Iterative search → reflect → re-search product concept
- Miranda et al. "Automated Fact Checking in the News Room" (2019) — BBC newsroom agentic fact-checking

## License

MIT
