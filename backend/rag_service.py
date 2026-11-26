"""
RAG service for journal articles: PDF parsing, chunking, embeddings, and Q&A.

Techniques implemented (ref: https://github.com/NirDiamant/RAG_Techniques):
- #6 Query Transformations: RAG_QUERY_TRANSFORM
- #7 HyDE (Hypothetical Document Embedding): RAG_HYDE
- #11 Context Enrichment (neighboring chunks): RAG_CONTEXT_ENRICH
- #15 Fusion Retrieval: Reciprocal Rank Fusion across multi-query results
- #16 Reranking: RAG_RERANK (LLM-based relevance scoring)
- #18 Hierarchical Indices: L0/L1/L2 progressive loading
- #10 Relevant Segment Extraction: RAG_RSE (merge adjacent chunks)
- #27 Explainable Retrieval: RAG_EXPLAIN (relevance scores in output)
- PaperQA2 RCS: RAG_USE_RCS (relevance-scored contextual summarization)
"""
import os
import re
from pathlib import Path
from statistics import median

import chromadb
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BACKEND_DIR / "uploads")))
CHROMA_DIR = Path(os.environ.get("CHROMA_DIR", str(BACKEND_DIR / "chroma_db")))
COLLECTION_NAME = "articles"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

_client = None
_client_fingerprint = None

_SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z\d"\(\[])')
_HEADING_PATTERNS = re.compile(
    r"^(Abstract|Introduction|Background|Related Work|Methodology|Methods|"
    r"Approach|Experiment|Results|Discussion|Conclusion|Acknowledgment|"
    r"References|Bibliography|Appendix|Evaluation|Analysis|Literature Review|"
    r"Future Work|Limitations|Implementation|System Design|Architecture|"
    r"Data|Dataset|Overview|Motivation|Problem Statement|Objective|"
    r"Proposed|Summary|Framework|Model|Training|Testing)",
    re.IGNORECASE,
)
_NUMBERED_HEADING = re.compile(r"^\d{1,2}(?:\.\d{1,2})*\.?\s+[A-Z]")
_REFERENCES_HEADING = re.compile(
    r"^(?:\d{1,2}(?:\.\d{1,2})*\.?\s+)?"
    r"(References|Bibliography|Works\s+Cited|Literature\s+Cited)\s*$",
    re.IGNORECASE,
)


def _get_client():
    """Get or recreate OpenAI client (recreates if config changed)."""
    global _client, _client_fingerprint
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    fingerprint = f"{base_url}|{api_key}"
    if _client is None or fingerprint != _client_fingerprint:
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        _client = OpenAI(timeout=300.0, **kwargs)
        _client_fingerprint = fingerprint
    return _client


