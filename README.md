# CBSE Class 9 Learning — MCP Server

This MCP server indexes NCERT Class 9 textbook PDFs and retrieves passages
with chapter and page attribution for an AI assistant.

## PDF layout

Place PDFs in a subject folder under `data/pdfs/`:

```
data/pdfs/maths/
  ch01_number_systems.pdf
data/pdfs/science/
  ch01_matter_in_our_surroundings.pdf
data/pdfs/social_science/
  ch01_india_size_and_location.pdf
data/pdfs/english/
data/pdfs/hindi/
data/pdfs/skill/
```

Folders named `maths`, `mathematics`, `science`, `english`, `hindi`, `skill`, or
`social_science` are recognized. PDFs placed directly in `data/pdfs/` are
treated as Mathematics for compatibility. Chapter labels are inferred from
filenames such as `ch01_topic.pdf`.

Download the official NCERT Class 9 books from <https://ncert.nic.in> and use
the edition specified by your school or CBSE syllabus.

## Install and index

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ingest.py
```

Run `ingest.py` again whenever PDFs are added, removed, or replaced. It
rebuilds the local Chroma index from scratch.

## Claude Desktop configuration

```json
{
  "mcpServers": {
    "cbse-class9-learning": {
      "command": "C:\\Users\\abhiJ\\MCP\\CBSE MCP\\CBSE-Grade-9-Learning-\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\abhiJ\\MCP\\CBSE MCP\\CBSE-Grade-9-Learning-\\server.py"
      ]
    }
  }
}
```

Restart Claude Desktop after changing the configuration.

## MCP tools

| Tool | Purpose |
|---|---|
| `get_indexed_summary` | Show indexed chunk and subject counts |
| `list_chapters(subject?)` | List chapters, optionally by subject |
| `search_content(query, chapter?, top_k, subject?)` | Semantic search with optional filters |
| `get_chapter_content(chapter, subject?, max_chunks)` | Retrieve a chapter in page order |

Scanned PDFs may need OCR before they can be indexed.
