"""Quick Chrome smoke test for source filters and library-aware chat shortcuts."""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser=pw.chromium.launch(
        headless=True,
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    page=browser.new_page()
    errors=[]
    page.on("pageerror",lambda exc: errors.append(str(exc)))
    page.goto("http://127.0.0.1:8000",wait_until="networkidle",timeout=30000)
    page.locator("#selectionSummary").wait_for()
    assert "5 of 5 sources selected" in page.locator("#selectionSummary").inner_text()
    page.locator("#clearSelectedDocs").click()
    assert "0 of 5 sources selected" in page.locator("#selectionSummary").inner_text()
    page.locator("#selectAllDocs").click()
    assert "5 of 5 sources selected" in page.locator("#selectionSummary").inner_text()
    print("PASS select all / none source controls")
    page.locator('button[data-question="Which PDFs are in my sources?"]').click()
    assert page.locator("#question").input_value()=="Which PDFs are in my sources?"
    print("PASS list-PDFs question shortcut")
    page.locator('button[data-question="What do these documents have in common?"]').click()
    assert page.locator("#mode").input_value()=="compare"
    assert "What do these documents have in common?"==page.locator("#question").input_value()
    page.locator('button[data-mode="find"]').click()
    assert page.locator("#mode").input_value()=="find"
    assert "Which topic" in page.locator("#question").get_attribute("placeholder")
    print("PASS Find content shortcut, mode hint, and topic prompt")
    assert not errors,errors
    print("PASS compare-documents shortcut and JavaScript console")
    browser.close()
