# Verification record — 2026-11-17

The following commands were executed successfully in the build environment.

```text
$ python -m pytest -q
..................... [100%]
21 passed

$ python -m scripts.live_smoke
PASS homepage and Javascript served
PASS PDF indexed
PASS chat grounded in PDF page 1
PASS original PDF downloadable
PASS document deletion

$ python -m compileall -q doculens scripts
(no errors)

$ node --check frontend/app.js
(no errors)
```

These checks use a deterministic offline embedding backend with persistent SQLite vectors, and do not require internet access or API credentials. The command-line evidence-only demonstration also succeeded with two illustrative research papers.

**Not independently verified here:** full dependency installation (package index access unavailable), ChromaDB persistent runtime, downloaded SentenceTransformer and CrossEncoder weights, Google Gemini / local Ollama credentials, real remote URL ingestion, OCR/Tesseract, and Docker build. The source code and configuration for these components are included; validate them in a machine with the needed services and packages before describing the whole solution as production-ready.

## Local Windows integration verification — 2026-11-17

- Used existing Python 3.11.9 virtual environment; installed pytest development dependencies; `pip check` reported no broken requirements.
- All 21 pytest checks passed on the Windows laptop.
- FastAPI health endpoint served the real configured backends: `sentence-transformers`, ChromaDB, CrossEncoder enabled, Gemini selected but not ready (key missing).
- Downloaded and loaded pretrained `all-MiniLM-L6-v2` embedding weights; indexed `paper_a.md` and `paper_b.md` through the live HTTP API into persistent ChromaDB.
- CrossEncoder `ms-marco-MiniLM-L-6-v2` loaded, and the reranked hybrid retrieval search returned hits from both papers with no warnings (`reranked: true`). The cold-load retrieval took about 57 seconds.
- `python -m scripts.verify_full_stack` passed live HTML/JS, two-page PDF ingestion, pasted-text ingestion, document-filtered retrieval, page-specific citations, evidence-only chat, prompt modes, original PDF download and test-document cleanup.
- Live import of `https://example.com/` returned one indexed document and was cleaned up.
- Windows `Start_DocuLens.ps1` successfully started a detached server and preserved the Chroma index across restart; `Restart_DocuLens.ps1` also restarted it safely.
- **Pending:** No Gemini key is present, so actual Gemini-generated responses were not tested. No Ollama model was installed. The app currently returns cited evidence-only excerpts rather than synthesized answers.
- **Not covered:** OCR/Tesseract integration, hosted deployment, adversarial prompt-injection tests, or multiuser security audit.

## Chat composer attachments feature — 2026-11-17

- Added `＋ Attach` file picker, pending file chips with removal, and 10-file/20 MB per-file limits to the chat composer.
- Added `chatView` PDF/document drag and drop and clipboard-file paste handling. Normal text paste is untouched; clipboard-file access depends on browser support.
- Send indexes staged attachments via `/api/documents/upload`, adds documents to the Knowledge Library, and scopes that question to the newly uploaded IDs; attachment-only messages use a grounded summary request.
- Added `tests/test_chat_attachments.py` and real Chrome automation script `scripts/browser_attachment_smoke.py`.
- Final check: `node --check frontend/app.js` passed; `python -m pytest -q` yielded **24 passed**; real Chrome test confirmed button visibility, staged PDF, removal, simulated clipboard-file paste, drag/drop, PDF indexing, and chat source ID scoping. Live test file removed afterward.
- Browser assets versioned in `frontend/index.html` to avoid stale cached frontend files. No API key was read or displayed during feature testing.

## Windows PostgreSQL + Gemini full integration — November 17, 2026

