"""
ingest.py — Turn CBSE/NCERT PDFs into a searchable local knowledge base.

Usage:
     1. Drop NCERT Class 9 PDFs into ./data/pdfs/<subject>/, where subject is
         maths, science, social_science, english, hindi, or skill. Root-level
         PDFs remain Mathematics.
    2. Run:  python ingest.py
    3. This builds a persistent Chroma vector store in ./data/chroma_db/

Re-run this script any time you add or update PDFs — it fully rebuilds the
collection so you don't get duplicate/stale chunks.
"""

import os
import re
from pathlib import Path

from pypdf import PdfReader
from tqdm import tqdm
import chromadb
from chromadb.utils import embedding_functions

PDF_DIR = Path(__file__).parent / "data" / "pdfs"
DB_DIR = Path(__file__).parent / "data" / "chroma_db"
COLLECTION_NAME = "cbse_class9_maths"

SUBJECT_NAMES = {
    "maths": "Mathematics",
    "mathematics": "Mathematics",
    "science": "Science",
    "social_science": "Social Science",
    "social-science": "Social Science",
    "social science": "Social Science",
    "english": "English",
    "hindi": "Hindi",
    "skill": "Skill",
}

CHUNK_SIZE_WORDS = 220      # roughly one solid "paragraph" of study content
CHUNK_OVERLAP_WORDS = 40    # keeps context continuous across chunk boundaries


def extract_pages(pdf_path: Path):
    """Yield (page_number, text) for every page in a PDF."""
    reader = PdfReader(str(pdf_path))
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            yield i, text


def chunk_text(text: str, size=CHUNK_SIZE_WORDS, overlap=CHUNK_OVERLAP_WORDS):
    """Split text into overlapping word-count chunks."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


def guess_chapter_label(filename: str) -> str:
    """Best-effort chapter label from filename, e.g. 'ch01_number_systems.pdf' -> 'Chapter 1: Number Systems'."""
    stem = Path(filename).stem
    m = re.match(r"ch(?:apter)?[\s_-]*0*(\d+)[\s_-]*(.*)", stem, re.IGNORECASE)
    if m:
        num, rest = m.groups()
        title = rest.replace("_", " ").replace("-", " ").strip().title()
        return f"Chapter {num}: {title}" if title else f"Chapter {num}"
    return stem.replace("_", " ").title()


def subject_for_pdf(pdf_path: Path) -> str:
    """Get the subject from the immediate folder, defaulting to Mathematics."""
    return SUBJECT_NAMES.get(pdf_path.parent.name.lower(), "Mathematics")


def main():
    if not PDF_DIR.exists() or not any(PDF_DIR.rglob("*.pdf")):
        print(f"No PDFs found in {PDF_DIR}")
        print("Download NCERT Class 9 chapter PDFs from ncert.nic.in "
              "(Publications > PDF (I-XII) Books > Class 9 > Mathematics) "
              "and place them there first.")
        return

    print("Loading embedding model (first run downloads it, ~80MB)...")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path=str(DB_DIR))
    # Fresh rebuild each time so stale/removed PDFs don't linger in the index
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME, embedding_function=embed_fn)

    doc_id = 0
    ids, docs, metadatas = [], [], []

    pdf_files = sorted(PDF_DIR.rglob("*.pdf"))
    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        chapter_label = guess_chapter_label(pdf_path.name)
        subject = subject_for_pdf(pdf_path)
        for page_num, page_text in extract_pages(pdf_path):
            for chunk in chunk_text(page_text):
                ids.append(f"doc_{doc_id}")
                docs.append(chunk)
                metadatas.append({
                    "subject": subject,
                    "grade": "9",
                    "chapter": chapter_label,
                    "source_file": pdf_path.name,
                    "page": page_num,
                })
                doc_id += 1

    if not docs:
        print("No extractable text found in the PDFs (they may be scanned images — "
              "you'd need OCR first).")
        return

    # Chroma has a batch add limit on some backends; add in batches to be safe
    BATCH = 500
    for i in range(0, len(docs), BATCH):
        collection.add(
            ids=ids[i:i + BATCH],
            documents=docs[i:i + BATCH],
            metadatas=metadatas[i:i + BATCH],
        )

    print(f"Done. Indexed {len(docs)} chunks from {len(pdf_files)} PDF(s) into {DB_DIR}")


if __name__ == "__main__":
    main()
