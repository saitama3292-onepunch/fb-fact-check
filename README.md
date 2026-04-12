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
| Sources | No distinction | Academic-first: Europe PMC > PubMed > Scholar > News media |
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

### Groq API Key (for transcription)

Transcription uses Groq's free Whisper API. Get a key at https://console.groq.com/keys

```bash
export GROQ_API_KEY="gsk_..."
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

# Specify Groq Whisper model
python3 fact_check.py https://www.facebook.com/share/v/xxxxx whisper-large-v3

# Direct transcript input (skip transcription)
python3 fact_check.py --transcript "Content from the video..."
```

### Transcription (with timestamps)

```bash
chmod +x transcribe.sh
./transcribe.sh https://www.facebook.com/share/v/xxxxx
```

### Paper Fetching

```bash
# Search Europe PMC (best success rate, ~100%)
python3 paper_fetch.py europepmc "facial asymmetry sleep position"

# Lookup by PMID via Europe PMC
python3 paper_fetch.py epmc-pmid 31263089

# Fetch full-text XML from Europe PMC
python3 paper_fetch.py epmc-fulltext PMC6611068

# Search by DOI (Unpaywall)
python3 paper_fetch.py doi 10.1038/s41598-019-40463-3

# Search by title (OpenAlex)
python3 paper_fetch.py search "chewing side preference facial asymmetry"

# Search J-STAGE (Japanese papers)
python3 paper_fetch.py jstage "片側咀嚼 顔面非対称"

# Direct PDF URL
python3 paper_fetch.py url https://example.com/paper.pdf
```

## Pipeline Details

See [AGENTS.md](AGENTS.md)

## Groq Whisper Models

| Model | Cost/Hour | Quality | Speed | Languages |
|-------|-----------|---------|-------|-----------|
| whisper-large-v3-turbo | $0.04 | ⭐⭐⭐⭐ | Fastest | Multilingual |
| whisper-large-v3 | $0.111 | ⭐⭐⭐⭐⭐ | Fast | Multilingual |

Free tier: 25MB max file size. Files are auto-compressed if larger.

## Project Structure

```
fb-fact-check/
├── fact_check.py      # 5-stage pipeline core (Groq Whisper transcription)
├── paper_fetch.py     # Academic paper fetcher (Europe PMC, OpenAlex, Unpaywall, J-STAGE)
├── transcribe.sh      # Transcription script (Groq Whisper API)
├── AGENTS.md          # Deep Research fact-check methodology v3
├── requirements.txt   # Python dependencies
└── README.md
```

## References

- Chen et al. "Complex Claim Verification with Evidence Retrieved in the Wild" (2023) — ClaimDecomp pipeline
- Google Gemini Deep Research — Iterative search → reflect → re-search product concept
- Miranda et al. "Automated Fact Checking in the News Room" (2019) — BBC newsroom agentic fact-checking
- [Europe PMC REST API](https://europepmc.org/RestfulWebService) — Open access to life sciences literature

## License

MIT
