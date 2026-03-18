from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from typing import Any, Dict, List, Optional
from app.models.result import FlowRunResult, FlowSummary
from app.storage.flow_store import flow_store
from app.engine.flow_engine import run_flow
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("", response_model=List[FlowSummary])
async def list_flows():
    flows = flow_store.list_flows()
    return [
        FlowSummary(
            id=f.id,
            name=f.name,
            description=f.description,
            parameter_count=len(f.parameters),
            has_auth=f.auth is not None,
        )
        for f in flows
    ]


@router.get("/{flow_id}")
async def get_flow(flow_id: str):
    flow = flow_store.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail=f"流程不存在：{flow_id}")
    return flow


@router.get("/{flow_id}/schema")
async def get_flow_schema(flow_id: str):
    """获取流程参数 Schema，便于调用方了解必填参数"""
    flow = flow_store.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail=f"流程不存在：{flow_id}")
    return {
        "flow_id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "has_auth": flow.auth is not None,
        "parameters": [p.model_dump() for p in flow.parameters],
        "example_request": {
            p.name: p.example or p.default
            for p in flow.parameters
        },
    }


@router.post("/{flow_id}/run", response_model=FlowRunResult)
async def run_flow_endpoint(flow_id: str, body: Dict[str, Any] = Body(default={})):
    flow = flow_store.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail=f"流程不存在：{flow_id}")

    missing = [
        p.name for p in flow.parameters
        if p.required and p.name not in body
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"缺少必填参数：{', '.join(missing)}",
        )

    params = {p.name: p.default for p in flow.parameters if p.default is not None}
    params.update(body)

    logger.info(f"执行流程 [{flow_id}]，参数：{params}")
    result = await run_flow(flow, params)
    return result


@router.post("")
async def register_flow(
    file: Optional[UploadFile] = File(default=None),
    yaml_content: Optional[str] = Body(default=None, media_type="text/plain"),
):
    """注册新流程：支持上传 YAML 文件或直接 POST YAML 文本"""
    if file is not None:
        content = await file.read()
        yaml_str = content.decode("utf-8")
    elif yaml_content is not None:
        yaml_str = yaml_content
    else:
        raise HTTPException(status_code=400, detail="请提供 YAML 文件（multipart）或 YAML 文本（text/plain body）")

    try:
        import yaml
        data = yaml.safe_load(yaml_str)
        flow_id = data.get("id")
        if not flow_id:
            raise HTTPException(status_code=400, detail="YAML 中缺少 id 字段")
        flow = flow_store.save_flow(flow_id, yaml_str)
        return {"message": f"流程已注册：{flow.id}", "flow": flow}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"流程配置解析失败：{e}")


@router.put("/{flow_id}")
async def update_flow(
    flow_id: str,
    file: Optional[UploadFile] = File(default=None),
    yaml_content: Optional[str] = Body(default=None, media_type="text/plain"),
):
    """更新流程配置：支持上传文件或直接 POST YAML 文本"""
    if file is not None:
        content = await file.read()
        yaml_str = content.decode("utf-8")
    elif yaml_content is not None:
        yaml_str = yaml_content
    else:
        raise HTTPException(status_code=400, detail="请提供 YAML 文件（multipart）或 YAML 文本（text/plain body）")

    try:
        flow = flow_store.save_flow(flow_id, yaml_str)
        return {"message": f"流程已更新：{flow.id}", "flow": flow}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{flow_id}")
async def delete_flow(flow_id: str):
    deleted = flow_store.delete_flow(flow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"流程不存在：{flow_id}")
    return {"message": f"流程已删除：{flow_id}"}
