"""Extract text with stable PDF page numbers, and safely fetch public web pages."""
import csv
import io
import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import fitz
import requests
from docx import Document

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".csv", ".json"}
MAX_TEXT_CHARS = 2_000_000


def extract_pages(data: bytes, filename: str, *, ocr: bool = False) -> list[dict]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or '(none)'}. Use PDF, DOCX, TXT, MD, HTML, CSV, or JSON.")
    if not data:
        raise ValueError("The uploaded document is empty.")
    if suffix == ".pdf":
        try:
            with fitz.open(stream=data, filetype="pdf") as document:
                if document.needs_pass:
                    raise ValueError("Password-protected PDFs aren't supported. Unlock the PDF before uploading.")
                pages = []
                for number, page in enumerate(document, 1):
                    text = page.get_text(sort=True).strip()
                    if not text and ocr:
                        try:
                            import pytesseract
                            from PIL import Image
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                            text = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png")))).strip()
                        except (ImportError, RuntimeError, OSError) as exc:
                            raise ValueError("OCR requires pytesseract and the Tesseract executable.") from exc
                    pages.append({"page": number, "text": text})
        except (fitz.FileDataError, fitz.EmptyFileError) as exc:
            raise ValueError("The PDF is invalid or cannot be opened.") from exc
    elif suffix == ".docx":
        try:
            doc = Document(io.BytesIO(data))
        except Exception as exc:
            raise ValueError("Could not read the DOCX file.") from exc
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                paras.append(" | ".join(cell.text.strip() for cell in row.cells))
        pages = [{"page": 1, "text": "\n".join(paras)}]
    else:
        try:
            raw = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text files must be UTF-8 encoded.") from exc
        if suffix in {".html", ".htm"}:
            soup = BeautifulSoup(raw, "html.parser")
            for node in soup(["script", "style", "nav", "footer", "noscript"]):
                node.decompose()
            raw = soup.get_text("\n", strip=True)
        elif suffix == ".json":
            try:
                raw = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSON document.") from exc
        elif suffix == ".csv":
            rows = list(csv.reader(io.StringIO(raw)))
            raw = "\n".join(" | ".join(row) for row in rows)
        pages = [{"page": 1, "text": raw}]
    count = sum(len(p["text"]) for p in pages)
    if count > MAX_TEXT_CHARS:
        raise ValueError("Document exceeds the extracted-text limit of 2 million characters.")
    if not any(p["text"].strip() for p in pages):
        raise ValueError("No extractable text was found. For scanned PDFs enable OCR and install Tesseract.")
    return pages


def text_pages(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        raise ValueError("Text content cannot be empty.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("Text exceeds the 2 million character limit.")
    return [{"page": 1, "text": text}]


def validate_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Provide a public HTTP or HTTPS URL without credentials.")
    if len(url) > 2048:
        raise ValueError("URL is too long.")
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise ValueError("URL hostname could not be resolved.") from exc
    if not addresses:
        raise ValueError("No IP address found for URL.")
    for item in addresses:
        try:
            address = ipaddress.ip_address(item[4][0])
        except ValueError as exc:
            raise ValueError("Invalid URL network address.") from exc
        if not address.is_global:
            raise ValueError("Local, private and reserved network addresses are not allowed.")


def fetch_public_url(url: str, *, max_bytes: int = 20 * 1024 * 1024) -> tuple[bytes, str, str]:
    """Best-effort SSRF protections; do not expose without an authenticated reverse proxy."""
    current = url
    for _ in range(4):
        validate_public_url(current)
        try:
            response = requests.get(current, timeout=(5, 20), stream=True, allow_redirects=False,
                                    headers={"User-Agent": "DocuLensAI/1.0 (research assistant)"})
            if response.status_code in {301, 302, 303, 307, 308}:
                next_url = response.headers.get("Location", "")
                response.close()
                if not next_url:
                    raise ValueError("Redirect missing location.")
                current = urljoin(current, next_url)
                continue
            response.raise_for_status()
            mime = response.headers.get("Content-Type", "").split(";")[0].lower().strip()
            if mime not in {"text/html", "text/plain", "application/pdf", "text/markdown", "application/json", "text/csv"}:
                response.close()
                raise ValueError(f"Web content type {mime or 'unknown'} isn't supported.")
            data = bytearray()
            for block in response.iter_content(chunk_size=65536):
                data.extend(block)
                if len(data) > max_bytes:
                    raise ValueError("Web resource exceeds upload limit.")
            response.close()
            ext = {"application/pdf": ".pdf", "text/plain": ".txt", "text/markdown": ".md",
                   "application/json": ".json", "text/csv": ".csv"}.get(mime, ".html")
            title = urlsplit(current).hostname or "website"
            if ext == ".html":
                soup = BeautifulSoup(bytes(data), "html.parser")
                if soup.title and soup.title.string:
                    title = re.sub(r"[^\w\s.-]", "", soup.title.string).strip()[:90] or title
            return bytes(data), f"{title}{ext}", current
        except requests.RequestException as exc:
            raise ValueError(f"Could not fetch web URL: {type(exc).__name__}") from exc
    raise ValueError("Too many URL redirects.")
