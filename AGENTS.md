# Fact-Check Agent Methodology — v3

Based on the [ClaimDecomp](https://arxiv.org/abs/2305.11859) (UT Austin) 5-stage pipeline,
combined with the Gemini Deep Research iterative search concept (search → reflect → re-search).

## v2 → v3 Changes

- **Transcription**: Replaced local Whisper with Groq Whisper API (free, no GPU needed, `whisper-large-v3-turbo`)
- **Fallback Chain**: Added Europe PMC REST API as #1 fallback after PMC is blocked (before Semantic Scholar)
- **Search Priority**: Europe PMC promoted to #1 (was PubMed/PMC)
- **paper_fetch.py**: Added 3 new functions (`search_europepmc`, `fetch_europepmc_by_pmid`, `fetch_europepmc_fulltext`) and 3 CLI modes (`europepmc`, `epmc-pmid`, `epmc-fulltext`)
- **Dependencies**: Removed `openai-whisper` (no longer needed)

## Pipeline Architecture

```
Video → [Stage 1] Transcription (Groq Whisper API)
      → [Stage 2] Claim Extraction → Claim Decomposition (sub-questions)
      → [Stage 3] Multilingual Iterative Search (≥2 rounds)
      → [Stage 4] Evidence Summarization + Cross-Validation
      → [Stage 5] Verdict + Report Generation
```

## Stage 1: Speech-to-Text Transcription

Use `python3 fact_check.py <URL>` — calls Groq Whisper API (requires `GROQ_API_KEY` env var).
Get a free key at https://console.groq.com/keys

Models: `whisper-large-v3-turbo` (default, fast) or `whisper-large-v3` (best accuracy).

## Stage 2: Claim Extraction & Decomposition

This is the most critical step in the pipeline. Based on the ClaimDecomp paper:

1. **Claim Extraction**: Identify all verifiable factual claims from the transcript
   - Only extract evidence-verifiable statements: data, causal relationships, historical events, scientific claims
   - Ignore opinions, emotional expressions, rhetorical questions
2. **Claim Decomposition**: Break each claim into 3-5 independently searchable sub-questions
   - Cover: the fact itself, data sources, causal logic, potential counter-evidence
   - Sub-question format: yes/no or wh-questions, independently searchable

## Stage 3: Multi-Round Iterative Search (Iterative Deep Search)

Follow a "search → read → reflect → re-search" loop, minimum 2 rounds.

### 3.1 Query Generation
- Generate multilingual queries for each sub-question (source language + English + relevant country languages)
- Include academic source-restricted queries (Europe PMC, PubMed, Scholar, PMC)
- **Important**: Search the same concept with different keyword combinations — "not found" does not mean "does not exist"

#### Search Term Strategy: Use Academic Terminology, Not Video Language

Videos use casual, exaggerated language. Academic papers use precise terminology. You must translate the video's claims into the keywords that would actually appear in a paper.

Examples:
| Video says | Search with |
|-----------|-------------|
| "face deforms 0.3mm per year" | `facial asymmetry measurement mm deviation longitudinal` |
| "skin repair ability drops 37%" | `melatonin suppression percentage self-luminous devices` |
| "aging speed 1.5x faster" | `cortisol collagen degradation skin aging quantitative` |
| "3.2x more likely to be asymmetric" | `sleep position compression wrinkles facial asymmetry quantitative` |
| "Stanford 12-year study" | `longitudinal study facial attractiveness aging participants` |

The goal is to find the **real research** behind the claim, then compare the **actual numbers** with what the video stated. Often the underlying science is real but the specific numbers are fabricated or exaggerated.

#### Searching for Specific Numbers

When a video cites a precise number (67%, 0.3mm, 43%, 3.2x, 37%, 48%), search for:
1. The number itself in quotes with related terms
2. The academic concept without the number (to find what the real data says)
3. The institution name in its original language

If the real data exists but with different numbers, that's a key finding — it means the video took real science and inflated/fabricated the statistics.

### 3.2 First Round Search + Full-Text Reading

Execute searches, use web_fetch to read full text of valuable results.

#### Full-Text Reading Validation Rules

After each web_fetch, check the following indicators to determine if full text was successfully retrieved:

| Indicator | Success | Failure |
|-----------|---------|---------|
| Content length | ≥1000 words (academic papers typically 5000-30000 words) | <200 words |
| Structural completeness | Contains Abstract/Methods/Results/Conclusion sections | Only title or navigation menu |
| Key data | Contains the specific numbers or conclusions you need to verify | No relevant content at all |
| Error signals | None | Contains any of the following |

**Failure signal keywords** (any one present = fetch failed):
- `Access Denied`
- `Cloudflare`
- `Checking your browser`
- `403 Forbidden`
- `Please verify you are a human`
- `blocked for possible abuse`
- `Enable JavaScript`

#### Full-Text Reading Fallback Chain

Real-world testing shows ~30% success rate for academic sources via web_fetch. When blocked, try in order:

```
PubMed blocked (common: Cloudflare)
  → PMC full text (pmc.ncbi.nlm.nih.gov/articles/PMCxxxxxxx/)
    → PMC also blocked (common: same Cloudflare)
      → Europe PMC REST API (python3 paper_fetch.py epmc-fulltext PMCxxxxxxx)  ← NEW in v3
        → Semantic Scholar (semanticscholar.org) search by paper title
          → ResearchGate (common: 403)
            → Google Scholar search by paper title, find university repository open-access version
              → Search news media / science journalism coverage of the study (secondary source)
                → Completely unable to retrieve full text
```

**When full text is completely unavailable**:
- If web_search snippets contain sufficient information (e.g., conclusion summary), use as "snippet-only" evidence
- Label as "unable to retrieve original full text, verdict based on search snippets"
- Confidence automatically drops to low
- Cannot give high confidence verdict based solely on snippets

#### Europe PMC REST API Endpoints

| Endpoint | CLI Command | Description |
|----------|-------------|-------------|
| search | `python3 paper_fetch.py europepmc "query"` | Keyword search, returns JSON (title, abstract, PMID, PMCID, DOI) |
| PMID query | `python3 paper_fetch.py epmc-pmid 31263089` | Lookup specific paper by PMID via `EXT_ID:{pmid}+SRC:MED` |
| fullTextXML | `python3 paper_fetch.py epmc-fulltext PMC6611068` | Full paper XML by PMCID |

#### Real-World Success Rate Reference

| Source | web_fetch Success Rate | Common Failure Reason |
|--------|----------------------|----------------------|
| Europe PMC REST API | ~100% | No auth required, JSON/XML responses | 
| PMC/PubMed | ~20% | Cloudflare, Access Denied |
| ResearchGate | ~10% | 403 Forbidden |
| MDPI | ~30% | 403 Forbidden |
| News media (HuffPost, BBC, etc.) | ~80% | Occasional paywall |
| Medical News Today | ~90% | Rarely fails |
| Wikipedia | ~95% | Rarely fails |
| Semantic Scholar API | 0% (JSON) | web_fetch doesn't support JSON responses |

**Strategy recommendation**: Use Europe PMC REST API as the primary academic source — it has ~100% success rate and provides abstracts, metadata, and full-text XML for open-access papers. Fall back to science journalism sites for non-OA papers.

### 3.3 Reflection & Gap Analysis

After each search round, answer:
1. Which sub-questions have sufficient evidence? (at least 1 full text or 2 snippets)
2. Which sub-questions lack evidence? What additional searches are needed?
3. Are search results contradictory?
4. **Is "not found" because it doesn't exist, or because the search terms weren't precise enough?**
   - Try different languages (source language / English / Japanese / relevant country languages)
   - Try different keyword combinations
   - Try searching institution names in their original language (e.g., "Nippon Dental University" in Japanese: "日本歯科大学")

### 3.4 Follow-up Search

Generate new queries based on gap analysis to fill knowledge gaps. Complete at least 2 rounds.

### Search Priority Order
1. Europe PMC REST API (peer-reviewed, ~100% success rate)
2. PubMed / PMC (peer-reviewed, but often blocked)
3. Google Scholar / Semantic Scholar
4. University websites, government agencies
5. Authoritative news media (Reuters, AP, BBC)
6. High-quality science journalism (Medical News Today, Healthline)
7. General web pages

## Stage 4: Evidence Summarization & Cross-Validation

### 4.1 Claim-Focused Summarization
- Summarize each piece of evidence independently (avoid cross-document hallucination)
- Explicitly label stance: support / refute / neutral
- Distinguish "peer-reviewed research" vs "web article" vs "snippet only"
- Label evidence source reading method: full_text / snippet / secondary_source

### 4.2 Cross-Validation
- Key data (percentages, multipliers, sample sizes) require at least 2 independent sources to confirm
- Single-source data labeled "single source only, credibility pending confirmation"
- Contradictory evidence requires additional search to clarify
- **Precise numbers cited in videos (e.g., 67%, 0.3mm, 43%, 3.2x, 37%, 48%) must be traced to original academic sources, otherwise labeled as "unverifiable number"**

## Stage 5: Verdict & Report

### Verdict Levels
| Level | Definition |
|-------|-----------|
| true | Completely correct, confirmed by multiple independent sources |
| mostly_true | Generally correct, minor detail discrepancies |
| half_true | Partially correct but with significant omissions or exaggerations |
| mostly_false | Mostly incorrect or seriously misleading |
| false | Completely wrong, clearly refuted by evidence |
| unverifiable | Insufficient evidence to make a determination |

### Confidence Levels
| Level | Criteria |
|-------|---------|
| high | ≥3 independent sources cross-validated, at least 1 full-text read successful |
| medium | 2 sources, or based only on snippets |
| low | Single source, snippet only, or all full-text reads failed |

### Report Format
```json
{
  "url": "video URL",
  "overall_verdict": "overall verdict",
  "claims": [
    {
      "claim": "claim text",
      "verdict": "verdict",
      "confidence": "confidence",
      "evidence_summary": "evidence summary",
      "evidence_quality": "full_text / snippet_only / secondary_source",
      "sources": ["source URLs"],
      "sub_verdicts": [
        {"question": "sub-question", "answer": "answer", "evidence": "evidence"}
      ]
    }
  ],
  "methodology_note": "methodology description",
  "fetch_stats": {
    "attempted": 7,
    "success_full_text": 2,
    "success_snippet_only": 3,
    "blocked": 4,
    "success_rate": "29%"
  }
}
```

## Using with AI Agents

### Automatic Mode (Recommended)
Use this file as the agent's system prompt, paired with an agent that has web_search + web_fetch capabilities:

```
@agent Please fact-check this video: <URL>
Follow the 5-stage pipeline in AGENTS.md.
```

### Semi-Automatic Mode
```bash
# Step 1-2: Local transcription + claim decomposition
python3 fact_check.py <URL>

# Step 3-5: Hand off output to agent for search and verdict
```
