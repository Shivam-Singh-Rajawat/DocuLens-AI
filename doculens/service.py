"""Application operations; can be exercised without starting the web server."""
import hashlib
import re
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from doculens.chunking import chunk_pages
from doculens.chat_intents import (exact_search_term, exact_word_counts, is_greeting,
                                  is_vague_document_question, library_inventory_kind,
                                  is_commonality_question, FILE_TYPE_NAMES, FILE_LABELS)
from doculens.database import DocumentDB, utcnow
from doculens.postgres_store import PostgresDocumentDB
from doculens.embeddings import HashEmbeddings, SentenceEmbeddings
from doculens.ingestion import extract_pages, fetch_public_url, text_pages
from doculens.llm import generate, generate_general, PROMPT_MODES
from doculens.retrieval import HybridRetriever
from doculens.settings import Settings
from doculens.vectorstore import ChromaStore, MemoryStore, SQLiteVectorStore


class RAGService:
    def __init__(self, settings: Settings | None = None, *, embedder=None, store=None):
        self.settings = settings or Settings()
        if self.settings.metadata_backend == "postgres":
            self.db = PostgresDocumentDB(self.settings.database_url)
        elif self.settings.metadata_backend == "sqlite":
            self.db = DocumentDB(self.settings.data_dir / "metadata.sqlite3")
        else:
            raise ValueError("METADATA_BACKEND must be sqlite or postgres")
        self.embedder = embedder or (HashEmbeddings() if self.settings.embedding_backend == "hash"
                                     else SentenceEmbeddings(self.settings.embedding_model))
        if store is None:
            if self.settings.vector_backend == "chroma":
                store = ChromaStore(self.settings.data_dir / "chroma")
            elif self.settings.vector_backend == "sqlite":
                store = SQLiteVectorStore(self.settings.data_dir / "vectors")
            elif self.settings.vector_backend == "memory":
                store = MemoryStore()
            else:
                raise ValueError("VECTOR_BACKEND must be chroma, sqlite or memory")
        self.store = store
        self.retriever = HybridRetriever(self.embedder, self.store,
                                         reranker_model=self.settings.reranker_model,
                                         enable_reranker=self.settings.enable_reranker)

    def ingest_file(self, name: str, data: bytes, *, origin: str | None = None) -> dict:
        if len(data) > self.settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"Upload exceeds {self.settings.max_upload_mb} MB limit.")
        name = Path(name.replace("\\", "/")).name.strip()[:150] or "untitled.txt"
        suffix = Path(name).suffix.lower()
        pages = extract_pages(data, name, ocr=self.settings.enable_ocr)
        kind = suffix.lstrip(".")
        return self._save(name, kind, data, pages, origin=origin, save_file=origin is None)

    def ingest_text(self, name: str, text: str) -> dict:
        name = name.strip()[:150] or "Pasted notes"
        return self._save(name, "text", text.encode("utf-8"), text_pages(text), save_file=False)

    def ingest_url(self, url: str) -> dict:
        data,name,canonical_url = fetch_public_url(url, max_bytes=self.settings.max_upload_mb*1024*1024)
        return self.ingest_file(name, data, origin=canonical_url)

    def _save(self, name: str, kind: str, raw: bytes, pages: list[dict], *, origin=None, save_file=False) -> dict:
        digest = hashlib.sha256(raw).hexdigest()
        existing = self.db.duplicate(digest, kind)
        if existing:
            return {**existing,"duplicate":True}
        source_id = uuid4().hex
        chunks = chunk_pages(pages, source_id,
                             chunk_size=self.settings.chunk_size,
                             overlap=self.settings.chunk_overlap)
        if not chunks:
            raise ValueError("No valid text chunks were extracted.")
        for chunk in chunks:
            chunk.update({"source_name": name, "kind":kind})
        vectors = self.embedder.encode([c["text"] for c in chunks])
        target = None
        entry = {"id":source_id,"name":name,"kind":kind,"digest":digest,
                 "origin":origin,"pages":len(pages),"chunks":len(chunks),
                 "file_path":None,"created_at":utcnow()}
        try:
            self.store.add(chunks, vectors)
            if save_file:
                suffix = Path(name).suffix.lower() or ".txt"
                directory = self.settings.data_dir / "uploads"
                directory.mkdir(exist_ok=True,parents=True)
                target = directory / f"{source_id}{suffix}"
                target.write_bytes(raw)
                entry["file_path"] = str(target)
            self.db.add_document(entry)
        except Exception:
            self.store.delete(source_id)
            if target:
                target.unlink(missing_ok=True)
            raise
        return {**entry,"duplicate":False}

    def list_documents(self):
        return self.db.documents()

    def delete_document(self, document_id: str):
        record = self.db.document(document_id)
        if not record:
            return False
        self.store.delete(document_id)
        self.db.remove_document(document_id)
        if record["file_path"]:
            Path(record["file_path"]).unlink(missing_ok=True)
        return True

    def _check_ids(self, source_ids: list[str] | None):
        if source_ids:
            missing = [id_ for id_ in source_ids if not self.db.document(id_)]
            if missing:
                raise ValueError("Unknown document ID: " + missing[0])

    def search(self, question: str, *, source_ids=None, top_k: int | None = None, rerank=True) -> dict:
        self._check_ids(source_ids)
        if len(question) > 4000:
            raise ValueError("Questions may contain at most 4,000 characters.")
        start = perf_counter()
        hits, warnings, reranked = self.retriever.retrieve(question, source_ids=source_ids,
                                top_k=top_k or self.settings.top_k, rerank=rerank)
        return {"hits":hits,"warnings":warnings,"reranked":reranked,
                "latency_ms":round((perf_counter()-start)*1000, 1),"total_chunks":self.store.count()}

    def _exact_search(self, question: str, term: str, source_ids: list[str] | None, session_id: str) -> dict:
        self._check_ids(source_ids)
        selected = [d for d in self.db.documents()
                    if not source_ids or d["id"] in source_ids]
        counts = exact_word_counts(term, selected, self.store.all_chunks(source_ids))
        total = sum(counts.values())
        docs_by_id = {d["id"]: d for d in selected}
        sources = []
        lines = [f"Found **{total} occurrences** of the exact word or phrase **{term}** "
                 f"in {len(selected)} selected document(s)."]
        for (doc_id, page), count in sorted(
                counts.items(), key=lambda item: (docs_by_id[item[0][0]]["name"].lower(), item[0][1])):
            doc = docs_by_id[doc_id]
            if len(sources) >= 12:
                continue
            number = len(sources) + 1
            page_label = f"Page {page}" if doc["kind"] == "pdf" else "Text"
            lines.append(f"- **{doc['name']}**, {page_label}: **{count}** occurrence(s) [{number}]")
            sources.append({
                "number": number, "source_id": doc_id, "source_name": doc["name"],
                "page": page if doc["kind"] == "pdf" else None,
                "kind": doc["kind"], "chunk_id": f"{doc_id}:p{page}",
                "origin": doc.get("origin"), "has_file": bool(doc.get("file_path")),
                "excerpt": f"Exact search for {term!r} on page {page}: {count} occurrence(s).",
                "semantic_score": 0.0, "rerank_score": None,
            })
        if len(counts) > len(sources):
            lines.append(f"Additional matching pages: {len(counts)-len(sources)} (not shown).")
        if not selected:
            lines.append("Attach or select a document to search.")
        answer = "\n".join(lines)
        self.db.message(session_id, "user", question)
        self.db.message(session_id, "assistant", answer)
        return {"session_id": session_id, "question": question, "answer": answer,
                "sources": sources, "provider": "document-search", "reranked": False,
                "warnings": [], "retrieval_ms": 0}

    def _library_answer(self, question: str, kind: str, source_ids: list[str] | None,
                        session_id: str) -> dict:
        """Answer file inventory questions from PostgreSQL, not low-similarity chunks."""
        self._check_ids(source_ids)
        documents = [d for d in self.db.documents() if not source_ids or d["id"] in source_ids]
        if kind == "all":
            matching = documents
            heading = f"**{len(matching)} uploaded source(s)** in the selected library:"
        else:
            matching = [d for d in documents if d["kind"].lower() in FILE_TYPE_NAMES[kind]]
            heading = (f"**{len(matching)} {FILE_LABELS[kind]}** in the selected sources:"
                       if matching else
                       f"No {FILE_LABELS[kind]} are uploaded in the selected sources.")
        rows = [heading]
        for d in matching[:30]:
            rows.append(f"- **{d['name']}** ({d['kind'].upper()}, {d['pages']} page(s))")
        if len(matching) > 30:
            rows.append(f"...and {len(matching) - 30} additional source(s).")
        if not matching and documents and kind != "all":
            rows.append(
                "\n**Available sources:** " +
                ", ".join(f"{d['name']} ({d['kind'].upper()})" for d in documents[:15])
            )
        if kind == "ppt" and not matching:
            rows.append(
                "\nDocuLens currently accepts PDFs, DOCX and text formats; "
                "convert a PowerPoint to PDF before uploading it."
            )
        if not documents:
            rows.append("Attach a document or select sources in the sidebar.")
        if re.search(r"\b(common|similar|overlap)\b", question, re.I):
            rows.append(
                "\nTo compare shared topics, ask **What do the selected documents have "
                "in common?** (that compares their content instead of just listing files)."
            )
        answer = "\n".join(rows)
        self.db.message(session_id, "user", question)
        self.db.message(session_id, "assistant", answer)
        return {"session_id": session_id, "question": question, "answer": answer,
                "sources": [], "provider": "library", "reranked": False,
                "warnings": [], "retrieval_ms": 0}

    def _balanced_comparison(self, source_ids: list[str] | None,
                             top_k: int | None = None) -> tuple[list[dict], list[str]]:
        """Include representative evidence from each selected source for commonality tasks.

        A vague 'what do these have in common' query has almost no lexical
        discriminators; normal global top-K can silently exclude entire documents.
        """
        self._check_ids(source_ids)
        selected = [d for d in self.db.documents() if not source_ids or d["id"] in source_ids]
        warnings = []
        if len(selected) > 8:
            warnings.append("Comparison uses the first 8 sources; narrow your selection to compare more precisely.")
            selected = selected[:8]
        selected_ids = [d["id"] for d in selected]
        if not selected_ids:
            return [], warnings
        groups: dict[str, list[dict]] = {doc_id: [] for doc_id in selected_ids}
        for chunk in self.store.all_chunks(selected_ids):
            if chunk["source_id"] in groups:
                groups[chunk["source_id"]].append(chunk)
        evidence = []
        for doc in selected:
            chunks = sorted(groups[doc["id"]], key=lambda c: (int(c.get("page", 1)),
                                                               int(c.get("start", 0))))
            if chunks:
                evidence.append({**chunks[0], "semantic_score": 0.0,
                                 "selection_method": "document-overview"})
        return evidence, warnings

    def chat(self, question: str, *, session_id: str | None = None, source_ids=None,
             top_k: int | None = None, rerank=True, mode="qa", custom_instructions="") -> dict:
        if not question.strip():
            raise ValueError("Question cannot be empty.")
        if mode not in PROMPT_MODES:
            raise ValueError("Unknown prompt mode.")
        if len(custom_instructions) > 1200:
            raise ValueError("Custom prompt instructions exceed 1,200 characters.")
        session_id = session_id or uuid4().hex
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", session_id):
            raise ValueError("Invalid session ID.")
        history = self.db.history(session_id, limit=10)
        if mode == "chat":
            answer, provider = generate_general(
                question, history, self.settings, custom_instructions)
            self.db.message(session_id, "user", question)
            self.db.message(session_id, "assistant", answer)
            return {"session_id": session_id, "question": question, "answer": answer,
                    "sources": [], "provider": provider, "reranked": False,
                    "warnings": [], "retrieval_ms": 0}
        if is_greeting(question):
            answer = ("Hello! Attach a PDF and ask about its contents, or select "
                      "**General chat** to ask questions without a document.")
            self.db.message(session_id, "user", question)
            self.db.message(session_id, "assistant", answer)
            return {"session_id": session_id, "question": question, "answer": answer,
                    "sources": [], "provider": "assistant", "reranked": False,
                    "warnings": [], "retrieval_ms": 0}
        term = exact_search_term(question)
        if term:
            return self._exact_search(question, term, source_ids, session_id)
        kind = library_inventory_kind(question)
        if kind:
            return self._library_answer(question, kind, source_ids, session_id)
        comparison = (is_commonality_question(question, mode) and
                      len(source_ids or self.db.documents()) >= 2)
        retrieval_query = (
            "Explain the main topic, purpose, key points, conclusion and limitations "
            "of the selected document."
            if source_ids and is_vague_document_question(question) else question
        )
        if retrieval_query == question and history and len(question) < 110 and re.search(r"\b(it|its|they|them|their|that|those|this|these)\b", question, re.I):
            last_questions = [item["content"] for item in history if item["role"] == "user"]
            if last_questions:
                retrieval_query = last_questions[-1][:450] + " " + question
        if comparison:
            started = perf_counter()
            hits, warnings = self._balanced_comparison(source_ids, top_k)
            search = {"hits": hits, "warnings": warnings, "reranked": False,
                      "latency_ms": round((perf_counter() - started) * 1000, 1)}
            credible = bool(hits)
        else:
            search = self.search(retrieval_query, source_ids=source_ids, top_k=top_k,rerank=rerank)
            hits = search["hits"]
            credible = any(h.get("semantic_score",0) >= self.settings.min_similarity or
                           h.get("bm25_score",0) > 0 for h in hits)
        if not credible:
            answer, provider = "I couldn't find that information in the selected sources.", "none"
            hits = []
        else:
            model_question = question
            if comparison:
                model_question = (
                    question + "\nUse evidence from EACH document separately. "
                    "Identify shared themes only where at least two documents support them. "
                    "If no topic is common to every document, say that clearly. "
                    "Cite each source where relevant; don't assume all documents agree."
                )
            answer, provider = generate(model_question, hits, history, settings=self.settings,
                                        mode="compare" if comparison else mode,
                                        custom_instructions=custom_instructions)
            # An abstention must not be followed by unrelated source references.
            if re.match(r"^\s*(?:sorry[,!\. ]*)?i\s+(?:couldn't|could not|cannot|can't)\s+find\b",
                        answer, re.I):
                hits = []
        documents_by_id = {h["source_id"]:self.db.document(h["source_id"]) or {} for h in hits}
        sources = [{"number":i,"source_id":h["source_id"],"source_name":h["source_name"],
                    "page":h["page"] if h.get("kind") == "pdf" else None,
                    "kind":h.get("kind", "text"),"chunk_id":h["id"],
                    "origin":documents_by_id[h["source_id"]].get("origin"),
                    "has_file":bool(documents_by_id[h["source_id"]].get("file_path")),
                    "excerpt":h["text"][:850],
                    "semantic_score":round(h.get("semantic_score",0),3),
                    "selection_method":h.get("selection_method","retrieval"),
                    "rerank_score":round(h["rerank_score"],3) if "rerank_score" in h else None}
                   for i,h in enumerate(hits,1)]
        # An LLM-generated [99] must never be presented as a valid source marker.
        allowed = set(range(1,len(sources)+1))
        answer = re.sub(r"(?<!\[)\[(\d+)\](?!\])",
                        lambda m:m.group() if int(m.group(1)) in allowed else "[unverified citation]",answer)
        # Models occasionally omit citation markers. Expose the retrieved evidence
        # without falsely claiming that we verified each generated factual claim.
        if hits and provider in {"gemini", "ollama"} and not any(
                f"[{number}]" in answer for number in allowed):
            markers = ", ".join(f"[{number}]" for number in sorted(allowed))
            answer += (
                "\n\n**Retrieved source excerpts (not independently verified):** "
                + markers
            )
        self.db.message(session_id,"user",question)
        self.db.message(session_id,"assistant",answer)
        return {"session_id":session_id,"question":question,"answer":answer,"sources":sources,
                "provider":provider,"reranked":search["reranked"],
                "warnings":search["warnings"],"retrieval_ms":search["latency_ms"]}

    def evaluate(self, cases: list[dict], top_k=5, rerank=False):
        if not cases or len(cases) > 100:
            raise ValueError("Provide between 1 and 100 evaluation cases.")
        rows = []
        for case in cases:
            expected = set(case.get("expected_source_ids",[]))
            if not expected:
                raise ValueError("Every case needs at least one expected_source_id.")
            result = self.search(case["question"],top_k=top_k,rerank=rerank)
            found = [h["source_id"] for h in result["hits"]]
            rank = next((i for i,doc in enumerate(found,1) if doc in expected),None)
            recall = len(set(found) & expected) / len(expected)
            rows.append({"question":case["question"],"expected_source_ids":list(expected),
                         "retrieved_source_ids":found,"recall_at_k":round(recall,3),
                         "reciprocal_rank": round(1/rank,3) if rank else 0,
                         "latency_ms":result["latency_ms"]})
        count = len(rows)
        return {"cases":rows,"recall_at_k":round(sum(c["recall_at_k"] for c in rows)/count,3),
                "mrr":round(sum(c["reciprocal_rank"] for c in rows)/count,3),
                "mean_latency_ms":round(sum(c["latency_ms"] for c in rows)/count,1),
                "note":"Retrieval metrics only; not a faithfulness or answer-quality score."}
