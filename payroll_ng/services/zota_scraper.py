"""
Playwright replacement for Bot.connect + Bot.dlEmpSales.

What Playwright removes from the old code:
  * the chromedriver download/unzip fallback  -> `playwright install chromium` once
  * WebDriverWait helpers                      -> locators auto-wait
  * polling the folder for .crdownload         -> page.expect_download() hands you the file
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from playwright.async_api import Page, TimeoutError as PWTimeout, async_playwright

from config import SEL, ZOTA_BASE

log = logging.getLogger("payroll")


def _parse_date(s: str) -> list[int]:
    m, d, y = (int(p) for p in s.strip().split("/"))
    return [m, d, y]


async def _enter_date(page: Page, selector: str, target: str) -> None:
    """
    Same trick as helper.enterDate: the masked input goes blank if you clear it, so step each
    segment (month, day, year) with arrow keys from the prefilled value.
    """
    field = page.locator(selector)
    default = _parse_date(await field.input_value())
    want = _parse_date(target)
    await field.click()
    for _ in range(3):
        await field.press("ArrowLeft")
    await page.wait_for_timeout(300)
    for i, (w, d) in enumerate(zip(want, default)):
        if i:
            await field.press("ArrowRight")
        key = "ArrowUp" if w > d else "ArrowDown"
        for _ in range(abs(w - d)):
            await field.press(key)


class ZotaScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def download_employee_sales(self, salon_name: str, username: str, password: str, start: str, end: str,
                                      save_to: Path) -> Path:
        """Logs in, runs the employee report for start..end, saves the xlsx to `save_to`."""
        save_to = Path(save_to)
        save_to.parent.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            try:
                await self._login_zota(page, username, password)
                await page.goto(f"{ZOTA_BASE}/#/reports/employee-reports")
                await page.locator(SEL["start_date"]).wait_for(state="visible", timeout=15_000)
                # await _enter_date(page, SEL["start_date"], start)
                # await page.fill(SEL["start_date"], start)
                # await page.wait_for_timeout(500)
                # await _enter_date(page, SEL["end_date"], end)
                # await page.fill(SEL["end_date"], end)
                # await page.wait_for_timeout(500)

                # manually choose date
                confirm = page.get_by_role('button', name=' Run Report')
                # this waits for once run report is clicked
                await confirm.evaluate(
                    "el => new Promise(resolve => el.addEventListener('click', resolve, { once: true }))"
                )
                await page.locator(SEL["run_report"]).click()

                download = await self._click_excel(page)
                await download.save_as(save_to)
                log.info("Downloaded %s", save_to.name)
                return save_to
            finally:
                await context.close()
                await browser.close()

    async def _login_zota(self, page: Page, username: str, password: str) -> None:
        await page.goto(f"{ZOTA_BASE}/#/login")
        await page.fill(SEL["username"], username)
        await page.fill(SEL["password"], password)
        await page.click(SEL["login_btn"])
        await page.locator(SEL["logged_in"]).wait_for(timeout=20_000)
        log.info("Logged in as %s", username)

    async def _click_excel(self, page: Page, attempts: int = 3):
        """Wait for the report, click the Excel link. Reload once if it never shows (old 30s/60s logic)."""
        link = page.locator(SEL["excel_link"])
        for attempt in range(1, attempts + 1):
            try:
                await link.wait_for(state="visible", timeout=30_000)
                async with page.expect_download(timeout=60_000) as info:
                    await link.click()
                return await info.value
            except PWTimeout:
                log.warning("Excel link not ready (attempt %d/%d)", attempt, attempts)
                if attempt < attempts:
                    await page.reload()
                    await page.locator(SEL["run_report"]).click()
                    await asyncio.sleep(1)
        raise RuntimeError("Could not download the Excel report from Zota (link never became clickable).")

    async def download_employee_sales_galaxy(self, salon_name: str, username: str, password: str, start: str, end: str,
                                      save_to: Path) -> Path:
        """Logs in, runs the employee report for start..end, saves the xlsx to `save_to`."""
        save_to = Path(save_to)
        save_to.parent.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            try:
                await self._login_galaxy(page, username, password)
                await page.get_by_test_id('MenuHeaderIconIcon').click()
                await page.get_by_test_id('ReportIconIcon').click()
                await page.get_by_test_id('EmployeesReportIconIcon').click()
                # enter admin password
                await page.keyboard.press('0')
                await page.keyboard.press('9')
                await page.keyboard.press('0')
                await page.keyboard.press('9')
                await page.keyboard.press('Enter')
                # setting dates
                # self.page.locator("//button[@id=':r1r:']").click()
                # temporarily manually click dates on website and click run report button
                confirm = page.get_by_role('button', name='Run Report')
                # this waits for once run report is clicked
                await confirm.evaluate(
                    "el => new Promise(resolve => el.addEventListener('click', resolve, { once: true }))"
                )
                # self.page.get_by_role('button', name='Run Report').click()
                # wait for export to be visible
                await page.locator("button:has(img[src='/images/microsoft-excel.svg'])").wait_for(state='visible')
                async with page.expect_download() as download:
                    await page.locator("button:has(img[src='/images/microsoft-excel.svg'])").click()
                report = await download.value
                await report.save_as(save_to)
                log.info("Downloaded %s", save_to.name)
                return save_to
            finally:
                await context.close()
                await browser.close()

    async def _login_galaxy(self, page: Page, username: str, password: str) -> None:
        await page.goto('https://galaxypinkv2.azurewebsites.net/login')
        await page.locator("input[name='email']").fill(username)
        await page.locator('input[name="password"]').fill(password)
        await page.keyboard.press('Enter')
        log.info("Logged in as %s", username)
