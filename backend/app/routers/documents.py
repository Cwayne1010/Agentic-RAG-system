import asyncio
import hashlib
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import create_client

from app.dependencies import get_current_user
from app.models.document import DocumentResponse
from app.services.ingestion_service import process_document

router = APIRouter()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

ALLOWED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/html",
}
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail="Unsupported file type. Accepted: PDF, DOCX, HTML, TXT, MD")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, detail="File too large (max 10MB)")

    # --- Record Manager: compute SHA-256 hash of raw file bytes ---
    content_hash = hashlib.sha256(content).hexdigest()

    # 1. Reject exact duplicate: same content already ingested anywhere in the corpus
    existing = (
        supabase.table("documents")
        .select("id, filename")
        .eq("content_hash", content_hash)
        .eq("status", "completed")
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate: this content already exists as '{existing.data[0]['filename']}'"
        )

    # 2. Incremental update: same filename exists → delete old document + chunks (cascade via FK)
    same_name = (
        supabase.table("documents")
        .select("id, file_path")
        .eq("user_id", str(user.id))
        .eq("filename", file.filename)
        .execute()
    )
    if same_name.data:
        old = same_name.data[0]
        try:
            supabase.storage.from_("documents").remove([old["file_path"]])
        except Exception:
            pass  # Storage file may already be gone; DB delete is what matters
        supabase.table("documents").delete().eq("id", old["id"]).eq("user_id", str(user.id)).execute()

    # Upload new file to Supabase Storage
    storage_path = f"{user.id}/{uuid.uuid4()}/{file.filename}"
    try:
        supabase.storage.from_("documents").upload(
            storage_path,
            content,
            {"content-type": file.content_type or "text/plain"},
        )
    except Exception as e:
        raise HTTPException(400, detail=f"Storage upload failed: {e}")

    # Create document record with content_hash (status starts as pending)
    result = supabase.table("documents").insert({
        "user_id": str(user.id),
        "filename": file.filename,
        "file_path": storage_path,
        "file_size": len(content),
        "mime_type": file.content_type or "text/plain",
        "status": "parsing",
        "content_hash": content_hash,
    }).execute()

    document = result.data[0]

    # Kick off background ingestion (parse → chunk → embed → store)
    asyncio.create_task(
        process_document(document["id"], str(user.id), content, file.filename or "", file.content_type or "")
    )

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
