# Paper A — Illustrative Hybrid RAG Study

**Sample data only — these results are invented for testing the application, not a real publication.**

The study compares keyword BM25 retrieval to a semantic embedding model on a small educational collection. The method uses 800-character chunks with a 100-character overlap. It reports an illustrative Recall@5 of 0.72 for keyword search and 0.81 for semantic search. The authors conclude that dense semantic retrieval helps when queries paraphrase the source.

Limitations: the dataset is small, no out-of-domain evaluation was performed, and answering accuracy was not measured. Further work should test a hybrid approach and reranking on larger collections.