# ---------------------------------------------------------------------------
# PDF Extraction - Structure-aware (inspired by PaperQA2)
# ---------------------------------------------------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF with structure awareness using PyMuPDF.

    Uses font-size analysis to detect headings and inserts markdown-style
    section markers. Strips repeated page headers/footers.
    """
    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    page_count = len(doc)

    all_font_sizes: list[float] = []
    page_blocks: list[list[dict]] = []

    for page in doc:
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        parsed = []
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                sizes = [s["size"] for s in spans if s.get("text", "").strip()]
                avg_size = sum(sizes) / len(sizes) if sizes else 0
                is_bold = any(
                    "bold" in s.get("font", "").lower() for s in spans
                    if s.get("text", "").strip()
                )
                all_font_sizes.append(avg_size)
                parsed.append({
                    "text": text,
                    "size": avg_size,
                    "bold": is_bold,
                    "y": line["bbox"][1],
                })
        page_blocks.append(parsed)

    doc.close()

    if not all_font_sizes:
        import fitz as fitz2
        doc2 = fitz2.open(pdf_path)
        parts = [p.get_text() for p in doc2]
        doc2.close()
        return "\n\n".join(parts).strip()

    median_size = median(all_font_sizes) if all_font_sizes else 12.0
    major_heading_threshold = median_size * 1.3
    minor_heading_threshold = median_size * 1.15

    header_footer_texts = _detect_headers_footers(page_blocks, page_count)

    output_parts: list[str] = []
    in_references = False

    for page_idx, blocks in enumerate(page_blocks):
        page_lines: list[str] = []

        for block in blocks:
            text = block["text"]

            if text in header_footer_texts:
                continue

            clean = text.strip()
            is_short = len(clean) < 120 and not clean.endswith(".")

            is_major = block["size"] >= major_heading_threshold and is_short
            is_minor = (
                not is_major
                and (block["size"] >= minor_heading_threshold or block["bold"])
                and is_short
            )
            pattern_match = bool(_HEADING_PATTERNS.match(clean)) and is_short
            numbered_match = bool(_NUMBERED_HEADING.match(clean)) and is_short
            is_heading = is_major or is_minor or pattern_match or numbered_match

            if is_heading:
                heading_text = clean.rstrip(".:")

                if _REFERENCES_HEADING.match(heading_text):
                    in_references = True
                    page_lines.append(f"\n## {heading_text}\n")
                    continue

                if in_references:
                    in_references = False

                is_top_level = is_major or pattern_match
                if numbered_match and not re.match(r"^\d{1,2}\.\d", clean):
                    is_top_level = True

                if is_top_level:
                    page_lines.append(f"\n## {heading_text}\n")
                else:
                    page_lines.append(f"\n### {heading_text}\n")
            elif in_references:
                continue
            else:
                page_lines.append(text)

        if page_lines:
            page_text = "\n".join(page_lines)
            output_parts.append(f"[Page {page_idx + 1}]\n{page_text}")

    return "\n\n".join(output_parts).strip()


def _detect_headers_footers(
    page_blocks: list[list[dict]], page_count: int
) -> set[str]:
    """Detect repeated text across pages (headers/footers/page numbers)."""
    if page_count < 3:
        return set()

    top_texts: dict[str, int] = {}
    bottom_texts: dict[str, int] = {}

    for blocks in page_blocks:
        if not blocks:
            continue
        sorted_by_y = sorted(blocks, key=lambda b: b["y"])
        for b in sorted_by_y[:2]:
            t = b["text"].strip()
            if len(t) < 80:
                top_texts[t] = top_texts.get(t, 0) + 1
        for b in sorted_by_y[-2:]:
            t = b["text"].strip()
            if len(t) < 80:
                bottom_texts[t] = bottom_texts.get(t, 0) + 1

    threshold = max(3, page_count // 2)
    repeated = set()
    for text, count in {**top_texts, **bottom_texts}.items():
        if count >= threshold and not _HEADING_PATTERNS.match(text):
            repeated.add(text)

    page_number_re = re.compile(r"^\d{1,4}$")
    for text in list(repeated):
        if page_number_re.match(text):
            repeated.add(text)
    for blocks in page_blocks:
        for b in blocks:
            if page_number_re.match(b["text"].strip()):
                repeated.add(b["text"].strip())

    return repeated


# ---------------------------------------------------------------------------
# Chunking - Section-aware with sentence boundaries
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Split text into overlapping chunks, respecting section and sentence
    boundaries. Produces higher-quality chunks for RAG retrieval.
    """
    if not text or not text.strip():
        return []

    sections = _split_into_sections(text)
    chunks: list[str] = []

    for section in sections:
        section_text = section["text"].strip()
        if not section_text:
            continue

        header = section.get("heading", "")
        prefix = f"[{header}] " if header else ""

        if len(prefix + section_text) <= chunk_size:
            chunks.append((prefix + section_text).strip())
            continue

        sentences = _split_sentences(section_text)
        current = prefix
        for sentence in sentences:
            if len(current) + len(sentence) > chunk_size and len(current) > len(prefix):
                chunks.append(current.strip())
                overlap_text = current[-(overlap):] if len(current) > overlap else current
                current = prefix + overlap_text.lstrip() + " " + sentence
            else:
                current += (" " if current and not current.endswith(" ") else "") + sentence

        if current.strip() and current.strip() != prefix.strip():
            chunks.append(current.strip())

    if not chunks:
        clean = re.sub(r"\s+", " ", text).strip()
        start = 0
        while start < len(clean):
            end = start + chunk_size
            chunk = clean[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
            if start >= len(clean):
                break

    return chunks


def _split_into_sections(text: str) -> list[dict]:
    """Split text at ## and ### heading markers into sections."""
    parts = re.split(r"\n#{2,3}\s+", text)
    sections = []

    if parts[0].strip():
        sections.append({"heading": "", "text": parts[0]})

    for part in parts[1:]:
        lines = part.split("\n", 1)
        heading = lines[0].strip()
        body = lines[1] if len(lines) > 1 else ""
        sections.append({"heading": heading, "text": body})

    return sections


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences at period/question/exclamation boundaries."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = _SENTENCE_END.split(text)
    return [s.strip() for s in parts if s.strip()]


def get_chroma_client():
    """Get persistent ChromaDB client."""
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _extract_section_from_chunk(chunk: str) -> str:
    """Extract section name from a chunk that starts with [SectionName]."""
    m = re.match(r"^\[([^\]]+)\]\s*", chunk)
    return m.group(1) if m else ""


def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed a list of text chunks using the configured embedding model."""
    openai_client = _get_client()
    embed_model = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
    embeddings = []
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        resp = openai_client.embeddings.create(model=embed_model, input=batch)
        embeddings.extend([e.embedding for e in resp.data])
    return embeddings


# ---------------------------------------------------------------------------
# L0/L1/L2 Hierarchical Context (inspired by OpenViking/ByteDance)
#
# L0 = one-line summary (~80 chars) for quick scanning — stored in metadata
# L1 = key details excerpt (~300 chars) for evaluation — stored in metadata
# L2 = full chunk text — stored as the ChromaDB document (loaded on demand)
# ---------------------------------------------------------------------------

def _generate_l0(chunk: str) -> str:
    """Generate L0 summary: first meaningful sentence, capped at 100 chars."""
    clean = re.sub(r"^\[[^\]]*\]\s*", "", chunk).strip()
    clean = re.sub(r"\[Page \d+\]\s*", "", clean).strip()
    sentences = _SENTENCE_END.split(clean)
    first = sentences[0].strip() if sentences else clean[:100]
    if len(first) > 100:
        first = first[:97] + "..."
    return first


def _generate_l1(chunk: str) -> str:
    """Generate L1 excerpt: condensed key details, capped at 300 chars."""
    clean = re.sub(r"^\[[^\]]*\]\s*", "", chunk).strip()
    clean = re.sub(r"\[Page \d+\]\s*", "", clean).strip()
    clean = re.sub(r"\s+", " ", clean)
    if len(clean) <= 300:
        return clean
    sentences = _SENTENCE_END.split(clean)
    excerpt = ""
    for s in sentences:
        if len(excerpt) + len(s) + 1 > 300:
            break
        excerpt += (" " if excerpt else "") + s.strip()
    return excerpt or clean[:300]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4


def _get_or_create_collection(name: str):
    client = get_chroma_client()
    try:
        return client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        return client.create_collection(
            name=name, metadata={"hnsw:space": "cosine"},
        )


def add_article_to_rag(article_id: int, title: str, full_text: str) -> None:
    """Chunk article, embed, and add to ChromaDB with L0/L1/L2 hierarchy."""
    import time as _time
    t0 = _time.time()
    print(f"[RAG] add_article_to_rag: start (article_id={article_id})")

    collection = _get_or_create_collection(COLLECTION_NAME)
    print(f"[RAG] chroma collection ready (+{_time.time()-t0:.2f}s)")

    chunks = chunk_text(full_text)
    print(f"[RAG] chunked into {len(chunks)} chunks (+{_time.time()-t0:.2f}s)")
    if not chunks:
        return

    try:
        existing = collection.get(where={"article_id": article_id}, include=[])
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    print(f"[RAG] embedding {len(chunks)} chunks... (+{_time.time()-t0:.2f}s)")
    embeddings = _embed_chunks(chunks)

    ids = [f"a{article_id}_c{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "article_id": article_id,
            "title": title,
            "chunk_idx": i,
            "section": _extract_section_from_chunk(chunks[i]),
            "l0": _generate_l0(chunks[i]),
            "l1": _generate_l1(chunks[i]),
        }
        for i in range(len(chunks))
    ]

    print(f"[RAG] adding {len(ids)} vectors to chroma... (+{_time.time()-t0:.2f}s)")
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    print(f"[RAG] add_article_to_rag: DONE total={_time.time()-t0:.2f}s")


# ---------------------------------------------------------------------------
# Advanced RAG techniques
# (Inspired by https://github.com/YaxiLuo/all-rag-techniques-main)
# ---------------------------------------------------------------------------

def _query_transform(question: str) -> list[str]:
    """
    Query Transform (technique 07): Rewrite the user's question into
    multiple search-oriented variants to cast a wider retrieval net.
    Returns the original + 2-3 reformulated queries.
    """
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert information retrieval specialist for academic "
                        "paper search systems. Your task is to rewrite a user's question "
                        "into exactly 3 alternative search queries that maximize recall.\n\n"
                        "STRATEGY for each query:\n"
                        "1. SYNONYM VARIANT: Replace key terms with academic synonyms or "
                        "technical equivalents\n"
                        "2. BROADER SCOPE: Generalize the question to capture related work\n"
                        "3. SPECIFIC DRILL-DOWN: Narrow to the most precise technical aspect\n\n"
                        "EXAMPLE:\n"
                        "User: \"How does BERT handle long documents?\"\n"
                        "Output:\n"
                        "transformer models processing lengthy text sequences\n"
                        "language model architectures for document understanding\n"
                        "BERT positional encoding limitations maximum token length\n\n"
                        "RULES:\n"
                        "- Return ONLY 3 queries, one per line\n"
                        "- Do NOT number them or add bullet points\n"
                        "- Do NOT repeat the original question\n"
                        "- Do NOT add explanations or commentary\n"
                        "- Each query should be 5-20 words"
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        variants = [q.strip().lstrip("0123456789.-) ") for q in text.split("\n") if q.strip()]
        variants = [v for v in variants if len(v) > 5][:3]
        print(f"[RAG] query_transform: {len(variants)} variants generated")
        return [question] + variants
    except Exception as e:
        print(f"[RAG] query_transform failed: {e}")
        return [question]


def _generate_hyde(question: str) -> str:
    """
    HyDE - Hypothetical Document Embeddings (technique 19): Generate a
    hypothetical answer passage. Its embedding is closer in vector space
    to real relevant passages than the raw question embedding.
    """
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a prolific academic researcher who has authored hundreds "
                        "of peer-reviewed papers. Given a research question, write a short "
                        "paragraph (3-5 sentences) that reads exactly like an excerpt from "
                        "a real published paper that answers this question.\n\n"
                        "WRITING STYLE:\n"
                        "- Use formal academic tone with passive voice where appropriate\n"
                        "- Include plausible technical terminology and methodology terms\n"
                        "- Reference concepts as if they were established in the literature\n"
                        "- Include quantitative language (e.g., 'significantly', 'achieved "
                        "94.2% accuracy', 'p < 0.05')\n\n"
                        "DO NOT:\n"
                        "- Say 'I don't know' or express uncertainty\n"
                        "- Start with 'This paper' or 'In this study' every time\n"
                        "- Add citations like [1] or (Author, Year)\n"
                        "- Write more than 5 sentences"
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=250,
        )
        hyde_doc = resp.choices[0].message.content.strip()
        print(f"[RAG] HyDE: generated {len(hyde_doc)} char hypothetical doc")
        return hyde_doc
    except Exception as e:
        print(f"[RAG] HyDE failed: {e}")
        return question


def _reciprocal_rank_fusion(
    result_lists: list[list[dict]], k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion (technique 16): Merge multiple ranked result
    lists into one, boosting items that appear in multiple lists.
    Score = sum(1 / (k + rank)) across all lists where the item appears.
    """
    scores: dict[str, float] = {}
    item_map: dict[str, dict] = {}

    for results in result_lists:
        for rank, item in enumerate(results):
            key = item["content"][:200]
            if key not in item_map:
                item_map[key] = item
                scores[key] = 0.0
            scores[key] += 1.0 / (k + rank + 1)

    ranked_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    fused = []
    for key in ranked_keys:
        entry = item_map[key].copy()
        entry["rrf_score"] = scores[key]
        fused.append(entry)

    return fused


def _enrich_with_neighbors(
    results: list[dict], collection_name: str, id_field: str,
    window: int = 1,
) -> list[dict]:
    """
    Context Enrichment (technique 04): For each retrieved chunk, also
    fetch its immediate neighbors (chunk_idx ± window) to provide
    surrounding context that may have been cut by chunking boundaries.
    """
    if not results:
        return results

    try:
        client = get_chroma_client()
        collection = client.get_collection(name=collection_name)
    except Exception:
        return results

    enriched_keys = set()
    enriched = []

    for r in results:
        content_key = r["content"][:200]
        if content_key in enriched_keys:
            continue
        enriched_keys.add(content_key)
        enriched.append(r)

        item_id = r.get(id_field)
        chunk_idx = None
        section = r.get("section", "")

        try:
            if "chunk_idx" in r:
                chunk_idx = r["chunk_idx"]
            elif item_id is not None:
                peek = collection.get(
                    where={id_field: item_id},
                    include=["metadatas"],
                )
                for j, meta in enumerate(peek.get("metadatas", [])):
                    if meta.get("chunk_idx") is not None:
                        doc_text = (peek.get("documents") or [None])[j]
                        if doc_text and doc_text[:100] == r["content"][:100]:
                            chunk_idx = meta["chunk_idx"]
                            break
        except Exception:
            pass

        if chunk_idx is None or item_id is None:
            continue

        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            neighbor_idx = chunk_idx + offset
            if neighbor_idx < 0:
                continue
            try:
                neighbor = collection.get(
                    where={"$and": [{id_field: item_id}, {"chunk_idx": neighbor_idx}]},
                    include=["documents", "metadatas"],
                )
                if neighbor and neighbor["documents"]:
                    for ni, ndoc in enumerate(neighbor["documents"]):
                        nkey = ndoc[:200]
                        if nkey not in enriched_keys:
                            enriched_keys.add(nkey)
                            nmeta = neighbor["metadatas"][ni] if neighbor.get("metadatas") else {}
                            enriched.append({
                                "content": ndoc,
                                id_field: item_id,
                                "chunk_idx": neighbor_idx,
                                "title": nmeta.get("title", r.get("title", "")),
                                "section": nmeta.get("section", section),
                                "distance": None,
                                "is_neighbor": True,
                            })
            except Exception:
                pass

    return enriched


def _raw_vector_query(
    collection, query_text: str, id_field: str,
    id_values: list[int] | None, top_k: int,
    metadata_only: bool = False,
) -> list[dict]:
    """
    Single vector query against a ChromaDB collection.

    When metadata_only=True (progressive L0 scan), only fetch metadata
    and distances — skip loading full document text to save memory.
    """
    q_emb = _embed_chunks([query_text])[0]

    where = None
    if id_values:
        where = {id_field: {"$in": id_values}}

    include = ["metadatas", "distances"]
    if not metadata_only:
        include.insert(0, "documents")

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(top_k, 20),
        where=where,
        include=include,
    )

    if not results or not results.get("metadatas") or not results["metadatas"][0]:
        return []

    out = []
    n = len(results["metadatas"][0])
    for i in range(n):
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i] if results.get("distances") else None

        entry = {
            id_field: meta.get(id_field),
            "title": meta.get("title", ""),
            "section": meta.get("section", ""),
            "chunk_idx": meta.get("chunk_idx"),
            "l0": meta.get("l0", ""),
            "l1": meta.get("l1", ""),
            "distance": dist,
        }

        if not metadata_only and results.get("documents"):
            entry["content"] = results["documents"][0][i]
        else:
            entry["content"] = meta.get("l1", "")

        out.append(entry)
    return out


