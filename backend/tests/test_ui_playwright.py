from __future__ import annotations

import time

import httpx
import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.config import get_settings

FRONTEND_URL = "http://127.0.0.1:3000"
BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health"
SETTINGS = get_settings()
ADMIN_USERNAME = SETTINGS.initial_admin_username
ADMIN_PASSWORD = SETTINGS.initial_admin_password


def _wait_for_service(url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    pytest.skip(f"service unavailable: {url}")


def _wait_for_text(page: Page, text: str, timeout: float = 15000) -> None:
    page.get_by_text(text, exact=False).first.wait_for(timeout=timeout)


def _api_login(username: str, password: str) -> dict:
    response = httpx.post(
        f"{FRONTEND_URL}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(admin_token: str, username: str, password: str, daily_task_limit: int = 3) -> dict:
    response = httpx.post(
        f"{FRONTEND_URL}/api/v1/users",
        headers=_auth_headers(admin_token),
        json={
            "username": username,
            "password": password,
            "role": "user",
            "is_active": True,
            "daily_task_limit": daily_task_limit,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def _create_demo_task(keyword: str, token: str) -> str:
    response = httpx.post(
        f"{FRONTEND_URL}/api/v1/leads/search",
        headers=_auth_headers(token),
        json={
            "keywords": [keyword],
            "countries": ["Germany"],
            "languages": ["en"],
            "target_count": 1,
            "mode": "demo",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["task_id"]


def _wait_for_task_completion(task_id: str, token: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = httpx.get(
            f"{FRONTEND_URL}/api/v1/tasks/{task_id}/status",
            headers=_auth_headers(token),
            timeout=3.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in {"completed", "failed", "stopped_early"}:
            return
        time.sleep(0.5)
    raise AssertionError(f"task {task_id} did not finish in time")


def _login_via_ui(page: Page, username: str, password: str) -> None:
    page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
    page.get_by_label("用户名").fill(username)
    page.get_by_label("密码").fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(f"{FRONTEND_URL}/", timeout=15000)
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => !!window.localStorage.getItem('leadgen-auth')")


def test_login_case_insensitive_and_admin_only_pages_hidden_for_user() -> None:
    _wait_for_service(BACKEND_HEALTH_URL)
    _wait_for_service(f"{FRONTEND_URL}/health")

    admin_payload = _api_login("haocheng", ADMIN_PASSWORD)
    username = f"CaseUi{int(time.time())}"
    password = "UserPass123"
    user_payload = _create_user(admin_payload["access_token"], username, password, daily_task_limit=3)

    wrong_password_response = httpx.post(
        f"{FRONTEND_URL}/api/v1/auth/login",
        json={"username": username, "password": password.lower()},
        timeout=10.0,
    )
    assert wrong_password_response.status_code == 401

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        user_context = browser.new_context()
        user_page = user_context.new_page()
        _login_via_ui(user_page, username.lower(), password)
        _wait_for_text(user_page, "▼ STEP 1 — 潜在客户发现")
        assert user_page.get_by_role("link", name="客户触达与拓展").count() == 0
        assert user_page.get_by_role("link", name="功能测试").count() == 0
        assert user_page.get_by_text(user_payload["username"], exact=False).count() > 0
        assert user_page.get_by_text("普通用户", exact=False).count() > 0
        assert user_page.get_by_text("每日额度 3", exact=False).count() > 0
        assert user_page.get_by_text("▼ STEP 3 — 客户触达与商业拓展", exact=False).count() == 0

        user_page.goto(f"{FRONTEND_URL}/outreach", wait_until="networkidle")
        assert user_page.url.rstrip("/") == FRONTEND_URL
        user_page.goto(f"{FRONTEND_URL}/testing", wait_until="networkidle")
        assert user_page.url.rstrip("/") == FRONTEND_URL

        admin_context = browser.new_context()
        admin_page = admin_context.new_page()
        _login_via_ui(admin_page, ADMIN_USERNAME.upper(), ADMIN_PASSWORD)
        _wait_for_text(admin_page, "▼ STEP 1 — 潜在客户发现")
        assert admin_page.get_by_role("link", name="客户触达与拓展").count() == 1
        assert admin_page.get_by_role("link", name="功能测试").count() == 1
        assert admin_page.get_by_text("管理员", exact=False).count() > 0
        assert admin_page.get_by_text("不限额", exact=False).count() > 0

        admin_page.goto(f"{FRONTEND_URL}/outreach", wait_until="networkidle")
        _wait_for_text(admin_page, "客户触达与商业拓展")
        assert admin_page.url.endswith("/outreach")

        user_context.close()
        admin_context.close()
        browser.close()


def test_demo_history_restore_and_contact_noise_reduction() -> None:
    _wait_for_service(BACKEND_HEALTH_URL)
    _wait_for_service(f"{FRONTEND_URL}/health")

    admin_payload = _api_login(ADMIN_USERNAME, ADMIN_PASSWORD)
    product_name = f"ui smoke {int(time.time())}"
    task_id = _create_demo_task(product_name, admin_payload["access_token"])
    _wait_for_task_completion(task_id, admin_payload["access_token"])

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        _login_via_ui(page, ADMIN_USERNAME, ADMIN_PASSWORD)
        page.get_by_role("link", name="任务记录").click()
        _wait_for_text(page, product_name, timeout=15000)

        page.get_by_role("link", name="潜在客户发现").click()
        page.wait_for_load_state("networkidle")
        page.reload(wait_until="networkidle")
        assert page.locator("textarea").first.input_value() == product_name

        page.get_by_role("link", name="核心联系人挖掘").click()
        _wait_for_text(page, product_name, timeout=15000)
        page.get_by_role("button", name="批量启动联系人挖掘").click()

        page.get_by_role("button", name="刷新数据").click()
        row = page.locator("table.result-table tbody tr").filter(has_text=product_name).first
        try:
            row.get_by_text("无数据", exact=False).first.wait_for(timeout=20000)
        except PlaywrightTimeoutError:
            page.get_by_role("button", name="刷新数据").click()
            row.get_by_text("无数据", exact=False).first.wait_for(timeout=20000)

        assert row.get_by_text("失败", exact=False).count() == 0

        task_id = page.evaluate("window.localStorage.getItem('leadgen-active-task')")
        assert task_id

        context.close()
        browser.close()
