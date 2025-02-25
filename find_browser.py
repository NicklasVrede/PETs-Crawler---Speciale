from playwright.sync_api import sync_playwright

def check_default_chromium():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        print(f"Default Chromium executable path: {p.chromium.executable_path}")
        browser.close()

check_default_chromium()