from typing import Any, Dict, Optional
from playwright.async_api import BrowserContext
from app.models.flow import AuthConfig
from app.utils.template import render_template
from app.utils.secrets import get_secret
from app.utils.logger import get_logger
from app.engine.step_executor import execute_step

logger = get_logger(__name__)


async def is_logged_in(context: BrowserContext, auth: AuthConfig) -> bool:
    check = auth.check

    if check.type == "cookie_exists":
        cookies = await context.cookies()
        return any(
            c["domain"] in (check.domain or "")
            and c["name"] == check.cookie_name
            for c in cookies
        )

    if check.type in ("navigate_and_check", "url_not_contains", "url_contains"):
        page = await context.new_page()
        try:
            await page.goto(check.url, wait_until="domcontentloaded", timeout=15000)
            current_url = page.url
            indicator = check.logged_in_indicator or {}
            ind_type = indicator.get("type", "url_not_contains")
            ind_value = indicator.get("value", "")

            if ind_type == "url_not_contains":
                return ind_value not in current_url
            elif ind_type == "url_contains":
                return ind_value in current_url
            return True
        except Exception as e:
            logger.warning(f"登录检测失败: {e}")
            return False
        finally:
            await page.close()

    return True


async def do_login(context: BrowserContext, auth: AuthConfig):
    if not auth.login:
        logger.warning("未配置登录流程，跳过自动登录")
        return

    secrets = {}
    if auth.secrets_key:
        raw = get_secret(auth.secrets_key)
        if raw:
            secrets = {"_auth": raw}
        else:
            logger.warning(f"未找到 secrets key: {auth.secrets_key}")

    logger.info(f"执行登录流程，secrets_key={auth.secrets_key}")
    page = await context.new_page()
    try:
        login_steps = auth.login.get("steps", [])
        from app.models.flow import Step
        for step_data in login_steps:
            step = Step(**step_data)
            await execute_step(page, step, secrets)
        logger.info("登录流程执行完成")
    finally:
        await page.close()


async def ensure_logged_in(context: BrowserContext, auth: Optional[AuthConfig]):
    if auth is None:
        return
    logged_in = await is_logged_in(context, auth)
    if not logged_in:
        logger.info("检测到未登录，开始自动登录...")
        await do_login(context, auth)
        logged_in_after = await is_logged_in(context, auth)
        if not logged_in_after:
            raise RuntimeError("自动登录失败，请手动登录后重试")
        logger.info("登录成功")
    else:
        logger.info("已登录，跳过认证")
