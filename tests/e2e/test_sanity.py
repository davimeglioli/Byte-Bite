from playwright.sync_api import Page, expect

def test_google(page: Page):
    print("DEBUG: Navigating to google")
    page.goto("https://www.google.com")
    print("DEBUG: Checking title")
    expect(page).to_have_title("Google")
    print("DEBUG: Done")
