import os
from supabase import create_client

from .embedding_service import embed_text
from .hybrid_search_service import hybrid_search, vector_only_search

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def search(
    query: str,
    top_k: int = 5,
    doc_type_filter: str | None = None,
    search_mode: str = "hybrid"
) -> list[dict]:
    """
    Search using hybrid (BM25 + vector) or vector-only approaches.

    Args:
        query: Search query text
        top_k: Number of results to return
        doc_type_filter: Optional document type filter
        search_mode: "hybrid" (default), "vector", or "keyword"

    Returns:
        List of ranked chunks with metadata and search provenance
    """
    if search_mode == "hybrid":
        return await hybrid_search(query, top_k, doc_type_filter)
    elif search_mode == "vector":
        return await vector_only_search(query, top_k, doc_type_filter)
    else:
        # Fallback to hybrid for any other mode
        return await hybrid_search(query, top_k, doc_type_filter)


async def fetch_all_chunks_by_document() -> dict[str, list[dict]]:
    """Fetch all document chunks from the global corpus, grouped by document_id."""
    result = supabase.table("document_chunks").select(
        "id, content, doc_filename, chunk_index, document_id, doc_metadata"
    ).execute()

    chunks_by_doc: dict[str, list[dict]] = {}
    for chunk in result.data or []:
        doc_id = chunk["document_id"]
        if doc_id not in chunks_by_doc:
            chunks_by_doc[doc_id] = []
        chunks_by_doc[doc_id].append(chunk)

    return chunks_by_doc
