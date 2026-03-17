import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserManager:
    _instance: Optional["BrowserManager"] = None

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = BrowserManager()
        return cls._instance

    async def initialize(self):
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            logger.info("初始化浏览器...")
            self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=settings.browser_profile_dir,
                headless=settings.browser_headless,
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
                ignore_default_args=["--enable-automation"],
            )
            self._initialized = True
            logger.info("浏览器初始化完成")

    async def new_page(self):
        await self.initialize()
        page = await self._context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return page

    async def get_context(self) -> BrowserContext:
        await self.initialize()
        return self._context

    async def restart(self):
        logger.info("重启浏览器...")
        async with self._lock:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
            self._context = None
            self._playwright = None
            self._initialized = False
        await self.initialize()
        logger.info("浏览器重启完成")

    async def close(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False

    def is_ready(self) -> bool:
        return self._initialized and self._context is not None


browser_manager = BrowserManager.get_instance()
