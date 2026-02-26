import asyncio
import os
from supabase import create_client

from .chunking_service import chunk_text, _token_len
from .embedding_service import embed_batch
from .metadata_service import extract_metadata
from .parsing_service import parse_document

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

_EMBED_BATCH_SIZE = 100  # Max chunks per embedding API call to avoid batch limits


async def process_document(document_id: str, user_id: str, content: bytes, filename: str, mime_type: str):
    """Background task: parse → chunk → embed → store. Updates document status in real-time."""
    try:
        try:
            text_content = await asyncio.to_thread(parse_document, content, filename, mime_type)
        except Exception as e:
            supabase.table("documents").update({
                "status": "failed",
                "error_message": f"Could not parse document: {e}",
            }).eq("id", document_id).execute()
            return

        supabase.table("documents").update({"status": "processing"}).eq("id", document_id).execute()

        chunks = chunk_text(text_content)

        if not chunks:
            supabase.table("documents").update({
                "status": "failed",
                "error_message": "No text content found in document",
            }).eq("id", document_id).execute()
            return

        supabase.table("documents").update({"chunks_total": len(chunks)}).eq("id", document_id).execute()

        embeddings = []
        chunks_done = 0
        for i in range(0, len(chunks), _EMBED_BATCH_SIZE):
            batch = chunks[i:i + _EMBED_BATCH_SIZE]
            embeddings.extend(await embed_batch(batch))
            chunks_done += len(batch)
            supabase.table("documents").update({"chunks_processed": chunks_done}).eq("id", document_id).execute()

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

        metadata = await extract_metadata(text_content)

        supabase.table("documents").update({
            "status": "completed",
            "chunk_count": len(chunks),
            "metadata": metadata,
        }).eq("id", document_id).execute()

    except Exception as e:
        supabase.table("documents").update({
            "status": "failed",
            "error_message": str(e),
        }).eq("id", document_id).execute()
