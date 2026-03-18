from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.browser.manager import browser_manager
from app.routes.flows import router as flows_router
from app.routes.browser import router as browser_router
from app.routes.logs import router as logs_router
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
    description=(
        "浏览器自动化 API 服务 —— 将 Playwright 流程包装为 HTTP 接口\n\n"
        "## 快速开始\n"
        "1. `GET /flows` 列出所有已注册流程\n"
        "2. `GET /flows/{id}/schema` 查看流程参数说明\n"
        "3. `POST /flows/{id}/run` 执行流程（传入参数 JSON）\n"
        "4. `GET /logs` 查看执行历史\n"
        "5. `GET /browser/status` 查看浏览器状态\n"
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(flows_router)
app.include_router(browser_router)
app.include_router(logs_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "browser_ready": browser_manager.is_ready(),
    }
