from playwright.sync_api import Page

def test_minimal(page: Page, base_url):
    print(f"DEBUG: Base URL is {base_url}")
    print("DEBUG: Navigating")
    page.goto(f"{base_url}/")
    print("DEBUG: Done")
