from typing import Any, Dict
from playwright.async_api import Page
from app.models.flow import Step
from app.utils.template import render_template
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 15000


async def _find_selector(page: Page, selectors: list[str], timeout: int) -> str:
    import asyncio
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=min(timeout, 3000))
            return sel
        except Exception:
            continue
    raise RuntimeError(f"所有选择器均未找到元素: {selectors}")


async def execute_step(page: Page, step: Step, params: Dict[str, Any]) -> Any:
    t = step.type

    if t == "navigate":
        url = render_template(step.url, params)
        wait_until = step.wait_until or "domcontentloaded"
        timeout = step.timeout or DEFAULT_TIMEOUT
        logger.info(f"navigate → {url}")
        await page.goto(url, wait_until=wait_until, timeout=timeout)

    elif t == "wait_for_selector":
        selector = render_template(step.selector, params)
        timeout = step.timeout or DEFAULT_TIMEOUT
        logger.info(f"wait_for_selector: {selector}")
        await page.wait_for_selector(selector, timeout=timeout)

    elif t == "wait_for_url":
        url_pattern = render_template(step.url_pattern, params)
        timeout = step.timeout or DEFAULT_TIMEOUT
        logger.info(f"wait_for_url: {url_pattern}")
        await page.wait_for_url(url_pattern, timeout=timeout)

    elif t == "click":
        selector = render_template(step.selector, params)
        timeout = step.timeout or DEFAULT_TIMEOUT
        logger.info(f"click: {selector}")
        await page.click(selector, timeout=timeout)

    elif t == "fill":
        timeout = step.timeout or DEFAULT_TIMEOUT
        if step.selectors:
            rendered = [render_template(s, params) for s in step.selectors]
            selector = await _find_selector(page, rendered, timeout)
        else:
            selector = render_template(step.selector, params)
        value = render_template(step.value, params)
        logger.info(f"fill: {selector} ← (value hidden)")
        await page.fill(selector, value)

    elif t == "try_selectors":
        timeout = step.timeout or DEFAULT_TIMEOUT
        selectors = [render_template(s, params) for s in (step.selectors or [])]
        action = step.value or "click"
        selector = await _find_selector(page, selectors, timeout)
        logger.info(f"try_selectors ({action}): {selector}")
        if action == "click":
            await page.click(selector, timeout=timeout)
        elif action == "focus":
            await page.focus(selector)

    elif t == "select":
        selector = render_template(step.selector, params)
        value = render_template(step.value, params)
        logger.info(f"select: {selector} ← {value}")
        await page.select_option(selector, value)

    elif t == "wait":
        ms = step.milliseconds or 1000
        logger.info(f"wait: {ms}ms")
        await page.wait_for_timeout(ms)

    elif t == "evaluate":
        script = render_template(step.script, params)
        logger.info(f"evaluate: {script[:80]}...")
        result = await page.evaluate(script)
        return result

    elif t == "screenshot":
        path = render_template(step.value or "./logs/screenshot.png", params)
        logger.info(f"screenshot → {path}")
        await page.screenshot(path=path, full_page=True)

    elif t == "scroll_to":
        selector = render_template(step.selector, params)
        logger.info(f"scroll_to: {selector}")
        await page.eval_on_selector(selector, "el => el.scrollIntoView()")

    elif t == "press_key":
        key = render_template(step.key or "Enter", params)
        logger.info(f"press_key: {key}")
        await page.keyboard.press(key)

    elif t in ("new_tab", "close_tab"):
        pass

    return None