def _llm_rerank(question: str, candidates: list[dict], top_n: int = 8) -> list[dict]:
    """
    Technique #16 Reranking: Use LLM to score relevance of top candidates and reorder.
    Controlled by RAG_RERANK env (default: false to avoid extra LLM cost).
    """
    if not candidates or len(candidates) <= 1:
        return candidates
    limit = min(len(candidates), 8)
    to_score = [c.copy() for c in candidates[:limit]]
    rest = candidates[limit:]
    client = _get_client()
    for c in to_score:
        content = (c.get("content") or c.get("l1") or "")[:800]
        title = c.get("title", "Unknown")
        try:
            resp = client.chat.completions.create(
                model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
                messages=[
                    {
                        "role": "system",
                        "content": "Score relevance 0-10. Reply with ONLY a number. 0=unrelated, 10=directly answers.",
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nExcerpt from {title}:\n{content}\n\nRelevance score (0-10):",
                    },
                ],
                max_tokens=5,
            )
            text = resp.choices[0].message.content.strip()
            m = re.search(r"\d+", text)
            score = min(10, max(0, int(m.group()) if m else 5))
        except Exception:
            score = 5
        c["_rerank_score"] = score
    to_score.sort(key=lambda x: x.get("_rerank_score", 0), reverse=True)
    return to_score[:top_n] + rest


