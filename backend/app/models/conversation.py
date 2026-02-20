from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class ConversationCreate(BaseModel):
    title: str = "New Chat"


class ConversationUpdate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
