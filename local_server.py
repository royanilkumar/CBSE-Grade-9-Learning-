"""Run the CBSE tutor as a small local HTTP API."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from dotenv import load_dotenv
from server import get_backend_status, get_generation_client, list_chapters, search_content

load_dotenv(override=True)

PDF_DIR = Path(__file__).parent / "data" / "pdfs"


def answer_question(question: str, subject: str | None) -> dict:
    if "chapter" in question.lower():
        chapters = list_chapters(subject)
        return {
            "answer": "Indexed chapters:\n" + "\n".join(f"- {chapter}" for chapter in chapters),
            "sources": [],
        }

    passages = search_content(question, subject=subject, top_k=6)
    if not passages:
        return {"answer": "No matching textbook passages found.", "sources": []}

    if not os.getenv("LLM_PROVIDER", "").strip():
        return {
            "answer": "Retrieved textbook passages:\n\n"
            + "\n\n".join(
                f"{item['source_file']} (page {item['page']})\n{item['text']}"
                for item in passages
            ),
            "sources": [
                {
                    "subject": item["subject"],
                    "source_file": item["source_file"],
                    "page": item["page"],
                    "url": f"/pdf/{quote(item['source_file'])}#page={item['page']}",
                }
                for item in passages
            ],
        }

    client = get_generation_client()

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
                    "provided textbook passages. Solve step by step, check the "
                    "answer, explain your reasoning, and cite the source file "
                    "and page. Do not copy the passage."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\nSubject: {subject or 'Any'}\n\n{context}",
            },
        ],
    )
    return {
        "answer": response.choices[0].message.content or "No answer returned.",
        "sources": [
            {
                "subject": item["subject"],
                "source_file": item["source_file"],
                "page": item["page"],
                "url": f"/pdf/{quote(item['source_file'])}#page={item['page']}",
            }
            for item in passages
        ],
    }


class RequestHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            body = (Path(__file__).with_name("chat.html")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/health":
            self.send_json(200, get_backend_status())
            return
        if self.path == "/chapters":
            self.send_json(200, {"chapters": list_chapters()})
            return
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith("/pdf/"):
            filename = Path(unquote(parsed_path.path[len("/pdf/"):])).name
            matches = list(PDF_DIR.rglob(filename))
            if len(matches) != 1:
                self.send_json(404, {"error": "PDF source not found"})
                return
            body = matches[0].read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json(404, {"error": "Use GET /health or POST /chat"})

    def do_POST(self) -> None:
        if self.path != "/chat":
            self.send_json(404, {"error": "Use POST /chat"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get("question", "")).strip()
            subject = payload.get("subject")
            if not question:
                self.send_json(400, {"error": "question is required"})
                return
            self.send_json(200, answer_question(question, subject))
        except Exception as error:
            self.send_json(500, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[local-server] {format % args}")


def main() -> None:
    host = os.getenv("CBSE_HOST", "127.0.0.1")
    port = int(os.getenv("CBSE_PORT", "8000"))
    httpd = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"CBSE tutor listening at http://{host}:{port}")
    print("Endpoints: GET /health, POST /chat")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()