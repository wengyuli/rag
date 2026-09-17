"""Unified asset upload, status, retry and management API.

Document management originally by Guo Lijian; extended for local media ingestion.
"""
import os
from datetime import timezone
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import or_, text
from sqlalchemy.orm import Session, joinedload
from dependencies import get_db, get_current_user
from models import User, DocumentRecord, Workspace
from asset_access import (can_read_asset, can_manage_asset, asset_path,
                          artifacts_path, contained_path, ref_doc_id)

router = APIRouter(prefix="/api/documents", tags=["documents"])
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md"}
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "128")) * 1024 * 1024


def validate_filename(name):
    if not name or len(name.encode("utf-8")) > 240 or any(c in name for c in ("/", "\\")) or any(ord(c) < 32 for c in name):
        raise HTTPException(400, "文件名无效，请使用不含路径的普通文件名（不超过 240 字节）")
    suffix = Path(name).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    raise HTTPException(415, "暂不支持此格式。请上传 PDF、DOCX、PPTX、XLSX、CSV、TXT、MD、JPG、PNG、WEBP 或 MP4/MOV/WEBM/MKV。")


def serialize_asset(doc, workspace_name=None):
    return {
        "id": str(doc.id), "name": doc.filename, "size": doc.file_size,
        "status": doc.processing_status, "progress": doc.processing_progress,
        "stage": doc.processing_stage, "error": doc.processing_error,
        "media_type": doc.media_type, "metadata": doc.media_metadata or {},
        "date": doc.upload_date.strftime("%Y-%m-%d") if doc.upload_date else "",
        "uploaded_at": (doc.upload_date if doc.upload_date.tzinfo else doc.upload_date.replace(tzinfo=timezone.utc)).isoformat() if doc.upload_date else None,
        "isGlobal": doc.is_global, "uploader_id": doc.uploader_id,
        "uploader_name": doc.uploader.username if doc.uploader else "Unknown",
        "workspace_id": doc.workspace_id,
        "workspace_name": workspace_name or ("公共资料库" if doc.is_global else doc.workspace_id),
    }


@router.post("/upload", status_code=202)
def upload_file(file: UploadFile = File(...), is_public: bool = Form(False),
                current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # A synchronous endpoint runs in FastAPI's thread pool. In particular, a
    # same-name PostgreSQL lock must never block the event loop while another
    # upload is waiting to resume reading its spooled request body.
    target = None
    created_directory = False
    commit_started = False
    try:
        media_type = validate_filename(file.filename)
        if is_public:
            if current_user.role != "admin":
                raise HTTPException(403, "只有管理员可以上传公共资料")
            workspace_id = "global"
        else:
            workspace_id = current_user.department_id
            if not workspace_id:
                raise HTTPException(400, "请先分配部门，再上传部门资料")
            if workspace_id == "global" and current_user.role != "admin":
                raise HTTPException(403, "请先分配非公共部门")
        if file.size and file.size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"单个文件不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB")

        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                   {"key": f"asset-upload:{workspace_id}:{file.filename}"})
        if db.query(DocumentRecord.id).filter_by(workspace_id=workspace_id, filename=file.filename).first():
            raise HTTPException(409, "同一资料库已有同名文件，请重命名后上传，或先删除旧资料")
        storage = f"_assets/{uuid.uuid4().hex}/original{Path(file.filename).suffix.lower()}"
        target = contained_path(storage)
        target.parent.mkdir(parents=True, exist_ok=False)
        created_directory = True
        size = 0
        with target.open("xb") as output:
            while block := file.file.read(1024 * 1024):
                size += len(block)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"单个文件不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
                output.write(block)
        if not size:
            raise HTTPException(400, "不能上传空文件")
        doc = DocumentRecord(filename=file.filename, storage_filename=storage,
                             file_size=f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / 1024 / 1024:.2f} MB",
                             workspace_id=workspace_id, is_global=workspace_id == "global",
                             uploader_id=current_user.id, media_type=media_type,
                             processing_status="queued", processing_progress=0,
                             processing_stage="等待解析", media_metadata={"size_bytes": size})
        db.add(doc)
        db.flush()
        # Capture fields before commit expires ORM objects: a refresh failure
        # after a successful commit must not delete the newly queued file.
        response = {"id": str(doc.id), "filename": doc.filename, "status": "queued"}
        commit_started = True
        db.commit()
        return response
    except Exception:
        db.rollback()
        if target is not None and created_directory and not commit_started:
            shutil.rmtree(target.parent, ignore_errors=True)
        # A disconnected commit has an uncertain outcome. Retain the original
        # rather than leave a possibly committed queue record without its file.
        raise
    finally:
        file.file.close()


@router.get("")
def get_documents(workspace_id: str = "global", db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    query = db.query(DocumentRecord, Workspace.name).outerjoin(Workspace, DocumentRecord.workspace_id == Workspace.id)
    query = query.options(joinedload(DocumentRecord.uploader))
    if current_user.role != "admin":
        conditions = [DocumentRecord.is_global.is_(True), DocumentRecord.workspace_id == "global"]
        if current_user.department_id:
            conditions.append(DocumentRecord.workspace_id == current_user.department_id)
        query = query.filter(or_(*conditions))
    return [serialize_asset(doc, name) for doc, name in query.order_by(DocumentRecord.upload_date.desc(), DocumentRecord.id.desc()).all()]


@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.get(DocumentRecord, doc_id)
    if not doc or not can_read_asset(current_user, doc):
        raise HTTPException(404, "资料不存在或无权访问")
    workspace = db.get(Workspace, doc.workspace_id)
    return serialize_asset(doc, workspace.name if workspace else None)


@router.post("/{doc_id}/retry", status_code=202)
def retry_document(doc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentRecord).filter_by(id=doc_id).with_for_update().first()
    if not doc or not can_manage_asset(current_user, doc):
        raise HTTPException(404, "资料不存在或无权管理")
    if doc.processing_status != "failed":
        raise HTTPException(409, "仅处理失败的资料可以重试")
    if not asset_path(doc).is_file():
        raise HTTPException(409, "原文件已不存在，请删除记录并重新上传")
    doc.processing_status = "queued"
    doc.processing_progress = 0
    doc.processing_stage = "等待重试"
    doc.processing_error = None
    db.commit()
    return {"id": str(doc.id), "filename": doc.filename, "status": "queued"}


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentRecord).filter_by(id=doc_id).with_for_update().first()
    if not doc or not can_manage_asset(current_user, doc):
        raise HTTPException(404, "资料不存在或无权管理")
    if doc.processing_status == "processing":
        raise HTTPException(409, "资料正在解析，请等待结束后删除")
    from rag_engine import get_vector_index
    get_vector_index().delete_ref_doc(ref_doc_id(doc), delete_from_docstore=True)
    path, artifacts = asset_path(doc), artifacts_path(doc)
    new_storage = bool(doc.storage_filename)
    db.delete(doc)
    db.commit()
    if new_storage:
        shutil.rmtree(path.parent, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)
        shutil.rmtree(artifacts, ignore_errors=True)
    return {"status": "success", "msg": "资料和检索索引已删除"}
