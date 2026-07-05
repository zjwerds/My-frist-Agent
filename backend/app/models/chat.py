from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    images: list[str] = []  # base64 data URIs
    temperature: float | None = None
    edit_mode: bool = False


class MessageOut(BaseModel):
    id: str
    role: str
    content: str | None = None
    tool_calls: str | None = None
    created_at: str
