"""Serial, durable ingestion worker backed by the documents table.

A PostgreSQL advisory lock gives one worker ownership. Interrupted jobs are
requeued on startup; partial vector inserts are removed before every attempt.
"""
import logging
import os
import threading
from sqlalchemy import text
from database import engine, SessionLocal
from models import DocumentRecord
from asset_access import asset_path, artifacts_path, ref_doc_id
from media_extract import MediaExtractionError

logger = logging.getLogger(__name__)
_stop = threading.Event()
_thread = None
WORKER_LOCK = 81734002


def extract_document(path, filename, artifacts, progress):
    from media_extract import MediaChunk, ExtractionResult, extract_media
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import fitz
        chunks, warnings, scanned = [], [], 0
        with fitz.open(path) as pdf:
            if pdf.needs_pass:
                raise MediaExtractionError("PDF 已加密，请先解密后上传")
            if len(pdf) > int(os.environ.get("PDF_MAX_PAGES", "200")):
                raise MediaExtractionError("PDF 超过 200 页，请拆分后上传")
            ocr_pages = sum(len(page.get_text().strip()) < 30 for page in pdf)
            if ocr_pages > int(os.environ.get("PDF_MAX_OCR_PAGES", "20")):
                raise MediaExtractionError("扫描 PDF 超过 20 页，请拆分后上传，以控制本地解析耗时")
            for number, page in enumerate(pdf, 1):
                content = page.get_text().strip()
                if len(content) < 30:
                    scanned += 1
                    progress(10 + int(60 * (number - 1) / max(len(pdf), 1)), f"识别扫描页 {number}/{len(pdf)}")
                    page_dir = artifacts / f"page-{number}"
                    page_dir.mkdir(parents=True, exist_ok=True)
                    image_path = page_dir / "page.png"
                    page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(image_path)
                    result = extract_media(image_path, f"{filename} 第 {number} 页.png", page_dir,
                                           lambda _percent, _stage: None)
                    content = "\n".join(chunk.text for chunk in result.chunks)
                    warnings.extend(result.metadata.get("warnings", []))
                if content:
                    chunks.append(MediaChunk(f"资料：{filename}，第 {number} 页\n{content}",
                                             {"media_type": "document", "source_kind": "document",
                                              "page": number, "page_label": str(number)}))
                progress(10 + int(60 * number / max(len(pdf), 1)), f"已读取 {number}/{len(pdf)} 页")
            if scanned:
                warnings.append(f"{scanned} 页使用视觉模型识别，数字、表格和小字请核对原文。")
            return ExtractionResult(chunks, {"page_count": len(pdf), "ocr_pages": scanned,
                                             "warnings": list(dict.fromkeys(warnings))})
    if suffix in {".txt", ".md"}:
        content = path.read_text(encoding="utf-8-sig")
        return ExtractionResult([MediaChunk(content, {"media_type": "document", "source_kind": "document"})], {})
    from llama_index.core import SimpleDirectoryReader
    from llama_index.readers.file import DocxReader, PptxReader, PandasExcelReader, PandasCSVReader
    readers = {".docx": DocxReader(), ".pptx": PptxReader(),
               ".xlsx": PandasExcelReader(pandas_config={"header": 0}), ".csv": PandasCSVReader()}
    documents = SimpleDirectoryReader(input_files=[str(path)], file_extractor=readers, raise_on_error=True).load_data()
    chunks = []
    for doc in documents:
        metadata = {"media_type": "document", "source_kind": "document"}
        for key in ("page_label", "page", "sheet_name"):
            if key in doc.metadata:
                metadata[key] = doc.metadata[key]
        chunks.append(MediaChunk(doc.text, metadata))
    return ExtractionResult(chunks, {})


def _update(doc_id, **values):
    with SessionLocal() as db:
        db.query(DocumentRecord).filter_by(id=doc_id).update(values)
        db.commit()


