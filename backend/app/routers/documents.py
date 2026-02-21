import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import create_client

from app.dependencies import get_current_user
from app.models.document import DocumentResponse
from app.services.ingestion_service import process_document

router = APIRouter()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

ALLOWED_MIME_TYPES = {"text/plain", "text/markdown"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), user=Depends(get_current_user)):
    # Allow text/plain and text/markdown; also handle .md files which browsers may label as text/plain
    if file.content_type not in ALLOWED_MIME_TYPES and not (
        file.filename and file.filename.endswith(".md")
    ):
        raise HTTPException(400, detail="Only .txt and .md files are supported")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, detail="File too large (max 10MB)")

    text_content = content.decode("utf-8")

    # Upload raw file to Supabase Storage
    storage_path = f"{user.id}/{file.filename}"
    supabase.storage.from_("documents").upload(
        storage_path,
        content,
        {"content-type": file.content_type or "text/plain"},
    )

    # Create document record (status starts as pending)
    result = supabase.table("documents").insert({
        "user_id": str(user.id),
        "filename": file.filename,
        "file_path": storage_path,
        "file_size": len(content),
        "mime_type": file.content_type or "text/plain",
        "status": "pending",
    }).execute()

    document = result.data[0]

    # Kick off background ingestion (chunk → embed → store)
    asyncio.create_task(process_document(document["id"], str(user.id), text_content))

    return document


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(user=Depends(get_current_user)):
    result = (
        supabase.table("documents")
        .select("*")
        .eq("user_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, user=Depends(get_current_user)):
    doc = (
        supabase.table("documents")
        .select("file_path")
        .eq("id", document_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from storage
    supabase.storage.from_("documents").remove([doc.data[0]["file_path"]])

    # Delete from DB (chunks cascade via FK)
    supabase.table("documents").delete().eq("id", document_id).eq("user_id", str(user.id)).execute()

    return {"deleted": True}
