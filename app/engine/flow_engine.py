"""
流程执行引擎

并发控制策略：
  - 使用 asyncio.Semaphore 限制同时执行的流程数（默认 1，可通过 HAMR_MAX_CONCURRENT_FLOWS 配置）
  - 每次执行生成唯一 run_id，记录到历史
  - 支持执行失败后自动重启浏览器重试（1 次）
"""
import asyncio
import time
import uuid
from typing import Any, Dict
from jsonpath_ng import parse as jsonpath_parse
from app.models.flow import FlowConfig
from app.models.result import FlowRunResult
from app.browser.manager import browser_manager
from app.browser.interceptor import ResponseWaiter, CaptureTimeoutError
from app.engine.step_executor import execute_step
from app.engine.auth_checker import ensure_logged_in
from app.utils.template import render_template
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger(__name__)

MAX_RETRIES = 1

# Semaphore: 允许最多 N 个流程同时执行
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_flows)
    return _semaphore


async def run_flow(flow: FlowConfig, params: Dict[str, Any]) -> FlowRunResult:
    start = time.time()
    run_id = str(uuid.uuid4())[:8]

    sem = _get_semaphore()
    async with sem:
        for attempt in range(MAX_RETRIES + 1):
            try:
                result = await _execute(flow, params, start, run_id)
                _record_history(flow.id, run_id, params, result)
                return result
            except CaptureTimeoutError as e:
                result = FlowRunResult(
                    flow_id=flow.id,
                    run_id=run_id,
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    error_code="CAPTURE_TIMEOUT",
                    error_message=str(e),
                )
                _record_history(flow.id, run_id, params, result)
                return result
            except Exception as e:
                logger.exception(f"流程执行异常 [{flow.id}] (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES:
                    logger.info("尝试重启浏览器后重试...")
                    try:
                        await browser_manager.restart()
                    except Exception as restart_err:
                        logger.error(f"浏览器重启失败: {restart_err}")
                    continue
                result = FlowRunResult(
                    flow_id=flow.id,
                    run_id=run_id,
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    error_code="FLOW_ERROR",
                    error_message=str(e),
                )
                _record_history(flow.id, run_id, params, result)
                return result

    result = FlowRunResult(
        flow_id=flow.id,
        run_id=run_id,
        status="error",
        duration_ms=int((time.time() - start) * 1000),
        error_code="UNKNOWN",
        error_message="未知错误",
    )
    _record_history(flow.id, run_id, params, result)
    return result


def _record_history(flow_id: str, run_id: str, params: Dict[str, Any], result: FlowRunResult):
    try:
        from app.storage.history_store import history_store, HistoryRecord
        record = HistoryRecord(
            run_id=run_id,
            flow_id=flow_id,
            params=params,
            status=result.status,
            duration_ms=result.duration_ms,
            data=result.data,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        history_store.add(record)
    except Exception as e:
        logger.warning(f"记录执行历史失败: {e}")


async def _execute(flow: FlowConfig, params: Dict[str, Any], start: float, run_id: str) -> FlowRunResult:
    context = await browser_manager.get_context()

    await ensure_logged_in(context, flow.auth)

    page = await browser_manager.new_page()

    try:
        capture_cfg = flow.capture

        waiter = None
        if capture_cfg.type == "wait_for_response":
            url_pattern = render_template(capture_cfg.url_pattern, params)
            waiter = ResponseWaiter(
                page,
                url_pattern=url_pattern,
                method=capture_cfg.method,
            )
            waiter.start()

        for step in flow.steps:
            if step.type == "new_tab":
                continue
            await execute_step(page, step, params)

        if waiter is not None:
            raw_data = await waiter.wait(capture_cfg.timeout)
            data = _extract(raw_data, capture_cfg.extract)
        elif capture_cfg.type == "page_evaluate":
            script = render_template(capture_cfg.script, params)
            data = await page.evaluate(script)
        else:
            data = None

        return FlowRunResult(
            flow_id=flow.id,
            run_id=run_id,
            status="success",
            duration_ms=int((time.time() - start) * 1000),
            data=data,
        )

    finally:
        try:
            await page.close()
        except Exception as e:
            logger.warning(f"关闭页面失败（可忽略）: {e}")


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
