# Paper B — Illustrative Fusion and Reranking Experiment

**Sample data only — these results are invented for testing the application, not a real publication.**

The team applies reciprocal rank fusion (RRF) with a rank constant of 60 to combine BM25 and dense search. A CrossEncoder then reranks the top 20 passages before the top 5 are provided to an LLM. The illustrative experiment reports Recall@5 of 0.86 and mean retrieval latency of 340 milliseconds.

Limitations: the reranker increases latency, multilingual queries were not studied, and the evaluation did not assess answer faithfulness or factual correctness. The method cannot guarantee that the LLM will never hallucinate.
