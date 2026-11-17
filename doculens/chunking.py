"""Page-preserving, overlap-aware document chunking."""
import re


def chunk_pages(pages: list[dict], source_id: str, *, chunk_size: int = 900, overlap: int = 150) -> list[dict]:
    if chunk_size < 10 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be >=10 and overlap must be >=0 and smaller than chunk_size")
    result = []
    for page_record in pages:
        page = int(page_record.get("page", 1))
        text = re.sub(r"[ \t]+", " ", str(page_record.get("text", "")))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            continue
        start, index = 0, 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                possible_break = max(text.rfind(" ", start + chunk_size // 2, end),
                                     text.rfind("\n", start + chunk_size // 2, end))
                if possible_break > start:
                    end = possible_break
            snippet = text[start:end].strip()
            if snippet:
                result.append({"id": f"{source_id}:p{page}:c{index}",
                               "source_id": source_id, "page": page,
                               "text": snippet, "start": start, "end": end})
                index += 1
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return result
