import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def launch_browser_for_manual_setup(profile_name="manual_setup", browser_type="chrome"):
    # Create a unique user data directory for the profile
    user_data_dir = Path(f"user_profiles/{profile_name}")
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Choose the browser type
        browser_launcher = {
            "chrome": p.chromium,
            "firefox": p.firefox,
            "webkit": p.webkit
        }.get(browser_type, p.chromium)

        # Launch the browser with a persistent context
        browser = browser_launcher.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False  # Ensure the browser is visible
        )
        
        page = browser.new_page()
        
        # Open the browser's extensions page or a blank page
        page.goto("about:blank")
        
        print(f"Browser is open with profile '{profile_name}'. You can now manually install extensions.")
        print("Press Enter to close the browser when you're done...")
        input()  # Wait for user input to close the browser
        
        # Close the browser
        browser.close()

if __name__ == "__main__":
    # Launch the browser for manual setup
    launch_browser_for_manual_setup(profile_name="i_dont_care_about_cookies", browser_type="chrome")