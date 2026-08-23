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

Copy `.env.example` to `.env`. The `.env` file is ignored by Git and loaded
automatically. Retrieval-only mode is the default and needs no LLM model or
API key.

Run `ingest.py` again whenever PDFs are added, removed, or replaced. It
rebuilds the local Chroma index from scratch.

## Local chat

Start the interactive tutor after completing the Ollama setup below:

```powershell
.\.venv\Scripts\python.exe chat.py
```

Use `/subject Science` or `/subject Maths` to restrict answers. Use `/quit`
to exit. The chat retrieves local textbook passages before asking the model to
answer, so responses include source-page references.

## Local HTTP server

Start an API on port 8000:

```powershell
.\.venv\Scripts\python.exe local_server.py
```

Open <http://127.0.0.1:8000/> in a browser for the chat window.

Check the backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

List chapters without an AI key:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/chapters
```

Ask a question:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"subject":"Science","question":"Why is sunlight important for photosynthesis?"}'
```

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

## Ollama setup

Install Ollama from <https://ollama.com>, then open a new PowerShell window.
Download the configured model:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen3:8b
```

Check that the model is installed and start the Ollama service if needed:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

Confirm `.env` contains:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
```

Start the browser chat in another PowerShell window:

```powershell
.\.venv\Scripts\python.exe local_server.py
```

Open <http://127.0.0.1:8000/>. Without an LLM configuration, it returns
matching textbook passages and source links. Configure Ollama below when you
want generated explanations.

If you see `model 'qwen3:8b' not found`, run `ollama pull qwen3:8b` and
restart `local_server.py`. If Ollama is installed but `ollama` is not
recognized, use the full executable path shown above.

## OpenAI alternative

To use OpenAI instead, change `.env` to `LLM_PROVIDER=openai`, set a valid
`OPENAI_API_KEY`, and optionally set `OPENAI_MODEL=gpt-4o-mini`.

For faster but less detailed local answers, change `LLM_MODEL` to
`qwen2.5:7b`.

## MCP tools

| Tool | Purpose |
|---|---|
| `get_indexed_summary` | Show indexed chunk and subject counts |
| `get_backend_status` | Show the active database path and record count |
| `list_chapters(subject?)` | List chapters, optionally by subject |
| `search_content(query, chapter?, top_k, subject?)` | Semantic search with optional filters |
| `get_chapter_content(chapter, subject?, max_chunks)` | Retrieve a chapter in page order |

Scanned PDFs may need OCR before they can be indexed.
