from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_size: int
    mime_type: str
    status: str
    error_message: str | None = None
    chunk_count: int | None = None
    content_hash: str | None = None
    created_at: datetime
    updated_at: datetime