def _merge_adjacent_chunks(candidates: list[dict], id_field: str) -> list[dict]:
    """
    Technique #10 Relevant Segment Extraction: Merge consecutive chunks from the same
    article into longer segments for richer context.
    """
    if not candidates:
        return []
    by_item: dict[int | str, list[dict]] = {}
    for i, c in enumerate(candidates):
        item_id = c.get(id_field)
        if item_id is None:
            item_id = f"_orphan_{i}"
        if item_id not in by_item:
            by_item[item_id] = []
        by_item[item_id].append((i, c))
    all_segments = []
    for item_id, items in by_item.items():
        items = sorted(items, key=lambda x: (x[1].get("chunk_idx") if x[1].get("chunk_idx") is not None else 999999, x[0]))
        j = 0
        while j < len(items):
            orig_pos, first = items[j]
            seg_contents = [first.get("content", "")]
            while j + 1 < len(items):
                curr_idx = items[j][1].get("chunk_idx")
                next_idx = items[j + 1][1].get("chunk_idx")
                if curr_idx is not None and next_idx is not None and next_idx == curr_idx + 1:
                    j += 1
                    seg_contents.append(items[j][1].get("content", ""))
                else:
                    break
            seg = first.copy()
            seg["content"] = "\n\n".join(s for s in seg_contents if s).strip()
            seg["_orig_pos"] = orig_pos
            all_segments.append(seg)
            j += 1
    all_segments.sort(key=lambda s: s.get("_orig_pos", 999))
    for s in all_segments:
        s.pop("_orig_pos", None)
    return all_segments


def _promote_to_l2(
    collection, candidates: list[dict], id_field: str,
) -> list[dict]:
    """
    Progressive loading: upgrade L0/L1-only results to full L2 content
    by fetching the actual documents from ChromaDB for top candidates.
    """
    needs_l2 = [c for c in candidates if len(c.get("content", "")) < 350]
    if not needs_l2:
        return candidates

    for c in needs_l2:
        item_id = c.get(id_field)
        chunk_idx = c.get("chunk_idx")
        if item_id is None or chunk_idx is None:
            continue
        try:
            result = collection.get(
                where={"$and": [{id_field: item_id}, {"chunk_idx": chunk_idx}]},
                include=["documents"],
            )
            if result and result["documents"]:
                c["content"] = result["documents"][0]
        except Exception:
            pass

    return candidates