def process_asset(doc_id, ownership_check=None):
    reference = None
    index = None

    def check_ownership():
        if _stop.is_set():
            raise InterruptedError("服务停止，等待重启后继续")
        if ownership_check is not None:
            ownership_check()

    def progress(percent, stage):
        check_ownership()
        _update(doc_id, processing_progress=min(85, max(1, int(percent))), processing_stage=stage)

    try:
        from media_extract import extract_media
        from llama_index.core import Document
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
        from rag_engine import get_vector_index
        with SessionLocal() as db:
            doc = db.get(DocumentRecord, doc_id)
            if not doc or doc.processing_status != "processing":
                return
            reference = ref_doc_id(doc)
            path, artifacts = asset_path(doc), artifacts_path(doc)
            filename, media_type, workspace = doc.filename, doc.media_type, doc.workspace_id
            metadata = dict(doc.media_metadata or {})
        check_ownership()
        artifacts.mkdir(parents=True, exist_ok=True)
        index = get_vector_index()
        index.delete_ref_doc(reference, delete_from_docstore=True)
        progress(3, "读取原始资料")
        result = (extract_media(path, filename, artifacts, progress) if media_type in {"image", "video"}
                  else extract_document(path, filename, artifacts, progress))
        check_ownership()
        nonempty = [chunk for chunk in result.chunks if chunk.text and chunk.text.strip()]
        if not nonempty or sum(len(chunk.text.strip()) for chunk in nonempty) < 10:
            raise MediaExtractionError("没有提取到可检索的内容，请检查文件是否损坏或内容是否清晰")
        documents = []
        for chunk in nonempty:
            tags = {**chunk.metadata, "document_id": doc_id, "file_name": filename,
                    "workspace_id": workspace, "is_global": str(workspace == "global").lower(),
                    "file_key": reference, "media_type": media_type}
            hidden = ["document_id", "workspace_id", "is_global", "file_key", "source_kind"]
            documents.append(Document(text=chunk.text, metadata=tags,
                                      excluded_llm_metadata_keys=hidden, excluded_embed_metadata_keys=hidden))
        nodes = SentenceSplitter(chunk_size=512, chunk_overlap=50).get_nodes_from_documents(documents)
        for i, node in enumerate(nodes):
            node.id_ = f"{reference}:chunk:{i}"
            node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=reference)
        metadata.update(result.metadata)
        metadata["chunk_count"] = len(nodes)
        metadata.setdefault("summary", nonempty[0].text[:280])
        check_ownership()
        _update(doc_id, media_metadata=metadata, processing_stage="生成检索索引", processing_progress=88)
        index.insert_nodes(nodes)
        check_ownership()
        _update(doc_id, processing_status="indexed", processing_progress=100,
                processing_stage="已入库", processing_error=None)
        logger.info("Asset %s indexed: %s chunks", doc_id, len(nodes))
    except InterruptedError:
        # Keep processing status; ownership recovery will requeue this record.
        logger.info("Ingestion interrupted for asset %s", doc_id)
    except Exception as exc:
        logger.exception("Ingestion failed for asset %s", doc_id)
        try:
            check_ownership()
        except InterruptedError:
            return
        if index is not None and reference is not None:
            try:
                index.delete_ref_doc(reference, delete_from_docstore=True)
            except Exception:
                logger.exception("Partial index cleanup deferred until retry for asset %s", doc_id)
        # Only deliberately user-facing extraction errors are safe to display;
        # arbitrary parser ValueError messages can include local paths or data.
        safe_error = (str(exc)[:400] if isinstance(exc, MediaExtractionError)
                      else "解析失败，请检查格式、模型服务和后台日志后重试")
        _update(doc_id, processing_status="failed", processing_stage="处理失败", processing_error=safe_error)


def _recover_interrupted():
    with SessionLocal() as db:
        db.query(DocumentRecord).filter_by(processing_status="processing").update({
            "processing_status": "queued", "processing_stage": "重启后继续解析",
            "processing_progress": 0, "processing_error": None})
        db.commit()


def _claim_next():
    with SessionLocal() as db:
        doc = db.query(DocumentRecord).filter_by(processing_status="queued").order_by(
            DocumentRecord.id).with_for_update(skip_locked=True).first()
        doc_id = doc.id if doc else None
        if doc:
            doc.processing_status = "processing"
            doc.processing_stage = "开始解析"
            doc.processing_progress = 0
            doc.processing_error = None
            db.commit()
        return doc_id


def _check_worker_lock(connection):
    # SELECT 1 alone can succeed after a pooled connection silently reconnects,
    # even though its session-level advisory lock was lost with the old session.
    try:
        owned = connection.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
            "AND pid = pg_backend_pid() AND classid = 0 AND objid = :key "
            "AND objsubid = 1 AND granted)"), {"key": WORKER_LOCK}).scalar()
        connection.commit()
    except Exception as exc:
        raise InterruptedError("任务锁连接已断开，等待重新接管") from exc
    if not owned:
        raise InterruptedError("任务锁已丢失，等待重新接管")


def _worker():
    while not _stop.is_set():
        try:
            with engine.connect() as lock_connection:
                owned = lock_connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}).scalar()
                lock_connection.commit()
                if not owned:
                    _stop.wait(3)
                    continue
                try:
                    _recover_interrupted()
                    while not _stop.is_set():
                        _check_worker_lock(lock_connection)
                        doc_id = _claim_next()
                        if doc_id is None:
                            _stop.wait(2)
                        else:
                            process_asset(doc_id, lambda: _check_worker_lock(lock_connection))
                finally:
                    lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
                    lock_connection.commit()
        except Exception:
            logger.exception("Ingestion worker will reconnect")
            _stop.wait(5)


def start_worker():
    global _thread
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_worker, name="media-ingestion", daemon=True)
        _thread.start()


def stop_worker():
    _stop.set()
    if _thread:
        _thread.join(timeout=5)
