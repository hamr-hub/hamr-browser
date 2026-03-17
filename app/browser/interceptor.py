import asyncio
from fnmatch import fnmatch
from typing import Any, Optional
from playwright.async_api import Page, Response
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CaptureTimeoutError(Exception):
    pass


class ResponseWaiter:
    def __init__(self, page: Page, url_pattern: str, method: Optional[str] = None):
        self._page = page
        self._url_pattern = url_pattern
        self._method = method
        self._future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._registered = False

    def start(self):
        self._page.on("response", self._on_response)
        self._registered = True

    async def _on_response(self, response: Response):
        if self._future.done():
            return
        url_match = fnmatch(response.url, self._url_pattern) or self._url_pattern in response.url
        method_match = self._method is None or response.request.method.upper() == self._method.upper()
        if url_match and method_match:
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await response.json()
                else:
                    body = await response.text()
                if not self._future.done():
                    self._future.set_result(body)
            except Exception as e:
                if not self._future.done():
                    self._future.set_exception(e)

    async def wait(self, timeout: int = 30000) -> Any:
        try:
            return await asyncio.wait_for(asyncio.shield(self._future), timeout=timeout / 1000)
        except asyncio.TimeoutError:
            raise CaptureTimeoutError(f"等待响应超时（{timeout}ms）：{self._url_pattern}")
        finally:
            if self._registered:
                self._page.remove_listener("response", self._on_response)


async def wait_for_response(
    page: Page,
    url_pattern: str,
    method: Optional[str] = None,
    timeout: int = 30000,
) -> Any:
    waiter = ResponseWaiter(page, url_pattern, method)
    waiter.start()
    return await waiter.wait(timeout)
