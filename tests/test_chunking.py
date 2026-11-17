from doculens.chunking import chunk_pages


def test_chunk_pages_preserves_page_numbers_and_overlap():
    pages = [{"page": 1, "text": "alpha beta gamma delta epsilon zeta eta theta iota"},
             {"page": 2, "text": "paper two has a different result"}]
    chunks = chunk_pages(pages, "doc-1", chunk_size=24, overlap=8)
    assert len(chunks) >= 3
    assert all(ch["source_id"] == "doc-1" for ch in chunks)
    assert set(ch["page"] for ch in chunks) == {1, 2}
    assert [ch["page"] for ch in chunks] == sorted(ch["page"] for ch in chunks)
    assert not any("paper two" in ch["text"] for ch in chunks if ch["page"] == 1)
    assert len({ch["id"] for ch in chunks}) == len(chunks)
    assert "alpha" in chunks[0]["text"]


def test_chunk_pages_rejects_invalid_overlap():
    import pytest
    with pytest.raises(ValueError, match="overlap"):
        chunk_pages([{"page":1, "text":"hello"}], "doc", chunk_size=20, overlap=20)