- PostgreSQL 18.4 was already installed on Windows and running as a service on port 5432. That existing service and data were left untouched.
- Created isolated local password-protected PostgreSQL 18.4 cluster in data/postgres18 on 127.0.0.1:5433, with database doculens_rag owned by non-superuser doculens_app.
- Database tables: documents (source metadata) and messages (chat history). ChromaDB continues indexing semantic vector embeddings.
- Migrated 3 existing document rows and 8 existing message records from metadata.sqlite3 without removing that file. Preserved data/metadata.before-postgres.sqlite3 as backup.
- Added psycopg 3 driver, PostgresDocumentDB adapter, backend configuration, and automatic local PostgreSQL start through Start_DocuLens.ps1.
- Confirmed FastAPI /api/health reports metadata_backend=postgres, vector_backend=chroma; existing vector chunks persisted across app restart.
- Added one benign demo document through /api/documents/text, verified it directly in PostgreSQL, and retrieved its chunk via Chroma + BM25.
- Verified both user and assistant messages were saved to PostgreSQL in fallback evidence-only chat.
- Gemini 2.5 Flash was unavailable to this API key (404); a 3.8 Flash request returned 503. Queried available model names and verified gemini-3.5-flash-lite generates valid text for this key. Updated .env and example configuration to that model.
- A final live /api/chat request succeeded with provider=gemini, one cited source, and an accurate generated answer distinguishing PostgreSQL metadata from Chroma embeddings.
- Last full local automated test run: 27 tests passed. Previous offline tests remain isolated on SQLite to avoid modifying live PostgreSQL test records.
- Security: passwords were randomly generated on-device and stored only under local data/private and the ignored .env file; no passwords were printed. PostgreSQL 5433 binds to localhost only.
- This demonstrates document metadata and chat persistence in PostgreSQL; vectors are in Chroma, not pgvector. Scanned PDF OCR, hosted multi-user deployment and automatic backups are outside the verified scope.

## Final user-led pgAdmin and full browser audit — November 17, 2026

- pgAdmin screenshot confirmed SQL access to doculens_rag and its two PostgreSQL tables, with the original 4 documents, 12 messages and 6 sessions at the time of inspection.
- Tested new browser workflow with a temporary two-page PDF containing a unique token on page 2.
- First integration run exposed that Gemini could omit inline citation markers despite returning relevant evidence. Added a minimal citation fallback in RAGService that displays clickable retrieved source references as **not independently verified**, rather than inventing claim-to-source attribution. Observed RED test failure, then GREEN; new tests test_citation_fallback.py.
- Repeated full live Chrome smoke after restart: PDF upload, Gemini-generated answer with accessible citation, source panel reporting page 2, restored chat on browser refresh, document and both chat turns persisted to PostgreSQL, CrossEncoder reranking retrieved page 2. Temporary test document and session were deleted.
- Final local suite: 29 pytest tests passed, zero failures. New one-click Verify_DocuLens.bat ran successfully with exit code 0: PostgreSQL status, automated tests, then live evaluation.
- On the two illustrative sample-paper retrieval queries: Recall@5 1.0, MRR 0.75, average retrieval about 48.1 ms in the last run. This is not a production benchmark.
- Current setup at final check: PostgreSQL metadata, Chroma vectors, local sentence embeddings, Gemini integration, web UI and document retrieval tested. Code lives in the existing local Windows folder; GitHub deployment was not attempted.
- Limitations: OCR for scanned documents remains off; application authentication is not configured for internet deployment; citations are retrieved-evidence references and do not prove every LLM-generated claim.

## Conversational chat and exact search upgrade — 2026-11-17

- Diagnosed `Case Study.pdf`: 7 extractable pages and 29 indexed chunks. The query `find the word the in this` was incorrectly rejected because BM25 filtered stop-words and semantic similarity failed threshold.
- Added deterministic exact word/phrase lookup independent of embeddings, with per-page counts and source references. Live result on the existing Case Study PDF: 178 whole-word occurrences of `the` across seven pages.
- Added lightweight greeting answers, summary-focused retrieval for vague document questions, and explicit General chat mode (no retrieval or misleading document citations), plus attachment-specific follow-up selection.
- Added Gemini transient-error fallback via a second model and evidence-only answers for document Q&A if both unavailable.
- Observed failing tests first for missing chat intents and Gemini fallback; corrected implementation. Last local regression suite: 39 passing tests.
- Publishing to a new **private** repository; Git excludes .env, database credentials, local PostgreSQL/Chroma data, PDFs, and venv.

## Final local chatbot checks — 2026-11-17

