"""Shared authorization and contained on-disk locations for library assets."""
import os
from pathlib import Path
from fastapi import HTTPException


def files_root():
    return Path(os.environ.get("FILES_ROOT", "./files")).resolve()


def can_read_asset(user, doc):
    return bool(user.role == "admin" or doc.is_global or doc.workspace_id == "global"
                or (user.department_id and user.department_id == doc.workspace_id))


def can_manage_asset(user, doc):
    return bool(user.role == "admin" or (not doc.is_global and doc.workspace_id != "global"
                and user.department_id and user.department_id == doc.workspace_id))


def contained_path(relative):
    root = files_root()
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise HTTPException(400, "文件路径无效")
    return target


def asset_path(doc):
    relative = doc.storage_filename or f"{doc.workspace_id}/{doc.filename}"
    return contained_path(relative)


def artifacts_path(doc):
    if doc.storage_filename:
        return contained_path(str(Path(doc.storage_filename).parent / "artifacts"))
    return contained_path(f"_artifacts/{doc.id}")


def ref_doc_id(doc):
    return f"asset:{doc.id}" if doc.storage_filename else f"{doc.workspace_id}_{doc.filename}"
