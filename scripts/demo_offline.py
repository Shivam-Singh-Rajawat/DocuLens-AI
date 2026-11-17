"""Self-contained offline smoke demo. No API key, model download or Chroma required."""
from pathlib import Path
from tempfile import TemporaryDirectory
from doculens.settings import Settings
from doculens.service import RAGService

with TemporaryDirectory() as directory:
    svc = RAGService(Settings(data_dir=Path(directory),embedding_backend="hash",
                              vector_backend="sqlite",enable_reranker=False,llm_provider="none"))
    for filename in ["paper_a.md","paper_b.md"]:
        file = Path(__file__).resolve().parent.parent / "sample_data" / filename
        doc = svc.ingest_file(filename,file.read_bytes())
        print("Indexed:",doc["name"],"with",doc["chunks"],"chunks")
    result = svc.chat("What are the limitations of reranking?",rerank=False)
    print("\nQUESTION:",result["question"])
    print("\nANSWER:\n",result["answer"])
    print("\nSOURCES:",[(s["source_name"],s["page"]) for s in result["sources"]])
