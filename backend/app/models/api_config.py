from pydantic import BaseModel


class ApiConfigCreate(BaseModel):
    name: str
    provider: str = "deepseek"
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"


class ApiConfigUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class ApiConfigOut(BaseModel):
    id: str
    name: str
    provider: str
    api_key: str
    base_url: str
    model: str
    is_active: bool
    created_at: str


class ApiTestRequest(BaseModel):
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"


class ApiTestResult(BaseModel):
    success: bool
    latency_ms: int
    error: str | None = None
