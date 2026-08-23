"""Interactive local chat client for the CBSE Class 9 knowledge base."""

import json
import os

from dotenv import load_dotenv
from server import get_generation_client, search_content

load_dotenv(override=True)


def ask_model(client, question: str, subject: str | None, passages: list[dict]) -> str:
    context = "\n\n".join(
        f"Source: {item['source_file']}, page {item['page']}\n{item['text']}"
        for item in passages
    )
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "qwen2.5:7b")),
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful CBSE Class 9 tutor. Answer using the "
                    "provided textbook passages. Solve step by step, check "
                    "calculations, distinguish inference from textbook facts, "
                    "and cite source files and pages. Do not copy the passage."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Subject: {subject or 'Any'}\nQuestion: {question}\n\n"
                    f"Textbook passages:\n{context}"
                ),
            },
        ],
    )
    return response.choices[0].message.content or "No answer returned."


def main() -> None:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    client = None
    if not provider:
        print("Retrieval-only mode: no LLM configured.")
    elif provider != "ollama" and (
        not os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY", "").startswith("replace_with_")
    ):
        print("OPENAI_API_KEY is not set. Use retrieval-only mode or set LLM_PROVIDER=ollama.")
    else:
        client = get_generation_client()
    print("CBSE Class 9 local chat")
    print("Commands: /subject <name>, /clear, /quit")
    subject = None

    while True:
        try:
            question = input(f"\nYou [{subject or 'all subjects'}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in {"/quit", "/exit", "quit", "exit"}:
            break
        if question.lower() == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if question.lower().startswith("/subject "):
            subject = question[9:].strip() or None
            print(f"Subject filter: {subject or 'all subjects'}")
            continue

        try:
            passages = search_content(question, subject=subject, top_k=6)
            if not passages:
                print("No matching textbook passages found.")
                continue
            if client:
                print("\nAssistant:\n" + ask_model(client, question, subject, passages))
            else:
                print("\nRetrieved textbook passages:\n")
                for item in passages:
                    print(f"[{item['source_file']}, page {item['page']}]\n{item['text']}\n")
        except Exception as error:
            print(f"\nError: {error}")


if __name__ == "__main__":
    main()