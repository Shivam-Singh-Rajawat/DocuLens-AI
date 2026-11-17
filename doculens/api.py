"""FastAPI endpoints; Swagger at /docs, dashboard at /."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from doculens.llm import PROMPT_MODES
from doculens.service import RAGService
from doculens.settings import ROOT, Settings


class TextInput(BaseModel):
    title: str = Field(default="Pasted notes",max_length=150)
    content: str = Field(min_length=1,max_length=2000000)


class URLInput(BaseModel):
    url: str = Field(min_length=10,max_length=2048)


class SearchInput(BaseModel):
    question: str = Field(min_length=1,max_length=4000)
    source_ids: list[str] | None = None
    top_k: int = Field(default=5,ge=1,le=20)
    rerank: bool = True


class ChatInput(SearchInput):
    session_id: str | None = Field(default=None,max_length=128)
    mode: Literal["qa", "compare", "summarize", "extract", "study", "quiz", "chat", "find"] = "qa"
    custom_instructions: str = Field(default="",max_length=1200)


class EvalCase(BaseModel):
    question: str = Field(min_length=1,max_length=4000)
    expected_source_ids: list[str] = Field(min_length=1)


class EvalInput(BaseModel):
    cases: list[EvalCase] = Field(min_length=1,max_length=100)
    top_k: int = Field(default=5,ge=1,le=20)
    rerank: bool = False


@lru_cache(maxsize=1)
def get_service() -> RAGService:
    return RAGService()


def create_app(service: RAGService | None = None) -> FastAPI:
    app = FastAPI(title="DocuLens AI",version="1.0.0",
                  description="Hybrid RAG: ingestion, retrieval, reranking, grounded Q&A and evaluation")
    app.add_middleware(CORSMiddleware,
                       allow_origins=["http://localhost:8501","http://127.0.0.1:8501",
                                      "http://localhost:8000","http://127.0.0.1:8000"],
                       allow_methods=["GET","POST","DELETE"],allow_headers=["*"])
    config = service.settings if service else Settings()

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        if (config.app_token and request.url.path.startswith("/api/") and
                request.url.path != "/api/health" and
                request.headers.get("X-App-Token") != config.app_token):
            return JSONResponse({"detail":"Invalid or missing X-App-Token header"},status_code=401)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def bad_input(request: Request, exc: ValueError):
        return JSONResponse({"detail":str(exc)},status_code=400)

    @app.exception_handler(RuntimeError)
    async def unavailable(request: Request, exc: RuntimeError):
        return JSONResponse({"detail":str(exc)},status_code=503)

    def dependency():
        return service or get_service()

    @app.get("/api/health")
    def health(svc: RAGService = Depends(dependency)):
        return {"status":"ok","documents":len(svc.list_documents()),
                "chunks":svc.store.count(),"vector_backend":svc.settings.vector_backend,
                "metadata_backend":svc.settings.metadata_backend,
                "embedding_backend":svc.settings.embedding_backend,
                "llm_provider":svc.settings.llm_provider,
                "llm_ready": (bool(svc.settings.gemini_key) if svc.settings.llm_provider == "gemini" else True),
                "reranker_enabled":svc.settings.enable_reranker}

    @app.get("/api/prompts")
    def prompts():
        return PROMPT_MODES

    @app.get("/api/documents")
    def documents(svc: RAGService = Depends(dependency)):
        return svc.list_documents()

    @app.post("/api/documents/upload",status_code=201)
    async def upload(request: Request, svc: RAGService = Depends(dependency)):
        # Supports normal multipart uploads and raw bytes with X-Filename.
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            try:
                form = await request.form()
            except AssertionError as exc:
                raise RuntimeError("Install python-multipart to accept multipart uploads.") from exc
            file = form.get("file")
            if not file or not getattr(file,"filename",None):
                raise ValueError("Expected a file field in multipart form.")
            name = file.filename
            data = await file.read(svc.settings.max_upload_mb*1024*1024+1)
            await file.close()
        else:
            name = request.headers.get("X-Filename", "document.txt")
            data = await request.body()
        return svc.ingest_file(name,data)

    @app.post("/api/documents/text",status_code=201)
    def ingest_text(data: TextInput, svc: RAGService = Depends(dependency)):
        return svc.ingest_text(data.title,data.content)

    @app.post("/api/documents/url",status_code=201)
    def ingest_url(data: URLInput, svc: RAGService = Depends(dependency)):
        return svc.ingest_url(data.url)

    @app.get("/api/documents/{document_id}")
    def document(document_id: str, svc: RAGService = Depends(dependency)):
        result = svc.db.document(document_id)
        if not result:
            raise HTTPException(status_code=404,detail="Document not found")
        return result

    @app.get("/api/documents/{document_id}/file")
    def download_document(document_id: str, svc: RAGService = Depends(dependency)):
        record = svc.db.document(document_id)
        if not record or not record["file_path"] or not Path(record["file_path"]).is_file():
            raise HTTPException(status_code=404,detail="Original file not available")
        return FileResponse(record["file_path"],filename=record["name"])

    @app.delete("/api/documents/{document_id}")
    def delete_document(document_id: str, svc: RAGService = Depends(dependency)):
        if not svc.delete_document(document_id):
            raise HTTPException(status_code=404,detail="Document not found")
        return {"deleted":True,"document_id":document_id}

    @app.post("/api/search")
    def search(data: SearchInput, svc: RAGService = Depends(dependency)):
        return svc.search(data.question,source_ids=data.source_ids,top_k=data.top_k,rerank=data.rerank)

    @app.post("/api/chat")
    def chat(data: ChatInput, svc: RAGService = Depends(dependency)):
        return svc.chat(data.question,session_id=data.session_id,source_ids=data.source_ids,
                        top_k=data.top_k,rerank=data.rerank,mode=data.mode,
                        custom_instructions=data.custom_instructions)

    @app.get("/api/sessions/{session_id}")
    def history(session_id: str, svc: RAGService = Depends(dependency)):
        return {"session_id":session_id,"messages":svc.db.history(session_id)}

    @app.delete("/api/sessions/{session_id}")
    def delete_history(session_id: str, svc: RAGService = Depends(dependency)):
        svc.db.clear_history(session_id)
        return {"cleared":True}

    @app.post("/api/evaluate")
    def evaluate(data: EvalInput, svc: RAGService = Depends(dependency)):
        return svc.evaluate([c.model_dump() for c in data.cases],top_k=data.top_k,rerank=data.rerank)

    app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True),name="dashboard")
    return app


app = create_app()