- Repeated a live exact-word lookup on user's selected Case Study PDF: provider=document-search; 178 occurrences of `the` across seven matching pages; results returned with source references.
- Asked an ordinary general question with `mode=chat` and no document selection: Gemini returned a meaningful response, provider=gemini, no bogus PDF citations.
- Added transient Gemini fallback for both grounded and general chat; focused fallback tests demonstrate a secondary-model attempt after HTTP 503, and document retrieval degrades to labelled evidence-only output if the LLM is down.
- Full local suite: **39 tests passed**, and `node --check frontend/app.js` completed successfully.
- Chrome browser attachment regression: Attach button, staged PDF, removal, clipboard-file paste, drag/drop, upload and document-scoped chat request all passed. Temporary test upload was deleted.
- User's actual PostgreSQL / Chroma records are retained; local secret files are excluded by `.gitignore`. Source code pushed to private GitHub repository only.

## Library-awareness and commonality upgrade — November 18, 2026

- Reproduced reported query: `what ppt in in the our source and is the common in it`. Previously returned unrelated RAG fragments.
- New metadata route: correctly responded **No PowerPoint presentations (PPT/PPTX) are uploaded**, enumerated available PDF/Markdown/text sources and offered an appropriate commonality prompt. Confirmed via live `/api/chat` HTTP request.
- Separate PDF inventory query correctly returned two existing PDFs; no Gemini call or irrelevant vector evidence needed.
- Added diverse source comparisons: first representative chunk per selected document (maximum 8). Live Gemini answer using five selected sources reported no universal common theme and differentiated document topics; all five source overviews were returned, identified as overview evidence rather than semantic similarity.
- Improved abstention handling: does not attach random citations to a model answer that says information was unavailable.
- Added All/None source selection count and two chat shortcuts. Chrome browser smoke passed source toggle, shortcut interactions, and page JavaScript checks.
- Tests observed failing before implementation; focused suite 9 passed and full local suite **46 passed** at last run. This is a local RAG usability improvement, not model training or a comprehensive external hallucination benchmark.

## Find content and scheduled local health watch — November 18, 2026

- Added a `Find content / passages` mode and automatic detection of targeted extract-the-passage requests in document Q&A, bypassing LLM generation. Retrieved excerpts are focused on matching sentences, with original PDF page references; unrelated results are filtered.
- Added tests for PDF page 2 retrieval, no-match/selected-source abstention, API/UI mode selection and focused snippets. Observed failing tests before implementation. Full suite after changes: 57 tests passed; JavaScript syntax compiled.
- Windows Scheduled Task `DocuLens AI Health Watch` registered to run every 15 minutes for the interactive Windows user, using restricted execution privilege. A test invocation returned Task Scheduler result 0 and logged health=healthy/retrieval=ok.
- First watch attempt flagged degraded during a cold model load. Investigated actual retrieval: the benchmark document was ranked #1; the issue was the request timing out before lazy model initialization. Added a longer timeout with one retry; watch now returns healthy, quality ok.
- Verified actual self-recovery by terminating only the existing DocuLens FastAPI server after checking its command line. The watchdog restarted it and restored healthy local API with 5 documents, 50 Chroma chunks and retrieval=ok. No document or database records were removed.
- Improved watchdog recovery to use the safe restart script, including when a DocuLens-owned process remains bound to port 8000 but is no longer answering health checks. It refuses to kill unrelated processes.
- Ongoing checks only run when the laptop is on and logged in; quality warnings are recorded for future debugging, not autonomously resolved by code edits. Monitoring makes no calls to a Gemini model.

## Final comprehensive check — November 18, 2026

- `Verify_DocuLens.bat` completed successfully: PostgreSQL database reachable, 57 pytest tests passed, and live hybrid retrieval passed both demo queries (Recall@5 1.0 and MRR 0.75 on only 2 illustrative cases).
- Live Chrome UI check passed source selection, PDF listing, Find content shortcut and topic prompt; no JavaScript page errors.
- `scripts.smoke_find_content` found five candidate Case Study PDF passages across pages 1, 3, 5 and 6, including literal 'customer satisfaction' evidence and original-page references; the test conversation was removed.
- A live `scripts.health_watch` run reported healthy and retrieval=ok, preserving 5 source records and 50 vector chunks.
- Windows Scheduled Task remained ready, last task result 0; no credentials, model weights, uploads, or database files were staged for GitHub.
