from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.browser.manager import browser_manager
from app.routes.flows import router as flows_router
from app.routes.browser import router as browser_router
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服务启动，初始化浏览器...")
    await browser_manager.initialize()
    yield
    logger.info("服务关闭，释放浏览器资源...")
    await browser_manager.close()


app = FastAPI(
    title="hamr-browser",
    description="浏览器自动化 API 服务 - 将浏览器操作流程包装为 HTTP 接口",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(flows_router)
app.include_router(browser_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "browser_ready": browser_manager.is_ready(),
    }
