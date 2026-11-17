"""Lightweight intents that complement, rather than replace, semantic RAG.

Exact word search must not depend on embeddings or stop-word filtering.
"""
import re
from pathlib import Path

from doculens.ingestion import extract_pages


def exact_search_term(question: str) -> str | None:
    match = re.match(
        r"^\s*(?:please\s+)?(?:find|locate|search(?:\s+for)?|look\s+for|count)\s+"
        r"(?:(?:all\s+)?occurrences\s+of\s+)?(?:(?:the|an?|this)\s+)?"
        r"(?:exact\s+)?(?:word|term|phrase)\s+(.+?)\s*[?!.]*$",
        question, flags=re.I,
    )
    if not match:
        return None
    phrase = re.sub(
        r"\s+in\s+(?:this|the)(?:\s+(?:pdf|document|file|text))?\s*$",
        "", match.group(1), flags=re.I
    ).strip().strip("'\"“”‘’").strip()
    return phrase if 1 <= len(phrase) <= 100 and len(phrase.split()) <= 8 else None


def is_greeting(question: str) -> bool:
    return bool(re.fullmatch(
        r"\s*(?:hi|hello|hey|hey there|good (?:morning|evening|afternoon)|thanks|thank you)[\s!?.]*",
        question, flags=re.I
    ))


def is_vague_document_question(question: str) -> bool:
    return bool(re.fullmatch(
        r"\s*(?:(?:what|tell me)\s+(?:is|about)\s+)?"
        r"(?:(?:this|the)\s+)?(?:pdf|file|document|paper)(?:\s+about)?[\s!?.]*"
        r"|\s*(?:what\s+is\s+(?:this|the)\s+(?:pdf|document|file)\s+about|"
        r"tell\s+me\s+about\s+(?:this|the)(?:\s+pdf)?|"
        r"explain\s+(?:this|the)(?:\s+(?:pdf|document|file))?|"
        r"summarize\s+(?:this|the)(?:\s+(?:pdf|document|file))?)[\s!?.]*",
        question, flags=re.I
    ))


def exact_word_counts(term: str, documents: list[dict], chunks: list[dict]):
    """Count exact matches by file page, using original content where available.

    If no original is stored (pasted text), dedupe overlapping chunk offsets.
    """
    pattern = re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, term.split())) + r"(?!\w)", re.I)
    grouped = {}
    for chunk in chunks:
        key = (chunk["source_id"], int(chunk.get("page", 1)))
        start = int(chunk.get("start", 0))
        grouped.setdefault(key, set()).update(
            start + occurrence.start() for occurrence in pattern.finditer(chunk["text"])
        )
    counts = {}
    for doc in documents:
        original = doc.get("file_path")
        if original and Path(original).is_file():
            try:
                pages = extract_pages(Path(original).read_bytes(), doc["name"])
                for page in pages:
                    count = len(pattern.findall(page["text"]))
                    if count:
                        counts[(doc["id"], int(page["page"]))] = count
                continue
            except (ValueError, OSError):
                pass
        for (doc_id,page), offsets in grouped.items():
            if doc_id == doc["id"] and offsets:
                counts[(doc_id,page)] = len(offsets)
    return counts
