"""
server.py — MCP server for CBSE Class 9 Mathematics.

Exposes retrieval tools over content ingested from NCERT PDFs (see ingest.py).
This server deliberately does NOT generate questions/worksheets itself — it
hands back real textbook passages with chapter/page attribution, and lets the
connected assistant (e.g. Claude, via Claude Desktop or the API) do the
reasoning/generation grounded in that retrieved content. This keeps the
server simple, fast, and free of any LLM API key.

Run:
    python server.py

Then point an MCP client (e.g. Claude Desktop's config, or Claude Code) at
this script. See README.md for the Claude Desktop config snippet.
"""

from pathlib import Path
from collections import defaultdict

import chromadb
from chromadb.utils import embedding_functions
from mcp.server.fastmcp import FastMCP

DB_DIR = Path(__file__).parent / "data" / "chroma_db"
COLLECTION_NAME = "cbse_class9_maths"

mcp = FastMCP("cbse-class9-maths")

_client = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        if not DB_DIR.exists():
            raise RuntimeError(
                "No knowledge base found. Run `python ingest.py` after placing "
                "NCERT PDFs in data/pdfs/ first."
            )
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _client = chromadb.PersistentClient(path=str(DB_DIR))
        _collection = _client.get_collection(COLLECTION_NAME, embedding_function=embed_fn)
    return _collection


@mcp.tool()
def list_chapters() -> list[str]:
    """List every chapter currently indexed in the CBSE Class 9 Maths knowledge base."""
    coll = get_collection()
    all_meta = coll.get(include=["metadatas"])["metadatas"]
    chapters = sorted(set(m["chapter"] for m in all_meta))
    return chapters


@mcp.tool()
def search_content(query: str, chapter: str | None = None, top_k: int = 6) -> list[dict]:
    """
    Semantic search over the NCERT Class 9 Maths textbook content.

    Args:
        query: What to search for, e.g. "factorization of polynomials" or
               "example problems on Heron's formula".
        chapter: Optional exact chapter label (from list_chapters) to restrict
                 the search to a single chapter.
        top_k: How many chunks to return (default 6).

    Returns:
        A list of results, each with the passage text and its chapter/page
        source, so you can cite exactly where it came from.
    """
    coll = get_collection()
    where = {"chapter": chapter} if chapter else None
    results = coll.query(query_texts=[query], n_results=top_k, where=where)

    out = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        out.append({
            "text": doc,
            "chapter": meta["chapter"],
            "source_file": meta["source_file"],
            "page": meta["page"],
        })
    return out


@mcp.tool()
def get_chapter_content(chapter: str, max_chunks: int = 40) -> list[dict]:
    """
    Retrieve the (near-)full indexed content of one chapter, in page order.
    Useful when generating a worksheet or question set that should cover an
    entire chapter rather than one narrow topic.

    Args:
        chapter: Exact chapter label as returned by list_chapters().
        max_chunks: Safety cap on how many chunks to return.
    """
    coll = get_collection()
    result = coll.get(where={"chapter": chapter}, include=["documents", "metadatas"])
    items = list(zip(result["documents"], result["metadatas"]))
    items.sort(key=lambda pair: (pair[1]["source_file"], pair[1]["page"]))
    items = items[:max_chunks]
    return [
        {"text": doc, "page": meta["page"], "source_file": meta["source_file"]}
        for doc, meta in items
    ]


@mcp.tool()
def get_indexed_summary() -> dict:
    """
    Return a quick summary of what's currently in the knowledge base:
    chapters indexed and how many chunks each has. Useful as a first call
    to see what material is available before searching or generating content.
    """
    coll = get_collection()
    all_meta = coll.get(include=["metadatas"])["metadatas"]
    counts = defaultdict(int)
    for m in all_meta:
        counts[m["chapter"]] += 1
    return {
        "total_chunks": len(all_meta),
        "chapters": dict(sorted(counts.items())),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
