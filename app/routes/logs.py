from fastapi import APIRouter, Query
from typing import Optional
from app.storage.history_store import history_store

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def list_logs(
    flow_id: Optional[str] = Query(None, description="按流程 ID 过滤"),
    status: Optional[str] = Query(None, description="按状态过滤: success / error"),
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
):
    records = history_store.list(flow_id=flow_id, status=status, limit=limit)
    return {"total": len(records), "records": records}


@router.get("/{run_id}")
async def get_log(run_id: str):
    record = history_store.get(run_id)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"执行记录不存在：{run_id}")
    return record
