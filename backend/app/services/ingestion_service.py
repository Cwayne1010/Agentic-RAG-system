import os
from supabase import create_client

from .chunking_service import chunk_text, _token_len
from .embedding_service import embed_batch

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def process_document(document_id: str, user_id: str, text_content: str):
    """Background task: chunk → embed → store. Updates document status in real-time."""
    try:
        supabase.table("documents").update({"status": "processing"}).eq("id", document_id).execute()

        chunks = chunk_text(text_content)

        if not chunks:
            supabase.table("documents").update({
                "status": "failed",
                "error_message": "No text content found in document",
            }).eq("id", document_id).execute()
            return

        embeddings = await embed_batch(chunks)

        rows = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "chunk_index": i,
                "content": chunk,
                "embedding": embedding,
                "token_count": _token_len(chunk),
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        supabase.table("document_chunks").insert(rows).execute()

        supabase.table("documents").update({
            "status": "completed",
            "chunk_count": len(chunks),
        }).eq("id", document_id).execute()

    except Exception as e:
        supabase.table("documents").update({
            "status": "failed",
            "error_message": str(e),
        }).eq("id", document_id).execute()
