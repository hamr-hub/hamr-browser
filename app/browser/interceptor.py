import asyncio
from fnmatch import fnmatch
from typing import Any, Optional
from playwright.async_api import Page, Response
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CaptureTimeoutError(Exception):
    pass


async def wait_for_response(
    page: Page,
    url_pattern: str,
    method: Optional[str] = None,
    timeout: int = 30000,
) -> Any:
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()

    async def on_response(response: Response):
        if future.done():
            return
        url_match = fnmatch(response.url, url_pattern) or url_pattern in response.url
        method_match = method is None or response.request.method.upper() == method.upper()
        if url_match and method_match:
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await response.json()
                else:
                    body = await response.text()
                future.set_result(body)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

    page.on("response", on_response)

    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout / 1000)
    except asyncio.TimeoutError:
        raise CaptureTimeoutError(
            f"等待响应超时（{timeout}ms）：{url_pattern}"
        )
    finally:
        page.remove_listener("response", on_response)
