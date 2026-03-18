from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.browser.manager import browser_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/browser", tags=["browser"])


class LoginRequest(BaseModel):
    flow_id: str
    secrets_override: Optional[Dict[str, Any]] = None


@router.get("/status")
async def browser_status():
    return {
        "ready": browser_manager.is_ready(),
        "headless": True,
    }


@router.post("/restart")
async def restart_browser():
    await browser_manager.restart()
    return {"message": "浏览器重启成功"}


@router.post("/{flow_id}/login")
async def trigger_login(flow_id: str):
    """手动触发指定流程的登录（适用于需要人工介入验证码的情况）"""
    from app.storage.flow_store import flow_store
    from app.engine.auth_checker import do_login

    flow = flow_store.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail=f"流程不存在：{flow_id}")
    if not flow.auth:
        raise HTTPException(status_code=400, detail=f"流程 {flow_id} 未配置认证")

    context = await browser_manager.get_context()
    try:
        final_url = await do_login(context, flow.auth)
        return {
            "message": f"登录流程已执行",
            "flow_id": flow_id,
            "final_url": final_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {e}")


@router.get("/{flow_id}/login/status")
async def check_login_status(flow_id: str):
    """检查指定流程的登录状态"""
    from app.storage.flow_store import flow_store
    from app.engine.auth_checker import is_logged_in

    flow = flow_store.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail=f"流程不存在：{flow_id}")
    if not flow.auth:
        return {"flow_id": flow_id, "has_auth": False, "logged_in": True}

    context = await browser_manager.get_context()
    try:
        logged_in = await is_logged_in(context, flow.auth)
        return {
            "flow_id": flow_id,
            "has_auth": True,
            "logged_in": logged_in,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录状态检测失败: {e}")


@router.get("/cookies")
async def get_all_cookies():
    """获取当前浏览器所有 Cookie"""
    context = await browser_manager.get_context()
    cookies = await context.cookies()
    return {"count": len(cookies), "cookies": cookies}


@router.get("/cookies/{site}")
async def get_site_cookies(site: str):
    context = await browser_manager.get_context()
    all_cookies = await context.cookies()
    site_cookies = [c for c in all_cookies if site in c.get("domain", "")]
    return {"site": site, "cookies": site_cookies, "count": len(site_cookies)}


@router.delete("/cookies/{site}")
async def clear_site_cookies(site: str):
    context = await browser_manager.get_context()
    all_cookies = await context.cookies()
    site_cookies = [c for c in all_cookies if site in c.get("domain", "")]
    await context.clear_cookies()
    keep = [c for c in all_cookies if site not in c.get("domain", "")]
    if keep:
        await context.add_cookies(keep)
    return {"message": f"已清除 {len(site_cookies)} 个 {site} Cookie"}
