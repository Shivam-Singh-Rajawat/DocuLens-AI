import io
import fitz
import pytest
from docx import Document
from doculens.ingestion import extract_pages, text_pages, validate_public_url


def make_pdf():
    document = fitz.open()
    document.new_page().insert_text((60, 80), "Page one: retrieval augmented generation")
    document.new_page().insert_text((60, 80), "Page two: citation traceability and evidence")
    result = document.tobytes()
    document.close()
    return result


def test_pdf_preserves_true_page_numbers():
    pages = extract_pages(make_pdf(), "paper.pdf")
    assert len(pages) == 2
    assert pages[0]["page"] == 1 and "retrieval" in pages[0]["text"]
    assert pages[1]["page"] == 2 and "citation" in pages[1]["text"]


def test_docx_extracts_paragraphs_and_tables():
    doc = Document()
    doc.add_paragraph("The experiment uses cosine similarity")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "R2", "0.89"
    stream = io.BytesIO()
    doc.save(stream)
    contents = extract_pages(stream.getvalue(), "research.docx")[0]["text"]
    assert "cosine similarity" in contents and "R2 | 0.89" in contents


def test_text_formats_and_rejections():
    assert "Important" in extract_pages(b"<html><body><script>ignoreme</script><p>Important</p></body></html>","a.html")[0]["text"]
    assert "ignoreme" not in extract_pages(b"<script>ignoreme</script>Important","a.html")[0]["text"]
    assert "key" in extract_pages(b'{"key": 9}',"a.json")[0]["text"]
    assert "name | age" in extract_pages(b"name,age\nBob,24", "a.csv")[0]["text"]
    with pytest.raises(ValueError, match="Unsupported"):
        extract_pages(b"binary", "app.exe")
    with pytest.raises(ValueError, match="empty"):
        text_pages("  ")


def test_private_url_is_blocked():
    with pytest.raises(ValueError, match="Local, private"):
        validate_public_url("http://127.0.0.1/admin")
    with pytest.raises(ValueError, match="public HTTP"):
        validate_public_url("file:///etc/passwd")
