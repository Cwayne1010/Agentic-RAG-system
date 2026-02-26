import os
from supabase import create_client

from .embedding_service import embed_text
from .hybrid_search_service import hybrid_search, vector_only_search

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def search(
    query: str,
    top_k: int = 5,
    doc_type_filter: str | None = None,
    search_mode: str = "hybrid",
    user_id: str | None = None,
) -> list[dict]:
    """
    Search using hybrid (BM25 + vector) or vector-only approaches.

    Args:
        query: Search query text
        top_k: Number of results to return
        doc_type_filter: Optional document type filter
        search_mode: "hybrid" (default), "vector", or "keyword"
        user_id: User ID for scoping results

    Returns:
        List of ranked chunks with metadata and search provenance
    """
    if search_mode == "hybrid":
        return await hybrid_search(query, top_k, doc_type_filter, user_id=user_id)
    elif search_mode == "vector":
        return await vector_only_search(query, top_k, doc_type_filter, user_id=user_id)
    else:
        # Fallback to hybrid for any other mode
        return await hybrid_search(query, top_k, doc_type_filter, user_id=user_id)


async def fetch_all_chunks_by_document(user_id: str) -> dict[str, list[dict]]:
    """Fetch all document chunks for a specific user, grouped by document_id."""
    result = supabase.table("document_chunks").select(
        "id, content, chunk_index, document_id, documents(filename, metadata)"
    ).eq("user_id", user_id).execute()

    chunks_by_doc: dict[str, list[dict]] = {}
    for chunk in result.data or []:
        doc_id = chunk["document_id"]
        if doc_id not in chunks_by_doc:
            chunks_by_doc[doc_id] = []
        # Flatten the joined data for compatibility
        chunk_flat = {
            **chunk,
            "doc_filename": chunk["documents"]["filename"],
            "doc_metadata": chunk["documents"]["metadata"]
        }
        del chunk_flat["documents"]  # Remove the nested structure
        chunks_by_doc[doc_id].append(chunk_flat)

    return chunks_by_doc


async def find_document_id_by_filename(filename: str, user_id: str) -> str | None:
    """Look up the document_id for a completed document by filename, scoped to user."""
    result = supabase.table("documents").select("id").eq(
        "filename", filename
    ).eq("user_id", user_id).eq("status", "completed").limit(1).execute()
    rows = result.data or []
    return rows[0]["id"] if rows else None


async def fetch_document_context(document_id: str, user_id: str) -> str | None:
    """
    Fetch all chunks for a specific document owned by user_id and concatenate
    them in chunk_index order. Returns None if not found or not owned by user.
    """
    doc_result = supabase.table("documents").select("id, filename").eq(
        "id", document_id
    ).eq("user_id", user_id).execute()
    if not doc_result.data:
        return None

    result = supabase.table("document_chunks").select(
        "content, chunk_index, documents(filename)"
    ).eq("document_id", document_id).execute()
    chunks = result.data or []
    if not chunks:
        return None

    sorted_chunks = sorted(chunks, key=lambda c: c.get("chunk_index", 0))
    doc_filename = sorted_chunks[0]["documents"]["filename"] if sorted_chunks[0]["documents"] else "document"
    parts = [f"[Document: {doc_filename}]"]
    for c in sorted_chunks:
        parts.append(f"[Chunk {c['chunk_index']}]\n{c['content']}")
    return "\n\n".join(parts)
