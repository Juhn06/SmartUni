# RAG Pipeline Configuration

Techniques implemented from [RAG_Techniques](https://github.com/NirDiamant/RAG_Techniques).

## Environment Variables

| Variable | Default | Description |
|----------|---------|--------------|
| `RAG_QUERY_TRANSFORM` | `true` | #6 Query Transformations – rewrite query into 3 variants for better recall |
| `RAG_HYDE` | `true` | #7 HyDE – generate hypothetical answer, embed it for retrieval |
| `RAG_CONTEXT_ENRICH` | `true` | #11 Context Enrichment – add neighboring chunks around each hit |
| `RAG_RERANK` | `false` | #16 Reranking – LLM scores top 8 candidates, reorders (adds latency) |
| `RAG_RSE` | `false` | #10 Relevant Segment Extraction – merge adjacent chunks into longer segments |
| `RAG_EXPLAIN` | `true` | #27 Explainable – include `relevance_score` (0–1) in results |
| `RAG_USE_RCS` | `true` | PaperQA2 RCS – relevance-scored contextual summarization in chat |
| `RAG_CONTEXT_BUDGET` | `4000` | Max tokens for context passed to LLM |

## Recommendations

- **Default** (low latency): `RAG_RERANK=false`, `RAG_RSE=false`
- **Higher accuracy** (slower): `RAG_RERANK=true` – reranks top 8 with LLM
- **Richer context**: `RAG_RSE=true` – merges consecutive chunks from same article
