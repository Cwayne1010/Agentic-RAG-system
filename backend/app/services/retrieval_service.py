import os
from supabase import create_client

from .embedding_service import embed_text

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def search(query: str, user_id: str, top_k: int = 5) -> list[dict]:
    """Vector similarity search using pgvector cosine distance via Supabase RPC."""
    query_embedding = await embed_text(query)

    result = supabase.rpc("match_document_chunks", {
        "query_embedding": query_embedding,
        "match_user_id": user_id,
        "match_count": top_k,
    }).execute()

    return result.data or []
