# CBSE Class 9 Maths — MCP Server

Lets an AI assistant (Claude Desktop, Claude Code, or your own agent using the
Anthropic API) search the actual NCERT Class 9 Maths textbook content and use
it to generate accurate sample questions, worksheets, and explanations —
grounded in the real book instead of the model's general knowledge.

## How it works

```
NCERT PDFs  --ingest.py-->  local vector DB  --server.py (MCP)-->  Claude
(data/pdfs/)                (data/chroma_db/)   search/retrieval tools
```

The MCP server only *retrieves* textbook passages with chapter/page
attribution. The connected assistant is the one that reasons over those
passages to write questions, worksheets, and explanations — so you always get
content actually grounded in the NCERT book, with a citation trail.

## 1. Get the PDFs

Download official NCERT Class 9 Maths chapter PDFs:

- Go to **https://ncert.nic.in** → **Publications** → **PDF (I-XII) Books** → **Class 9** → **Mathematics**
- Download each chapter you want covered
- NCERT has both an older 15-chapter edition and a newer restructured
  ("Ganita Prakash") edition in circulation for 2026-27 — grab whichever your
  school/CBSE syllabus actually specifies this year

Save them into `data/pdfs/`, ideally named so the chapter is obvious, e.g.:

```
data/pdfs/
  ch01_number_systems.pdf
  ch02_polynomials.pdf
  ch03_coordinate_geometry.pdf
  ...
```

(The ingest script guesses chapter names from the filename — if you skip the
`chNN_` prefix it'll just use the filename as the label, which still works
fine, just less tidy.)

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Build the knowledge base

```bash
python ingest.py
```

Re-run this any time you add, remove, or replace PDFs — it rebuilds the index
from scratch each time.

## 4. Connect it to an assistant

### Option A — Claude Desktop

Add this to your Claude Desktop MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cbse-class9-maths": {
      "command": "python",
      "args": ["/absolute/path/to/cbse-math-mcp/server.py"]
    }
  }
}
```

Restart Claude Desktop. You can then ask things like:
- "Generate 10 MCQs from Chapter 2: Polynomials, mixed difficulty"
- "Make a worksheet on factorization with an answer key"
- "Explain the proof of Heron's formula the way the textbook does it"

### Option B — Your own agent script (Anthropic API)

Any MCP-compatible client library works. The general pattern:
1. Your agent calls `get_indexed_summary` or `list_chapters` to see what's available
2. It calls `search_content` or `get_chapter_content` for the topic requested
3. It passes those retrieved passages to Claude (via the Messages API) with an
   instruction like "using only the passages below, generate 10 CBSE-style
   exam questions on {topic}, with an answer key"

## Tools exposed by the server

| Tool | Purpose |
|---|---|
| `get_indexed_summary` | See what chapters/how much content is indexed |
| `list_chapters` | List all indexed chapter labels |
| `search_content(query, chapter?, top_k)` | Semantic search for a topic |
| `get_chapter_content(chapter, max_chunks)` | Pull most/all of one chapter, in order |

## Extending this

Natural next steps once the core loop works:
- Add a `subject` field and ingest Science/Social Science PDFs too (currently
  hardcoded to Mathematics — change the `"subject"` value in `ingest.py`)
- Add a `generate_worksheet_docx` tool that formats the assistant's output
  into a downloadable Word doc (question paper + separate answer key)
- Add OCR (e.g. `pytesseract`) if any of your source PDFs are scanned images
  rather than text-based
- Track which questions a student has already seen, to avoid repeats across
  sessions
