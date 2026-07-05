from fastapi import APIRouter, HTTPException
from app.models.skill import SkillToggle
from app.services import skill_store
from app.services import config_file

router = APIRouter(prefix="/api/skills")


@router.get("")
def list_skills():
    skills = skill_store.list_skills()
    # Filter out hidden skills (built-in function tools shown only in chat, not sidebar)
    visible = [s for s in skills if not s.get("hidden")]
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "category": s["category"],
            "enabled": s["enabled"],
            "builtin": s["builtin"],
            "config": s.get("config"),
        }
        for s in visible
    ]


@router.post("/auto-categorize")
async def auto_categorize():
    """Use AI to classify skills that the keyword matcher couldn't."""
    cfg = config_file.read_config()
    if not cfg or not cfg.get("api_key"):
        raise HTTPException(400, "请先配置 API Key 以使用 AI 自动分类")
    count = await skill_store.auto_categorize_ai(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url", "https://api.deepseek.com"),
        model=cfg.get("model", "deepseek-v4-flash"),
    )
    return {"reclassified": count}


@router.patch("/{skill_id}/toggle")
def toggle_skill(skill_id: str, body: SkillToggle):
    skill = skill_store.toggle_skill(skill_id, body.enabled)
    if not skill:
        return {"error": "Skill not found"}, 404
    return {"id": skill["id"], "enabled": skill["enabled"]}


@router.delete("/{skill_id}")
def remove_skill(skill_id: str):
    success = skill_store.remove_skill(skill_id)
    return {"success": success}
