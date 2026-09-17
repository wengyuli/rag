"""Authenticated original-file and thumbnail delivery.

Author: Guo Lijian
Local changes: resolve assets through database records and enforce workspace access.
"""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from asset_access import asset_path, artifacts_path, can_read_asset
from dependencies import get_db, get_current_user
from models import DocumentRecord, User


router = APIRouter(prefix="/api/files", tags=["file"])
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}


def _readable_document(doc_id: int, db: Session, user: User) -> DocumentRecord:
    document = db.query(DocumentRecord).filter(DocumentRecord.id == doc_id).first()
    if document is None or not can_read_asset(user, document):
        # Do not reveal another department's asset existence.
        raise HTTPException(404, "文件不存在或无权访问")
    return document


def _original_response(document: DocumentRecord):
    try:
        path = asset_path(document)
    except (ValueError, OSError):
        raise HTTPException(404, "文件未找到") from None
    if not path.is_file():
        raise HTTPException(404, "文件未找到")

    suffix = Path(document.filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        try:
            return {"type": "text", "content": path.read_text(encoding="utf-8")}
        except UnicodeDecodeError:
            pass

    media_type = mimetypes.guess_type(document.filename)[0] or "application/octet-stream"
    inline = media_type.startswith(("image/", "video/")) or media_type == "application/pdf"
    # FileResponse reads Range / If-Range from the ASGI request scope and streams
    # the requested bytes; never load an entire video into application memory.
    return FileResponse(
        path,
        media_type=media_type,
        filename=document.filename,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/assets/{doc_id}")
async def get_asset(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve an authorized original, including HTTP Range requests for video."""
    return _original_response(_readable_document(doc_id, db, current_user))


@router.get("/assets/{doc_id}/thumbnail")
async def get_asset_thumbnail(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _readable_document(doc_id, db, current_user)
    try:
        directory = artifacts_path(document).resolve()
        thumbnail = (directory / "thumbnail.jpg").resolve()
        if thumbnail.parent != directory or not thumbnail.is_file():
            raise HTTPException(404, "缩略图尚未生成")
    except (ValueError, OSError):
        raise HTTPException(404, "缩略图尚未生成") from None
    return FileResponse(
        thumbnail,
        media_type="image/jpeg",
        filename="thumbnail.jpg",
        content_disposition_type="inline",
    )


# Keep this compatibility route after explicit asset routes.
@router.get("/{filename}")
async def get_file_content(
    filename: str,
    doc_workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(DocumentRecord).filter(
        DocumentRecord.filename == filename,
        DocumentRecord.workspace_id == doc_workspace_id,
    ).first()
    if document is None or not can_read_asset(current_user, document):
        raise HTTPException(404, "文件不存在或无权访问")
    return _original_response(document)