def _query_collection(
    collection_name: str, question: str, id_field: str,
    id_values: list[int] | None = None, top_k: int = 5,
    for_search: bool = False,
) -> list[dict]:
    """
    Enhanced retrieval pipeline with OpenViking-style progressive loading:

    Phase 1 (broad scan):  Query Transform + HyDE → retrieve many candidates
                           with metadata only (L0 summaries) — cheap.
    Phase 2 (rank + fuse): Reciprocal Rank Fusion across all query results.
    Phase 3 (promote):     Load full L2 text only for top candidates.
    Phase 4 (enrich):      Fetch neighboring chunks for context.
    Phase 5 (budget):      Trim to context token budget.

    Each technique is controlled by an env var and gracefully degrades.
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        return []

    use_transform = os.environ.get("RAG_QUERY_TRANSFORM", "true").lower() != "false"
    use_hyde = os.environ.get("RAG_HYDE", "true").lower() != "false"
    use_neighbors = os.environ.get("RAG_CONTEXT_ENRICH", "true").lower() != "false"
    use_rerank = os.environ.get("RAG_RERANK", "false").lower() == "true"
    use_rse = os.environ.get("RAG_RSE", "false").lower() == "true"
    use_explain = os.environ.get("RAG_EXPLAIN", "true").lower() != "false"
    context_budget = int(os.environ.get("RAG_CONTEXT_BUDGET", "4000"))

    queries = [question]

    if use_transform:
        queries = _query_transform(question)

    if use_hyde:
        hyde_doc = _generate_hyde(question)
        queries.append(hyde_doc)

    multi_query = len(queries) > 1
    scan_k = max(top_k * 3, 10) if multi_query else top_k

    if multi_query:
        all_result_lists = []
        for q in queries:
            q_results = _raw_vector_query(
                collection, q, id_field, id_values, scan_k,
                metadata_only=True,
            )
            if q_results:
                all_result_lists.append(q_results)

        if all_result_lists:
            results = _reciprocal_rank_fusion(all_result_lists)
        else:
            results = []
    else:
        results = _raw_vector_query(
            collection, question, id_field, id_values, top_k,
            metadata_only=False,
        )

    candidates = results[:top_k * 2]

    if multi_query and candidates:
        candidates = _promote_to_l2(collection, candidates, id_field)

    if use_rerank and candidates:
        candidates = _llm_rerank(question, candidates, top_n=min(top_k + 2, 8))

    if use_neighbors and candidates:
        candidates = _enrich_with_neighbors(
            candidates, collection_name, id_field, window=1,
        )

    if use_rse and candidates:
        candidates = _merge_adjacent_chunks(candidates, id_field)

    if for_search:
        final = candidates[:top_k]
    else:
        token_count = 0
        final = []
        for r in candidates:
            chunk_tokens = _estimate_tokens(r.get("content", ""))
            if token_count + chunk_tokens > context_budget and final:
                break
            token_count += chunk_tokens
            final.append(r)

    for r in final:
        if use_explain and r.get("distance") is not None:
            d = float(r["distance"])
            r["relevance_score"] = round(max(0, 1 - d / 2), 2)
        if r.get("_rerank_score") is not None:
            r["rerank_score"] = r.pop("_rerank_score", None)
        r.pop("chunk_idx", None)
        r.pop("is_neighbor", None)
        r.pop("rrf_score", None)
        r.pop("l0", None)
        r.pop("l1", None)

    if for_search:
        print(f"[RAG] _query_collection: {collection_name} | search | final={len(final)}")
    else:
        print(
            f"[RAG] _query_collection: {collection_name} | "
            f"queries={len(queries)} | scanned={len(results)} | "
            f"final={len(final)} | ~tokens={token_count}/{context_budget}"
        )
    return final


def query_articles(
    question: str,
    article_ids: list[int] | None = None,
    top_k: int = 5,
    for_search: bool = False,
) -> list[dict]:
    """Retrieve relevant chunks for a question from articles."""
    return _query_collection(
        COLLECTION_NAME, question, "article_id", article_ids, top_k, for_search=for_search
    )


def query_articles_fast(
    question: str,
    article_ids: list[int] | None = None,
    top_k: int = 15,
) -> list[dict]:
    """
    Fast semantic search: single embedding + vector query, no Query Transform,
    HyDE, neighbor enrichment, or rerank. Optimized for /api/ask latency.
    """
    try:
        client = get_chroma_client()
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return []
    results = _raw_vector_query(
        collection, question, "article_id", article_ids, top_k, metadata_only=False
    )
    for r in results:
        if r.get("distance") is not None:
            r["relevance_score"] = round(max(0, 1 - float(r["distance"]) / 2), 2)
        r.pop("chunk_idx", None)
        r.pop("l0", None)
        r.pop("l1", None)
    return results


def generate_summary_three_pass(full_text: str) -> dict:
    """Generate three-pass style summary using CoT and structured output."""
    client = _get_client()
    truncated = full_text[:12000] if len(full_text) > 12000 else full_text

    system_prompt = (
        "You are a senior research scientist with 20+ years of experience reviewing "
        "academic papers across multiple disciplines (CS, AI/ML, engineering, medicine). "
        "You use S. Keshav's three-pass method to systematically analyze papers.\n\n"
        "APPROACH: Think step-by-step through each pass. For each pass, first identify "
        "what information is available in the text, then synthesize your analysis.\n\n"
        "OUTPUT FORMAT: Use the exact markdown headers shown below. Do not skip any section.\n\n"
        "DO NOT:\n"
        "- Invent information not present in the paper\n"
        "- Use vague phrases like 'the paper discusses various things'\n"
        "- Copy-paste raw text verbatim — always synthesize in your own words\n"
        "- Add a generic conclusion paragraph at the end"
    )

    prompt = (
        "Analyze this academic paper using the three-pass method.\n\n"
        "## Pass 1: Bird's-Eye View (5-minute skim)\n"
        "Read the title, abstract, introduction headings, and conclusion. Then answer:\n"
        "- **Category**: What type of paper is this? (empirical study / theoretical / "
        "system design / survey / benchmark / position paper)\n"
        "- **Contribution**: What are the 1-3 main contributions claimed?\n"
        "- **Correctness**: Do the assumptions and claims seem reasonable?\n"
        "- **Clarity**: Is the paper well-written and organized?\n"
        "- **Context**: What prior work does it build on? What field/subfield?\n\n"
        "## Pass 2: Main Ideas (detailed reading)\n"
        "Now read more carefully. For each major section, summarize:\n"
        "- The **problem** being addressed and why it matters\n"
        "- The **proposed approach** or methodology (step by step)\n"
        "- Key **figures, tables, or equations** and what they show\n"
        "- How the ideas **connect** to form the paper's narrative\n\n"
        "## Pass 3: Deep Dive (critical analysis)\n"
        "Now critically evaluate:\n"
        "- **Technical details** that are novel or noteworthy\n"
        "- **Strengths**: What does this paper do particularly well?\n"
        "- **Weaknesses/Limitations**: What are the gaps or concerns?\n"
        "- **Key takeaways**: What should the reader remember?\n"
        "- **Questions for the authors**: What would you ask if you could?\n\n"
        "---\n"
        f"Paper text:\n{truncated[:8000]}"
    )

    chat_model = os.environ.get("CHAT_MODEL", "qwen3:8b")
    print(f"[DEBUG] generate_summary_three_pass: CHAT_MODEL={chat_model}")
    print(f"[DEBUG] prompt length={len(prompt)} chars")

    resp = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
    )

    summary = resp.choices[0].message.content.strip()
    print(f"[DEBUG] summary length={len(summary)} chars")

    return {
        "pass1": summary,
        "pass2": "",
        "pass3": "",
        "full": summary,
    }


def _contextual_summarize(question: str, chunk: dict) -> dict | None:
    """
    PaperQA2-inspired Relevance-scored Contextual Summarization (RCS).

    For each retrieved chunk, ask the LLM to produce a brief summary
    relevant to the question and rate its relevance (0-10). Chunks
    below a threshold are discarded, improving final answer quality.
    """
    client = _get_client()
    title = chunk.get("title", "Unknown")
    section = chunk.get("section", "")
    content = chunk.get("content", "")
    source_label = f"{title}" + (f" / {section}" if section else "")

    system_prompt = (
        "You are a precision-focused research librarian who evaluates whether "
        "a document excerpt is relevant to a specific question. You think "
        "step-by-step before scoring.\n\n"
        "SCORING RUBRIC (use this to determine relevance):\n"
        "- 0-2: Excerpt is completely unrelated to the question\n"
        "- 3-4: Excerpt is tangentially related but does not help answer\n"
        "- 5-6: Excerpt contains some useful background context\n"
        "- 7-8: Excerpt contains information that partially answers the question\n"
        "- 9-10: Excerpt directly and specifically answers the question\n\n"
        "DO NOT:\n"
        "- Give a high score just because the excerpt mentions similar keywords\n"
        "- Summarize parts of the excerpt that are irrelevant to the question\n"
        "- Add information from your own knowledge — only summarize what's in the excerpt"
    )

    prompt = (
        f"QUESTION: \"{question}\"\n\n"
        f"SOURCE: \"{source_label}\"\n\n"
        f"EXCERPT:\n{content[:2000]}\n\n"
        "TASK: First, think about which parts of this excerpt (if any) help "
        "answer the question. Then provide your response in EXACTLY this format:\n\n"
        "Relevance: <score 0-10>\n"
        "Summary: <2-4 sentence summary of ONLY the relevant information>"
    )

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()

        relevance = 5
        summary_text = text
        rel_match = re.search(r"Relevance:\s*(\d+)", text, re.IGNORECASE)
        if rel_match:
            relevance = min(10, int(rel_match.group(1)))
        sum_match = re.search(r"Summary:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        if sum_match:
            summary_text = sum_match.group(1).strip()

        if relevance < 3:
            return None

        return {
            "source": source_label,
            "summary": summary_text,
            "relevance": relevance,
            "content": content,
        }
    except Exception:
        return {
            "source": source_label,
            "summary": content[:500],
            "relevance": 5,
            "content": content,
        }


def get_available_models() -> list[str]:
    """Return the list of chat models configured in CHAT_MODELS env var."""
    raw = os.environ.get("CHAT_MODELS", "")
    if raw.strip():
        return [m.strip() for m in raw.split(",") if m.strip()]
    default = os.environ.get("CHAT_MODEL", "qwen3:8b")
    return [default]


def generate_chat_answer(
    question: str, context_chunks: list[dict],
    source_type: str = "article", source_id: int | None = None,
    model: str | None = None,
) -> str:
    """
    Generate answer using RAG context with:
    - Conversation memory recall (OpenViking-style persistent learning)
    - PaperQA2-style contextual summarization (RCS)
    - Context budget management
    """
    if not context_chunks:
        return "No relevant articles found. Please upload articles in the admin panel first."

    memories = recall_memories(question, source_type, source_id)

    use_rcs = os.environ.get("RAG_USE_RCS", "true").lower() != "false"

    if use_rcs and len(context_chunks) <= 10:
        scored = []
        for c in context_chunks:
            result = _contextual_summarize(question, c)
            if result:
                scored.append(result)

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        scored = scored[:5]

        if scored:
            context = "\n\n---\n\n".join(
                f"[{s['source']}] (relevance: {s['relevance']}/10)\n{s.get('content', s['summary'])}"
                for s in scored
            )
        else:
            context = "\n\n---\n\n".join(
                f"[{c.get('title', 'Unknown')}]\n{c['content']}"
                for c in context_chunks
            )
    else:
        context = "\n\n---\n\n".join(
            f"[{c.get('title', 'Unknown')}]\n{c['content']}"
            for c in context_chunks
        )

    system_prompt = (
        "You are a knowledgeable research assistant helping a scholar understand "
        "academic papers. You answer questions using the EXACT content from the "
        "provided article excerpts.\n\n"
        "APPROACH (think step-by-step):\n"
        "1. Identify which excerpts contain information relevant to the question\n"
        "2. Ground your answer in the exact wording from excerpts — quote directly "
        "in quotation marks for key facts, figures, and findings\n"
        "3. Synthesize across excerpts only when combining multiple sources\n"
        "4. Note any conflicting information between sources\n\n"
        "EXACT CONTENT RULES:\n"
        "- Prefer direct quotes from the excerpts over paraphrasing — accuracy matters\n"
        "- For numbers, statistics, methodology details, or specific claims: use the exact "
        "wording from the excerpt\n"
        "- Paraphrase only for transitions or when exact wording is unclear\n\n"
        "REFERENCE (mandatory for each key point):\n"
        "- End EVERY substantive finding or claim with a reference in this format:\n"
        "  **Ref:** [Author(s)] or [Author(s) / Title] or [Title]\n"
        "- Use author names if they appear in the excerpt (e.g. Smith et al., 2020); "
        "otherwise use the article title or a short title phrase\n"
        "- Place the Ref at the end of the relevant sentence or paragraph\n\n"
        "FORMATTING:\n"
        "- Use clear, structured paragraphs\n"
        "- For multi-part questions, address each part with a sub-heading\n"
        "- Bold key terms or findings for readability\n\n"
        "DO NOT:\n"
        "- Invent information not present in the excerpts\n"
        "- Use phrases like 'based on my knowledge' or 'I think'\n"
        "- Provide a generic answer when excerpts are insufficient — explicitly "
        "state what information is missing\n"
        "- Repeat the question back to the user"
    )

    memory_section = ""
    if memories:
        memory_lines = "\n".join(f"- {m['fact']}" for m in memories)
        memory_section = (
            f"\n\nPAST INSIGHTS (from previous Q&A sessions — use if relevant, "
            f"but prioritize the article excerpts above):\n{memory_lines}\n"
        )

    use_model = model or os.environ.get("CHAT_MODEL", "qwen3:8b")

    client = _get_client()
    resp = client.chat.completions.create(
        model=use_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"ARTICLE EXCERPTS (use exact content; quote directly when stating facts):\n\n"
                    f"{context}\n\n"
                    f"---{memory_section}\n"
                    f"QUESTION: {question}\n\n"
                    "Answer using the exact content from the excerpts above. Quote key facts directly. "
                    "End each key finding with a Ref: [Author(s)] or [Title]."
                ),
            },
        ],
        max_tokens=1200,
    )
    return resp.choices[0].message.content.strip()


def generate_thesis_analysis(full_text: str) -> str:
    """Analyze a thesis/dissertation with structured checklist using CoT."""
    client = _get_client()
    truncated = full_text[:15000] if len(full_text) > 15000 else full_text

    system_prompt = (
        "You are a university thesis examination committee member with expertise "
        "in evaluating graduate research across CS, engineering, and AI/ML. You "
        "perform thorough, systematic reviews.\n\n"
        "APPROACH:\n"
        "- For each section, first scan the thesis text for relevant passages\n"
        "- Quote or paraphrase specific sentences as evidence (cite page if available)\n"
        "- If a section topic is not found, state: '**Not found in the document.**'\n"
        "- Distinguish between what the thesis explicitly states vs. what you infer\n\n"
        "QUALITY STANDARDS:\n"
        "- Be specific: use names of technologies, algorithms, and metrics found in text\n"
        "- Be concise: 2-5 sentences per section, more for Evaluation/Results\n"
        "- Be critical: note both strengths and weaknesses you observe\n\n"
        "DO NOT:\n"
        "- Invent information not present in the thesis text\n"
        "- Give generic filler like 'The thesis discusses methodology thoroughly'\n"
        "- Skip sections — address every numbered section even if content is absent\n"
        "- Add your own recommendations unless under Future Work"
    )

    prompt = (
        "Analyze this thesis/dissertation. For EACH section below, extract and "
        "synthesize the relevant content from the text. Think step-by-step: first "
        "locate the relevant passages, then summarize them.\n\n"
        "## 1. Objective / Research Question\n"
        "What is the main objective or research question? Quote the thesis statement.\n\n"
        "## 2. Importance / Motivation\n"
        "Why does this research matter? What problem does it solve? "
        "Cite the specific justifications given by the author.\n\n"
        "## 3. Literature Review\n"
        "What prior work is referenced? List the key papers/methods mentioned "
        "and how they relate to this thesis.\n\n"
        "## 4. Main Technology / Methodology\n"
        "What technologies, frameworks, languages, or methods are used? "
        "Be specific (e.g., 'TensorFlow 2.x with ResNet-50' not just 'deep learning').\n\n"
        "## 5. System Architecture\n"
        "Describe the system architecture. Include component names, layers, "
        "and how they interact.\n\n"
        "## 6. ERD / Data Design / Class Design\n"
        "Any database schemas, ER diagrams, class hierarchies, or data models?\n\n"
        "## 7. Data Flow\n"
        "How does data move through the system? Describe input → processing → output.\n\n"
        "## 8. Algorithm / Flowchart\n"
        "Any algorithms described? Summarize the key steps. Note any pseudocode.\n\n"
        "## 9. Evaluation / Results\n"
        "This is the most important section. Extract:\n"
        "- Datasets used (name, size, source)\n"
        "- Metrics reported (accuracy, F1, RMSE, etc.) with exact numbers\n"
        "- Comparison with baselines or prior work\n"
        "- Statistical significance if mentioned\n\n"
        "## 10. Application Screenshots\n"
        "Any UI mockups, screenshots, or interface descriptions?\n\n"
        "## 11. Limitations\n"
        "What limitations does the author acknowledge? What limitations do you observe?\n\n"
        "## 12. Future Work\n"
        "What extensions or improvements are suggested?\n\n"
        "---\n"
        f"Thesis text:\n{truncated[:12000]}"
    )

    print(f"[RAG] generate_thesis_analysis: sending to LLM ({len(prompt)} chars)")
    resp = client.chat.completions.create(
        model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3500,
    )
    return resp.choices[0].message.content.strip()


def generate_article_analysis(full_text: str) -> str:
    """Extract structured analysis from a journal article: ratio, gap, discussion, limitation, future direction."""
    client = _get_client()
    truncated = full_text[:15000] if len(full_text) > 15000 else full_text

    system_prompt = (
        "You are an expert academic reviewer. Extract and synthesize specific content "
        "from research articles. Be precise: quote or paraphrase key sentences. "
        "If a section is not found, state: '**Not found in the document.**' "
        "Do not invent content."
    )

    prompt = (
        "Analyze this research article. For EACH section below, extract the relevant content.\n\n"
        "## 1. Ratio of This Article\n"
        "Describe the proportion or balance of sections (e.g. Introduction 15%, Methods 25%, Results 30%, Discussion 20%). "
        "If the paper mentions explicit ratios (e.g. word counts, page distribution), include them. "
        "Otherwise estimate based on section lengths.\n\n"
        "## 2. Gap from Introduction or Literature Review\n"
        "What research gap does the paper identify? What problem or limitation in prior work does it address? "
        "Quote the key statements from the Introduction or Literature Review.\n\n"
        "## 3. Discussion\n"
        "Summarize the main discussion points: interpretation of results, implications, comparisons with prior work.\n\n"
        "## 4. Limitation\n"
        "What limitations does the author acknowledge? What methodological or practical constraints are mentioned?\n\n"
        "## 5. Future Direction\n"
        "What future work or extensions does the paper suggest? Research directions, open questions, or next steps.\n\n"
        "---\n"
        f"Article text:\n{truncated[:12000]}"
    )

    print(f"[RAG] generate_article_analysis: sending to LLM ({len(prompt)} chars)")
    resp = client.chat.completions.create(
        model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2500,
    )
    return resp.choices[0].message.content.strip()


THESIS_COLLECTION = "theses"


def _add_to_rag(
    collection_name: str, id_field: str, item_id: int,
    id_prefix: str, title: str, full_text: str,
    chunk_size: int = 800, overlap: int = 150,
) -> None:
    """Shared logic for adding any document with L0/L1/L2 hierarchy."""
    import time as _time
    t0 = _time.time()
    print(f"[RAG] add to {collection_name}: start ({id_field}={item_id})")

    collection = _get_or_create_collection(collection_name)

    chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=overlap)
    print(f"[RAG] chunked into {len(chunks)} chunks (+{_time.time()-t0:.2f}s)")
    if not chunks:
        return

    try:
        existing = collection.get(where={id_field: item_id}, include=[])
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    embeddings = _embed_chunks(chunks)

    ids = [f"{id_prefix}{item_id}_c{i}" for i in range(len(chunks))]
    metadatas = [
        {
            id_field: item_id,
            "title": title,
            "chunk_idx": i,
            "section": _extract_section_from_chunk(chunks[i]),
            "l0": _generate_l0(chunks[i]),
            "l1": _generate_l1(chunks[i]),
        }
        for i in range(len(chunks))
    ]

    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    print(f"[RAG] add to {collection_name}: DONE total={_time.time()-t0:.2f}s")


def add_thesis_to_rag(thesis_id: int, title: str, full_text: str) -> None:
    """Chunk thesis and add to ChromaDB with section metadata."""
    _add_to_rag(THESIS_COLLECTION, "thesis_id", thesis_id, "t", title, full_text)


def query_theses(question: str, thesis_ids: list[int] | None = None, top_k: int = 5) -> list[dict]:
    """Retrieve relevant chunks from theses collection."""
    return _query_collection(THESIS_COLLECTION, question, "thesis_id", thesis_ids, top_k)


BOOK_COLLECTION = "books"


def add_book_to_rag(book_id: int, title: str, full_text: str) -> None:
    """Chunk book and add to ChromaDB. Uses smaller chunks (500) for long books to enable exact retrieval."""
    _add_to_rag(
        BOOK_COLLECTION, "book_id", book_id, "b",
        title, full_text,
        chunk_size=500,
        overlap=100,
    )


def query_books(question: str, book_ids: list[int] | None = None, top_k: int = 8) -> list[dict]:
    """Retrieve relevant chunks from books collection. Higher top_k for long books."""
    return _query_collection(BOOK_COLLECTION, question, "book_id", book_ids, top_k)


PROJECT_COLLECTION = "projects"


def add_project_file_to_rag(project_file_id: int, title: str, full_text: str) -> None:
    """Chunk a project file, embed, and add to the projects ChromaDB collection."""
    _add_to_rag(PROJECT_COLLECTION, "project_file_id", project_file_id, "pf", title, full_text)


def remove_project_file_from_rag(project_file_id: int) -> None:
    """Remove all vectors for a project file from ChromaDB."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(PROJECT_COLLECTION)
        results = collection.get(where={"project_file_id": project_file_id}, include=[])
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        pass


