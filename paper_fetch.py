#!/usr/bin/env python3
"""Academic paper fetcher — bypasses web_fetch limitations.

Finds open-access PDFs via Unpaywall API and extracts text.
Also supports direct PDF URL download + text extraction.

Usage:
    # Search by DOI (uses Unpaywall to find open-access PDF)
    python3 paper_fetch.py doi 10.1038/s41598-019-40463-3

    # Search by title (uses OpenAlex API)
    python3 paper_fetch.py search "chewing side preference facial asymmetry"

    # Direct PDF URL
    python3 paper_fetch.py url https://example.com/paper.pdf

    # Search J-STAGE (Japanese academic papers)
    python3 paper_fetch.py jstage "片側咀嚼 顔面非対称"
"""

import sys, os, json, tempfile, subprocess, urllib.request, urllib.parse

CONTACT_EMAIL = "factcheck@example.com"  # Required by Unpaywall API


def fetch_by_doi(doi: str) -> dict:
    """Use Unpaywall API to find open-access PDF for a DOI."""
    url = f"https://api.unpaywall.org/v2/{doi}?email={CONTACT_EMAIL}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        title = data.get("title", "")
        # Find best open-access PDF
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or best.get("url")
        return {"title": title, "doi": doi, "pdf_url": pdf_url,
                "is_oa": data.get("is_oa", False)}
    except Exception as e:
        return {"error": str(e), "doi": doi}


def search_openalex(query: str, limit: int = 5) -> list[dict]:
    """Search OpenAlex API for papers matching a query."""
    params = urllib.parse.urlencode({
        "search": query, "per_page": limit,
        "select": "id,doi,title,publication_year,open_access,authorships"
    })
    url = f"https://api.openalex.org/works?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "factcheck/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = []
        for w in data.get("results", []):
            authors = ", ".join(
                a.get("author", {}).get("display_name", "")
                for a in (w.get("authorships") or [])[:3]
            )
            oa = w.get("open_access") or {}
            results.append({
                "title": w.get("title"),
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "year": w.get("publication_year"),
                "authors": authors,
                "is_oa": oa.get("is_oa", False),
                "pdf_url": oa.get("oa_url"),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


def search_jstage(query: str, limit: int = 5) -> list[dict]:
    """Search J-STAGE API for Japanese academic papers."""
    params = urllib.parse.urlencode({"keyword": query, "count": limit})
    url = f"https://api.jstage.jst.go.jp/searchapi/do?service=3&{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "factcheck/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            # J-STAGE returns XML
            content = resp.read().decode("utf-8")
        # Simple XML parsing for titles and links
        import re
        entries = re.findall(r"<entry>(.*?)</entry>", content, re.DOTALL)
        results = []
        for entry in entries[:limit]:
            title = re.search(r"<title>(.*?)</title>", entry)
            link = re.search(r'<link.*?href="(.*?)"', entry)
            doi = re.search(r"<prism:doi>(.*?)</prism:doi>", entry)
            results.append({
                "title": title.group(1) if title else "",
                "url": link.group(1) if link else "",
                "doi": doi.group(1) if doi else "",
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


def download_and_extract_pdf(url: str) -> str:
    """Download a PDF and extract text using pdftotext."""
    tmp = os.path.join(tempfile.gettempdir(), "paper.pdf")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; factcheck/1.0)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(tmp, "wb") as f:
                f.write(resp.read())
        result = subprocess.run(
            ["pdftotext", "-layout", tmp, "-"],
            capture_output=True, text=True, timeout=30
        )
        text = result.stdout.strip()
        if len(text) < 100:
            return f"[PDF extraction failed or empty: {len(text)} chars]"
        return text
    except Exception as e:
        return f"[Error: {e}]"


def search_in_text(text: str, terms: list[str]) -> list[str]:
    """Find lines containing any of the search terms."""
    hits = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        for term in terms:
            if term.lower() in line.lower():
                context = lines[max(0, i-2):i+3]
                hits.append("\n".join(context))
                break
    return hits


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    query = " ".join(sys.argv[2:])

    if mode == "doi":
        print(f"🔍 Looking up DOI: {query}")
        info = fetch_by_doi(query)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        if info.get("pdf_url"):
            print(f"\n📄 Downloading PDF...")
            text = download_and_extract_pdf(info["pdf_url"])
            print(f"  Extracted {len(text)} chars")
            out = os.path.join(tempfile.gettempdir(), "paper_text.txt")
            with open(out, "w") as f:
                f.write(text)
            print(f"  Saved to {out}")

    elif mode == "search":
        print(f"🔍 Searching OpenAlex: {query}")
        results = search_openalex(query)
        for r in results:
            oa = "🔓 OA" if r.get("is_oa") else "🔒"
            print(f"  {oa} [{r.get('year')}] {r.get('title')}")
            print(f"     DOI: {r.get('doi')} | Authors: {r.get('authors')}")
            if r.get("pdf_url"):
                print(f"     PDF: {r['pdf_url']}")
            print()

    elif mode == "jstage":
        print(f"🔍 Searching J-STAGE: {query}")
        results = search_jstage(query)
        for r in results:
            print(f"  {r.get('title')}")
            print(f"     URL: {r.get('url')} | DOI: {r.get('doi')}")
            print()

    elif mode == "url":
        print(f"📄 Downloading PDF: {query}")
        text = download_and_extract_pdf(query)
        print(f"  Extracted {len(text)} chars")
        # Search for key terms if provided via stdin
        out = os.path.join(tempfile.gettempdir(), "paper_text.txt")
        with open(out, "w") as f:
            f.write(text)
        print(f"  Saved to {out}")
        print(f"\n  First 500 chars:")
        print(text[:500])

    else:
        print(f"Unknown mode: {mode}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
