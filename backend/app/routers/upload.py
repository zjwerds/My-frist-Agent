"""File upload & parse router — accept docx/xlsx/pdf, return extracted text."""

import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_parser_service import parse_file

router = APIRouter(prefix="/api/upload")

# File size limits
MAX_FILE_SIZE = {
    "pdf": 50 * 1024 * 1024,      # 50 MB
    "docx": 20 * 1024 * 1024,     # 20 MB
    "doc": 20 * 1024 * 1024,      # 20 MB
    "xlsx": 20 * 1024 * 1024,     # 20 MB
    "xls": 20 * 1024 * 1024,      # 20 MB
}

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "xlsx", "xls"}


def _get_ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/parse-file")
async def upload_parse_file(file: UploadFile = File(...)):
    """Upload a document and get its extracted text content.

    - Accepts: PDF, DOCX, DOC, XLSX, XLS
    - Returns: extracted text + metadata (pages, rows, etc.)
    - File is NOT persisted — only parsed in memory.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = _get_ext(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式: .{ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Stream-read with size limit check
    max_size = MAX_FILE_SIZE.get(ext, 10 * 1024 * 1024)
    file_bytes = b""
    while True:
        chunk = await file.read(64 * 1024)  # 64KB chunks
        if not chunk:
            break
        file_bytes += chunk
        if len(file_bytes) > max_size:
            max_mb = max_size // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"文件过大（{len(file_bytes) / 1024 / 1024:.1f} MB），.{ext} 限制为 {max_mb} MB",
            )

    # Parse
    start = time.time()
    result = parse_file(file_bytes, file.filename)
    elapsed = round((time.time() - start) * 1000)

    result["time_ms"] = elapsed

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result