def query_project(question: str, project_file_ids: list[int], top_k: int = 8) -> list[dict]:
    """Retrieve relevant chunks across all files in a project."""
    if not project_file_ids:
        return []
    return _query_collection(PROJECT_COLLECTION, question, "project_file_id", project_file_ids, top_k)


def generate_project_summary(file_summaries: list[dict]) -> str:
    """Synthesize a combined project overview from individual file summaries."""
    if not file_summaries:
        return ""

    parts = []
    for idx, fs in enumerate(file_summaries, 1):
        parts.append(
            f"### Document {idx}: {fs.get('title', 'Untitled')}\n"
            f"{fs.get('summary', '(no summary)')}"
        )
    combined_input = "\n\n---\n\n".join(parts)

    system_prompt = (
        "You are a senior research program manager who synthesizes findings "
        "from multiple research documents into cohesive project overviews. "
        "You excel at identifying patterns, connections, and gaps across "
        "related papers.\n\n"
        "DO NOT:\n"
        "- Simply concatenate or list the individual summaries\n"
        "- Ignore any document — every document must be referenced at least once\n"
        "- Add external knowledge not present in the summaries\n"
        "- Use filler phrases like 'In conclusion, this project covers various topics'"
    )

    prompt = (
        f"Below are summaries of {len(file_summaries)} documents in a research project.\n\n"
        "TASK: Synthesize a unified project overview. Follow these steps:\n\n"
        "**Step 1 — Identify Themes**: What are the 2-5 major themes or topics "
        "that appear across multiple documents?\n\n"
        "**Step 2 — Map Connections**: How do the documents relate to each other? "
        "Do they build on each other, address different aspects of the same problem, "
        "or use similar methodologies?\n\n"
        "**Step 3 — Note Tensions**: Are there any contradictions, disagreements, "
        "or alternative approaches between documents?\n\n"
        "**Step 4 — Synthesize**: Write a cohesive overview that weaves these "
        "findings together. Use this structure:\n"
        "- **Project Overview**: 2-3 sentence high-level summary\n"
        "- **Key Themes**: The major themes with references to which documents\n"
        "- **Connections**: How the documents relate and build on each other\n"
        "- **Research Gaps**: What's missing or what questions remain\n\n"
        f"---\n\nDOCUMENT SUMMARIES:\n\n{combined_input[:10000]}"
    )

    client = _get_client()
    resp = client.chat.completions.create(
        model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2500,
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Conversation Memory (inspired by OpenViking/ByteDance)
#
# After each Q&A, extract key facts and store them with embeddings.
# Before answering new questions, recall relevant past memories to
# provide continuity across sessions — the system learns over time.
#
# Memory paths (conceptual):
#   memories://article/{id}/facts   - facts learned about an article
#   memories://thesis/{id}/facts    - facts learned about a thesis
#   memories://project/{id}/facts   - facts learned about a project
# ---------------------------------------------------------------------------

MEMORY_COLLECTION = "memories"


def store_memory(
    question: str, answer: str,
    source_type: str = "article", source_id: int | None = None,
) -> None:
    """
    Extract key facts from a Q&A exchange and store them as persistent
    memories that can be recalled in future conversations.
    """
    if not answer or len(answer) < 20:
        return

    use_memory = os.environ.get("RAG_MEMORY", "true").lower() != "false"
    if not use_memory:
        return

    fact_card = _extract_fact_card(question, answer)
    if not fact_card:
        return

    try:
        collection = _get_or_create_collection(MEMORY_COLLECTION)
        embedding = _embed_chunks([fact_card])[0]

        import time
        memory_id = f"mem_{source_type}_{source_id}_{int(time.time())}"

        collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[fact_card],
            metadatas=[{
                "source_type": source_type,
                "source_id": source_id or 0,
                "question": question[:200],
                "created_at": int(time.time()),
            }],
        )
        print(f"[MEMORY] stored: {memory_id} ({len(fact_card)} chars)")
    except Exception as e:
        print(f"[MEMORY] store failed: {e}")


