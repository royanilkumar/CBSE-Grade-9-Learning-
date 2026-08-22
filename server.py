"""
server.py — MCP server for CBSE Class 9.

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

import json
import os
from pathlib import Path
from collections import defaultdict

import chromadb
from chromadb.utils import embedding_functions
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv(override=True)

DB_DIR = Path(__file__).parent / "data" / "chroma_db"
COLLECTION_NAME = "cbse_class9_maths"

mcp = FastMCP("cbse-class9-maths")

_client = None
_collection = None
_embedding_function = None
_metadata_cache = None

SUBJECT_ALIASES = {
    "math": "Mathematics",
    "maths": "Mathematics",
    "mathematics": "Mathematics",
    "social studies": "Social Science",
    "social_science": "Social Science",
    "social-science": "Social Science",
    "social science": "Social Science",
    "english": "English",
    "hindi": "Hindi",
    "science": "Science",
    "skill": "Skill",
}


def get_embedding_function():
    global _embedding_function
    if _embedding_function is None:
        _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _embedding_function


def get_collection():
    global _client, _collection
    if _collection is None:
        if not DB_DIR.exists():
            raise RuntimeError(
                "No knowledge base found. Run `python ingest.py` after placing "
                "NCERT PDFs in data/pdfs/ first."
            )
        _client = chromadb.PersistentClient(path=str(DB_DIR))
        _collection = _client.get_collection(
            COLLECTION_NAME, embedding_function=get_embedding_function()
        )
    return _collection


def get_metadata():
    global _metadata_cache
    if _metadata_cache is None:
        _metadata_cache = get_collection().get(include=["metadatas"])["metadatas"]
    return _metadata_cache


def normalize_subject(subject: str | None) -> str | None:
    if subject is None:
        return None
    return SUBJECT_ALIASES.get(subject.strip().lower(), subject.strip())


def get_generation_client():
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider == "ollama":
        from openai import OpenAI

        return OpenAI(
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("replace_with_"):
        raise RuntimeError(
            "Set OPENAI_API_KEY, or set LLM_PROVIDER=ollama to use a local "
            "Ollama model."
        )
    from openai import OpenAI

    return OpenAI(api_key=api_key)


@mcp.tool()
def list_chapters(subject: str | None = None) -> list[str]:
    """List every indexed chapter, optionally restricted to one subject."""
    coll = get_collection()
    all_meta = get_metadata()
    subject = normalize_subject(subject)
    if subject:
        all_meta = [meta for meta in all_meta if meta["subject"] == subject]
    chapters = sorted(set(m["chapter"] for m in all_meta))
    return chapters


@mcp.tool()
def search_content(
    query: str,
    chapter: str | None = None,
    top_k: int = 4,
    subject: str | None = None,
) -> list[dict]:
    """
    Semantic search over the indexed NCERT Class 9 textbook content.

    Args:
        query: What to search for, e.g. "factorization of polynomials" or
               "example problems on Heron's formula".
        subject: Optional subject, such as "Mathematics", "Science", "English",
             "Hindi", "Skill", or "Social Science".
        chapter: Optional exact chapter label (from list_chapters) to restrict
                 the search to a single chapter.
        top_k: How many chunks to return (default 6).

    Returns:
        A list of results, each with the passage text and its chapter/page
        source, so you can cite exactly where it came from.
    """
    coll = get_collection()
    filters = []
    if chapter:
        filters.append({"chapter": chapter})
    if subject:
        filters.append({"subject": normalize_subject(subject)})
    where = {"$and": filters} if len(filters) > 1 else (filters[0] if filters else None)
    results = coll.query(
        query_texts=[query],
        n_results=max(1, min(top_k, 10)),
        where=where,
        include=["documents", "metadatas"],
    )

    out = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        out.append({
            "text": doc,
            "chapter": meta["chapter"],
            "subject": meta["subject"],
            "source_file": meta["source_file"],
            "page": meta["page"],
        })
    return out


@mcp.tool()
def get_chapter_content(
    chapter: str, subject: str | None = None, max_chunks: int = 40
) -> list[dict]:
    """
    Retrieve the (near-)full indexed content of one chapter, in page order.
    Useful when generating a worksheet or question set that should cover an
    entire chapter rather than one narrow topic.

    Args:
        chapter: Exact chapter label as returned by list_chapters().
        subject: Optional subject to disambiguate chapters with the same name.
        max_chunks: Safety cap on how many chunks to return.
    """
    coll = get_collection()
    filters = [{"chapter": chapter}]
    if subject:
        filters.append({"subject": normalize_subject(subject)})
    where = {"$and": filters} if len(filters) > 1 else filters[0]
    result = coll.get(where=where, include=["documents", "metadatas"])
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
    all_meta = get_metadata()
    counts = defaultdict(int)
    subject_counts = defaultdict(int)
    for m in all_meta:
        counts[m["chapter"]] += 1
        subject_counts[m["subject"]] += 1
    return {
        "total_chunks": len(all_meta),
        "chapters": dict(sorted(counts.items())),
        "subjects": dict(sorted(subject_counts.items())),
    }


@mcp.tool()
def get_backend_status() -> dict:
    """Report the active database path, collection, and indexed record count."""
    collection = get_collection()
    return {
        "database_path": str(DB_DIR.resolve()),
        "collection": COLLECTION_NAME,
        "total_chunks": collection.count(),
        "subjects": get_indexed_summary()["subjects"],
    }


@mcp.tool()
def generate_questions(
    topic: str,
    subject: str,
    chapter: str | None = None,
    difficulty: str = "medium",
    question_type: str = "application",
    question_count: int = 5,
) -> dict:
    """Generate reasoning-based questions grounded in indexed textbook content."""
    question_count = max(1, min(question_count, 10))
    difficulty = difficulty.lower().strip()
    question_type = question_type.lower().strip()
    if difficulty not in {"easy", "medium", "hard"}:
        raise ValueError("difficulty must be easy, medium, or hard")

    client = get_generation_client()
    passages = search_content(
        query=topic,
        chapter=chapter,
        subject=subject,
        top_k=8,
    )
    if not passages:
        return {"subject": subject, "topic": topic, "questions": []}

    context = "\n\n".join(
        f"Source: {item['source_file']}, page {item['page']}\n{item['text']}"
        for item in passages
    )
    prompt = f"""Create {question_count} original Class 9 questions for {subject}.
Topic: {topic}
"""
    prompt += f"Difficulty: {difficulty}\nQuestion style: {question_type}\n\n"
    prompt += "Use the source passages only for factual grounding. Do not copy questions or sentences. Each question must require reasoning, application, comparison, inference, or multi-step thinking. Check every answer before returning it.\n\n"
    prompt += "Return valid JSON only with this shape:\n"
    prompt += '{"questions":[{"question":"...","answer":"...","reasoning_steps":["..."],"difficulty":"...","source_references":[{"source_file":"...","page":1}]}]}\n\n'
    prompt += f"Source passages:\n{context}"

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "qwen3:8b")),
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a careful CBSE Class 9 assessment designer. Reason step by step internally, verify every answer, and return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or '{"questions": []}'
    generated = json.loads(content)
    return {
        "subject": subject,
        "topic": topic,
        "difficulty": difficulty,
        "question_type": question_type,
        "questions": generated.get("questions", [])[:question_count],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
