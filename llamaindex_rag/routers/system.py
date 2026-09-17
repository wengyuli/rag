"""Administrator-only resource monitoring; requests only read cached samples."""
from fastapi import APIRouter, Depends, Response
from dependencies import get_current_admin
from system_metrics import get_metrics_snapshot

router = APIRouter(prefix="/api/system", tags=["系统资源"])


@router.get("/metrics")
async def resource_metrics(response: Response, _admin=Depends(get_current_admin)):
    response.headers["Cache-Control"] = "no-store"
    return get_metrics_snapshot()
