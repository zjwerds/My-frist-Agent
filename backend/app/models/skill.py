from pydantic import BaseModel


class SkillToggle(BaseModel):
    enabled: bool
