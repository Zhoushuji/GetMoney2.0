from __future__ import annotations

import time

import httpx
import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

FRONTEND_URL = "http://127.0.0.1:3000"
BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health"


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


def _create_demo_task(product_name: str) -> str:
    response = httpx.post(
        f"{FRONTEND_URL}/api/v1/leads/search",
        json={
            "product_name": product_name,
            "countries": ["Germany"],
            "languages": ["en"],
            "target_count": 1,
            "mode": "demo",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["task_id"]


def _wait_for_task_completion(task_id: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = httpx.get(f"{FRONTEND_URL}/api/v1/tasks/{task_id}/status", timeout=3.0)
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in {"completed", "failed", "stopped_early"}:
            return
        time.sleep(0.5)
    raise AssertionError(f"task {task_id} did not finish in time")


def test_demo_history_restore_and_contact_noise_reduction() -> None:
    _wait_for_service(BACKEND_HEALTH_URL)
    _wait_for_service(f"{FRONTEND_URL}/health")

    product_name = f"ui smoke {int(time.time())}"
    task_id = _create_demo_task(product_name)
    _wait_for_task_completion(task_id)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script(
            """
            window.localStorage.clear();
            window.sessionStorage.clear();
            """
        )
        page = context.new_page()

        page.goto(f"{FRONTEND_URL}/", wait_until="networkidle")
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
