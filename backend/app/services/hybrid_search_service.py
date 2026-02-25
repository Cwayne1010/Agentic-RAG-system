import os
from typing import Dict, List
from supabase import create_client

from .embedding_service import embed_text

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def hybrid_search(
    query: str,
    top_k: int = 5,
    doc_type_filter: str | None = None,
    alpha: float = 0.5
) -> List[Dict]:
    """
    Hybrid search combining BM25 keyword search and vector similarity search.

    Uses Reciprocal Rank Fusion (RRF) to combine rankings from both methods.

    Args:
        query: Search query text
        top_k: Number of final results to return
        doc_type_filter: Optional document type filter
        alpha: Weight for combining scores (0.0 = all BM25, 1.0 = all vector)

    Returns:
        List of chunks ranked by hybrid score with metadata
    """
    # Fetch larger candidate pools for better fusion
    candidate_count = top_k * 4

    # Run BM25 and vector searches in parallel
    bm25_results = await _bm25_search(query, candidate_count, doc_type_filter)
    vector_results = await _vector_search(query, candidate_count, doc_type_filter)

    # Combine results using RRF
    fused_results = _reciprocal_rank_fusion(
        bm25_results, vector_results, alpha=alpha
    )

    # Apply per-document diversity like current retrieval
    diverse_results = _apply_document_diversity(fused_results, top_k)

    return diverse_results


async def _bm25_search(query: str, top_k: int, doc_type_filter: str | None = None) -> List[Dict]:
    """BM25 full-text search using PostgreSQL's built-in capabilities."""
    params = {
        "query_text": query,
        "match_count": top_k,
    }
    if doc_type_filter:
        params["filter_doc_type"] = doc_type_filter

    result = supabase.rpc("bm25_search_chunks", params).execute()
    chunks = result.data or []

    # Normalize to match vector search format
    for chunk in chunks:
        chunk["id"] = chunk.pop("chunk_id")
        chunk["similarity"] = chunk.pop("bm25_score")
        chunk["search_type"] = "bm25"

    return chunks


async def _vector_search(query: str, top_k: int, doc_type_filter: str | None = None) -> List[Dict]:
    """Vector similarity search using existing pgvector infrastructure."""
    query_embedding = await embed_text(query)

    params = {
        "query_embedding": query_embedding,
        "match_count": top_k,
    }
    if doc_type_filter:
        params["filter_doc_type"] = doc_type_filter

    result = supabase.rpc("match_document_chunks", params).execute()
    chunks = result.data or []

    # Add search type for debugging
    for chunk in chunks:
        chunk["search_type"] = "vector"

    return chunks


def _reciprocal_rank_fusion(
    bm25_results: List[Dict],
    vector_results: List[Dict],
    alpha: float = 0.5,
    k: int = 60
) -> List[Dict]:
    """
    Combine BM25 and vector search results using Reciprocal Rank Fusion (RRF).

    RRF formula: RRF(d) = α * (1/(k + rank_bm25(d))) + (1-α) * (1/(k + rank_vector(d)))

    Args:
        bm25_results: BM25 search results
        vector_results: Vector search results
        alpha: Weight for BM25 vs vector (0.0 = all BM25, 1.0 = all vector)
        k: RRF constant (typically 60)

    Returns:
        Combined results sorted by RRF score
    """
    # Create rank mappings
    bm25_ranks = {chunk["id"]: rank + 1 for rank, chunk in enumerate(bm25_results)}
    vector_ranks = {chunk["id"]: rank + 1 for rank, chunk in enumerate(vector_results)}

    # Collect all unique chunks
    all_chunks = {}
    for chunk in bm25_results + vector_results:
        chunk_id = chunk["id"]
        if chunk_id not in all_chunks:
            all_chunks[chunk_id] = chunk.copy()

    # Calculate RRF scores
    scored_chunks = []
    for chunk_id, chunk in all_chunks.items():
        bm25_rank = bm25_ranks.get(chunk_id, float('inf'))
        vector_rank = vector_ranks.get(chunk_id, float('inf'))

        # RRF formula
        bm25_score = 1.0 / (k + bm25_rank) if bm25_rank != float('inf') else 0
        vector_score = 1.0 / (k + vector_rank) if vector_rank != float('inf') else 0

        rrf_score = alpha * bm25_score + (1 - alpha) * vector_score

        # Add scoring metadata for debugging
        chunk.update({
            "rrf_score": rrf_score,
            "bm25_rank": bm25_rank if bm25_rank != float('inf') else None,
            "vector_rank": vector_rank if vector_rank != float('inf') else None,
            "found_in": []
        })

        if bm25_rank != float('inf'):
            chunk["found_in"].append("bm25")
        if vector_rank != float('inf'):
            chunk["found_in"].append("vector")

        scored_chunks.append(chunk)

    # Sort by RRF score (highest first)
    scored_chunks.sort(key=lambda x: x["rrf_score"], reverse=True)

    return scored_chunks


def _apply_document_diversity(chunks: List[Dict], top_k: int) -> List[Dict]:
    """
    Apply per-document diversity constraint like existing retrieval service.

    Ensures chunks from multiple documents are represented in final results.
    """
    per_doc_limit = 3
    buckets: Dict[str, List[Dict]] = {}

    for chunk in chunks:
        filename = chunk.get("doc_filename", "unknown")
        buckets.setdefault(filename, [])
        if len(buckets[filename]) < per_doc_limit:
            buckets[filename].append(chunk)

    # Interleave: take one chunk from each doc in round-robin order
    diverse: List[Dict] = []
    sources = list(buckets.values())
    i = 0

    while len(diverse) < top_k and sources:
        idx = i % len(sources)
        bucket = sources[idx]
        if bucket:
            diverse.append(bucket.pop(0))
        if not bucket:
            sources.pop(idx)
        else:
            i += 1

    return diverse


async def vector_only_search(
    query: str,
    top_k: int = 5,
    doc_type_filter: str | None = None
) -> List[Dict]:
    """
    Vector-only search for comparison and fallback.

    Maintains compatibility with existing retrieval_service interface.
    """
    return await _vector_search(query, top_k * 4, doc_type_filter)[:top_k]


async def bm25_only_search(
    query: str,
    top_k: int = 5,
    doc_type_filter: str | None = None
) -> List[Dict]:
    """
    BM25-only search for comparison and debugging.
    """
    return await _bm25_search(query, top_k, doc_type_filter)