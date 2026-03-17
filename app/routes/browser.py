from fastapi import APIRouter, HTTPException
from app.browser.manager import browser_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/browser", tags=["browser"])


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


@router.get("/{site}/cookies")
async def get_site_cookies(site: str):
    context = await browser_manager.get_context()
    all_cookies = await context.cookies()
    site_cookies = [c for c in all_cookies if site in c.get("domain", "")]
    return {"site": site, "cookies": site_cookies, "count": len(site_cookies)}


@router.delete("/{site}/cookies")
async def clear_site_cookies(site: str):
    context = await browser_manager.get_context()
    all_cookies = await context.cookies()
    site_cookies = [c for c in all_cookies if site in c.get("domain", "")]
    await context.clear_cookies()
    keep = [c for c in all_cookies if site not in c.get("domain", "")]
    if keep:
        await context.add_cookies(keep)
    return {"message": f"已清除 {len(site_cookies)} 个 {site} Cookie"}
