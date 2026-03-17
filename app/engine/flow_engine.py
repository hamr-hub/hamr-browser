import asyncio
import time
from typing import Any, Dict
from jsonpath_ng import parse as jsonpath_parse
from app.models.flow import FlowConfig
from app.models.result import FlowRunResult
from app.browser.manager import browser_manager
from app.browser.interceptor import wait_for_response, CaptureTimeoutError
from app.engine.step_executor import execute_step
from app.engine.auth_checker import ensure_logged_in
from app.utils.template import render_template
from app.utils.logger import get_logger

logger = get_logger(__name__)

_execution_lock = asyncio.Lock()


async def run_flow(flow: FlowConfig, params: Dict[str, Any]) -> FlowRunResult:
    start = time.time()

    async with _execution_lock:
        try:
            return await _execute(flow, params, start)
        except CaptureTimeoutError as e:
            return FlowRunResult(
                flow_id=flow.id,
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                error_code="CAPTURE_TIMEOUT",
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"流程执行异常 [{flow.id}]: {e}")
            return FlowRunResult(
                flow_id=flow.id,
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                error_code="FLOW_ERROR",
                error_message=str(e),
            )


async def _execute(flow: FlowConfig, params: Dict[str, Any], start: float) -> FlowRunResult:
    context = await browser_manager.get_context()

    await ensure_logged_in(context, flow.auth)

    page = await browser_manager.new_page()
    capture_task = None

    try:
        capture_cfg = flow.capture

        if capture_cfg.type == "wait_for_response":
            url_pattern = render_template(capture_cfg.url_pattern, params)
            capture_future = asyncio.ensure_future(
                wait_for_response(
                    page,
                    url_pattern=url_pattern,
                    method=capture_cfg.method,
                    timeout=capture_cfg.timeout,
                )
            )

        for step in flow.steps:
            if step.type == "new_tab":
                continue
            await execute_step(page, step, params)

        if capture_cfg.type == "wait_for_response":
            raw_data = await capture_future
            data = _extract(raw_data, capture_cfg.extract)
        elif capture_cfg.type == "page_evaluate":
            script = render_template(capture_cfg.script, params)
            data = await page.evaluate(script)
        else:
            data = None

        return FlowRunResult(
            flow_id=flow.id,
            status="success",
            duration_ms=int((time.time() - start) * 1000),
            data=data,
        )

    finally:
        await page.close()


def _extract(data: Any, extract_cfg) -> Any:
    if extract_cfg is None or extract_cfg.type == "full":
        return data
    if extract_cfg.type == "jsonpath":
        expr = jsonpath_parse(extract_cfg.path)
        matches = [m.value for m in expr.find(data)]
        if not matches:
            return None
        return matches[0] if len(matches) == 1 else matches
    return data
