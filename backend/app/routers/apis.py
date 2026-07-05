from fastapi import APIRouter
from app.models.api_config import ApiConfigCreate, ApiConfigUpdate, ApiTestRequest, ApiTestResult
from app.services.deepseek_service import test_connection
from app.services import config_file

router = APIRouter(prefix="/api/apis")


def _cfg_to_item(cfg: dict) -> dict:
    """Convert config.json dict to the response format the frontend expects."""
    key = cfg.get("api_key", "")
    masked = key[:8] + "..." if len(key) > 8 else ""
    return {
        "id": "file",
        "name": "DeepSeek API",
        "provider": "deepseek",
        "api_key": masked,
        "base_url": cfg.get("base_url", "https://api.deepseek.com"),
        "model": cfg.get("model", "deepseek-v4-flash"),
        "is_active": True,
        "created_at": "",
    }


@router.get("")
def list_api_configs():
    cfg = config_file.read_config()
    if cfg:
        return [_cfg_to_item(cfg)]
    return []


@router.post("")
def create_api_config(body: ApiConfigCreate):
    config_file.write_config(api_key=body.api_key, base_url=body.base_url, model=body.model)
    return _cfg_to_item(config_file.read_config())


@router.put("/{config_id}")
def update_api_config(config_id: str, body: ApiConfigUpdate):
    cfg = config_file.read_config() or {}
    new_key = body.api_key if body.api_key is not None else cfg.get("api_key", "")
    new_url = body.base_url if body.base_url is not None else cfg.get("base_url", "https://api.deepseek.com")
    new_model = body.model if body.model is not None else cfg.get("model", "deepseek-v4-flash")
    config_file.write_config(api_key=new_key, base_url=new_url, model=new_model)
    return {"success": True}


@router.delete("/{config_id}")
def delete_api_config(config_id: str):
    config_file.clear_config()
    return {"success": True}


@router.patch("/{config_id}/activate")
def activate_api_config(config_id: str):
    return {"success": True, "is_active": True}


@router.post("/test", response_model=ApiTestResult)
def test_api_connection(body: ApiTestRequest):
    success, latency, error = test_connection(body.api_key, body.base_url, body.model)
    return ApiTestResult(success=success, latency_ms=latency, error=error)
