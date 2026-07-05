import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db
from app.services.skill_store import init_skills
from app.services.conversation_memory import init_memories
from app.services.analysis_service import generate_daily_report, _ensure_dir as ensure_analysis_dir
from app.routers import chat, history, skills, apis, stats, upload, files
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.utils import BEIJING

logger = logging.getLogger(__name__)
app = FastAPI(title="煎蛋Agent API", version="1.0.0")
scheduler = AsyncIOScheduler()

# CORS — 明确列出允许的 origins（不能与 allow_credentials=True 同时使用 "*"）
ALLOWED_ORIGINS = [
    "http://localhost:5173",     # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:8000",     # Backend self (for production build)
    "http://127.0.0.1:8000",
    "null",                      # Electron file:// protocol
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(skills.router)
app.include_router(apis.router)
app.include_router(stats.router)
app.include_router(upload.router)
app.include_router(files.router)


@app.on_event("startup")
def startup():
    init_db()
    init_skills()
    init_memories()
    ensure_analysis_dir()
    # 每日 22:00（北京时间）生成综合分析报告
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=22, minute=0, timezone=BEIJING),
        id="daily_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — daily report at 22:00 Beijing time")


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown(wait=False)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static files in production
def _find_frontend_dist() -> str | None:
    """Resolve frontend dist directory in dev and PyInstaller bundle mode."""
    # PyInstaller bundle: look relative to the executable
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        candidate = os.path.join(sys._MEIPASS, 'frontend', 'dist')
        if os.path.exists(candidate):
            return candidate
    # Dev mode: relative to this file
    candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend', 'dist')
    if os.path.exists(candidate):
        return candidate
    return None


frontend_dir = _find_frontend_dist()
if frontend_dir:
    assets_dir = os.path.join(frontend_dir, 'assets')
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        file_path = os.path.join(frontend_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