def recall_memories(
    question: str,
    source_type: str | None = None,
    source_id: int | None = None,
    top_k: int = 3,
) -> list[dict]:
    """
    Recall relevant memories from past Q&A sessions. Returns a list of
    past fact cards that are relevant to the current question.
    """
    use_memory = os.environ.get("RAG_MEMORY", "true").lower() != "false"
    if not use_memory:
        return []

    try:
        client = get_chroma_client()
        collection = client.get_collection(name=MEMORY_COLLECTION)
    except Exception:
        return []

    try:
        q_emb = _embed_chunks([question])[0]
    except Exception:
        return []

    where = None
    if source_type and source_id:
        where = {"$and": [
            {"source_type": source_type},
            {"source_id": source_id},
        ]}
    elif source_type:
        where = {"source_type": source_type}

    try:
        results = collection.query(
            query_embeddings=[q_emb],
            n_results=min(top_k, 10),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    memories = []
    for i, doc in enumerate(results["documents"][0]):
        dist = results["distances"][0][i] if results.get("distances") else None
        if dist is not None and dist > 1.5:
            continue
        meta = results["metadatas"][0][i] if results.get("metadatas") else {}
        memories.append({
            "fact": doc,
            "original_question": meta.get("question", ""),
            "distance": dist,
        })

    if memories:
        print(f"[MEMORY] recalled {len(memories)} relevant memories")

    return memories


def _extract_fact_card(question: str, answer: str) -> str:
    """
    Extract a concise fact card from a Q&A pair. Uses a lightweight
    heuristic to avoid an LLM call on every interaction.

    Format: "Q: <question> → <key finding in 1-2 sentences>"
    """
    clean_answer = re.sub(r"\*\*([^*]+)\*\*", r"\1", answer)
    clean_answer = re.sub(r"\[([^\]]+)\]", "", clean_answer)
    clean_answer = re.sub(r"\s+", " ", clean_answer).strip()

    sentences = _SENTENCE_END.split(clean_answer)
    key_sentences = []
    total_len = 0
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 15:
            continue
        skip_phrases = [
            "based on the excerpts", "the context does not",
            "information is missing", "not mentioned in",
            "I cannot", "no relevant",
        ]
        if any(p in s.lower() for p in skip_phrases):
            continue
        key_sentences.append(s)
        total_len += len(s)
        if total_len > 400 or len(key_sentences) >= 3:
            break

    if not key_sentences:
        return ""

    fact = " ".join(key_sentences)
    return f"Q: {question[:150]} → {fact}"


def is_llm_configured() -> bool:
    """Check if LLM/embeddings are configured."""
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL"))
