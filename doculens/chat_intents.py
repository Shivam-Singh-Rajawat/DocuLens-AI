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


# User questions about the library's inventory must consult document metadata,
# not the embedding index (especially when the requested format is absent).
FILE_TYPE_NAMES = {
    "ppt": ("ppt", "pptx"), "pdf": ("pdf",),
    "word": ("docx",), "text": ("txt", "text", "md", "markdown"),
}
FILE_LABELS = {
    "ppt": "PowerPoint presentations (PPT/PPTX)",
    "pdf": "PDF documents",
    "word": "Word documents",
    "text": "text documents",
}


def library_inventory_kind(question: str) -> str | None:
    q = re.sub(r"\s+", " ", question.casefold()).strip()
    is_library = bool(re.search(
        r"\b(my|our|uploaded|upload|uploads|library|files?|sources?|documents?|collection)\b", q))
    is_listing = bool(re.search(
        r"\b(what|which|list|show|how many|any|available|present|have|contain|inside|in)\b", q))
    if not (is_library and is_listing):
        return None
    if re.search(r"\b(ppt|pptx|powerpoint|slides?|presentations?)\b", q):
        return "ppt"
    if re.search(r"\b(pdfs?|pdf files?)\b", q):
        return "pdf"
    if re.search(r"\b(docx|word files?)\b", q):
        return "word"
    if re.search(r"\b(txt|text files?|markdown)\b", q):
        return "text"
    if re.search(r"\b(common|similarities?|overlap|compare|differences?)\b", q):
        return None
    # Generic inventory requests need a file-listing structure; the word
    # "library" by itself is not a listing intent ("what does this library use").
    if re.search(r"^\s*(?:please\s+)?(?:list|show|display|enumerate)\b", q) and re.search(
        r"\b(files?|documents?|sources?|uploads?|library|collection)\b", q
    ):
        return "all"
    if (re.search(r"\b(what|which|how many)\b", q)
            and re.search(r"\b(files?|documents?|sources?|uploads?)\b", q)
            and re.search(r"\b(my|our|have|uploaded|in|available|present)\b", q)):
        return "all"
    return None


def is_commonality_question(question: str, mode: str = "qa") -> bool:
    q = question.casefold()
    if mode == "compare":
        return True
    return bool(
        re.search(r"\b(common|similarities|similarity|overlap|shared|compare|differences?)\b", q)
        and re.search(r"\b(files?|documents?|sources?|pdfs?|papers?|notes?|them|these|both)\b", q)
    )
