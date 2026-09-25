"""Source-grounded learning activities for the Class 9 tutor."""

import re
from collections.abc import Iterable


MODES = ("mixed", "flashcards", "mcq", "short_answer", "teach_back")


def _sentences(text: str) -> list[str]:
    candidates = [
        sentence.strip(" -")
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if len(sentence.strip()) >= 35
    ]
    return [
        sentence for sentence in candidates
        if not re.match(r"^\d+\s", sentence)
        and "fig." not in sentence.lower()
        and "table." not in sentence.lower()
    ]


def _trim(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3].rsplit(" ", 1)[0] + "..."


def _keywords(text: str, limit: int = 6) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text.lower())
    ignored = {
        "about", "after", "also", "because", "being", "between", "from",
        "have", "into", "more", "other", "such", "than", "that", "their",
        "these", "this", "through", "which", "with", "would", "your",
        "also", "some", "them", "during", "from", "into", "using",
    }
    result = []
    for word in words:
        if word not in ignored and word not in result:
            result.append(word)
        if len(result) == limit:
            break
    return result


def _source(item: dict) -> dict:
    return {key: item.get(key) for key in ("subject", "chapter", "source_file", "page")}


def _normalise_mode(mode: str | None) -> str:
    mode = (mode or "mixed").strip().lower().replace("-", "_")
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    return mode


def build_practice_set(passages: Iterable[dict], mode: str = "mixed", count: int = 5) -> dict:
    """Build varied activities from retrieved passages without adding facts."""
    mode = _normalise_mode(mode)
    usable = []
    for passage in passages:
        sentences = _sentences(passage.get("text", ""))
        if sentences:
            usable.append((passage, max(sentences, key=len)))
    if not usable:
        return {"mode": mode, "items": [], "message": "No study material found for this topic."}

    count = max(1, min(int(count), 10))
    items = []
    for index in range(min(count, len(usable))):
        passage, key_sentence = usable[index]
        selected_mode = mode if mode != "mixed" else MODES[1 + index % (len(MODES) - 1)]
        item = {"id": index + 1, "type": selected_mode, "source": _source(passage)}
        if selected_mode == "flashcards":
            item.update({
                "prompt": "What is the main idea of this passage? Explain it in your own words.",
                "answer": _trim(key_sentence), "keywords": _keywords(key_sentence),
            })
        elif selected_mode == "mcq":
            choices = [_trim(key_sentence, 160)]
            for other_index, (_, other_sentence) in enumerate(usable):
                if other_index != index and len(choices) < 4:
                    choices.append(_trim(other_sentence, 160))
            item.update({
                "prompt": "Which statement best matches this study topic?",
                "choices": choices, "answer_index": 0, "explanation": _trim(key_sentence),
            })
        elif selected_mode == "short_answer":
            item.update({
                "prompt": "Write 1-2 sentences explaining one important idea from the passage.",
                "answer": _trim(key_sentence), "keywords": _keywords(key_sentence),
            })
        else:
            item.update({
                "prompt": "Teach this idea to a classmate without copying the textbook wording.",
                "answer": _trim(key_sentence), "keywords": _keywords(key_sentence),
            })
        items.append(item)
    return {"mode": mode, "items": items}


def evaluate_answer(activity: dict, response: str) -> dict:
    """Score one activity using exact choice or keyword coverage."""
    response = (response or "").strip()
    if not response:
        return {"correct": False, "score": 0, "feedback": "Write an answer before checking."}
    if activity.get("type") == "mcq":
        try:
            selected = int(response) - 1
        except ValueError:
            selected = -1
        correct = selected == activity.get("answer_index")
        return {
            "correct": correct, "score": 100 if correct else 0,
            "feedback": "Correct. Check the source explanation." if correct else "Not quite. Re-read the source passage and try again.",
            "explanation": activity.get("explanation", ""),
        }

    keywords = activity.get("keywords", [])
    matched = [word for word in keywords if re.search(rf"\b{re.escape(word)}\b", response.lower())]
    score = round(100 * len(matched) / len(keywords)) if keywords else 0
    return {
        "correct": score >= 50, "score": score, "matched_keywords": matched,
        "feedback": "Good explanation. Add one more textbook idea if you can." if score >= 50 else "Try again using the key terms from the source passage.",
        "model_answer": activity.get("answer", ""),
    }