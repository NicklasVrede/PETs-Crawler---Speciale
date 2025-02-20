from playwright.async_api import async_playwright
import asyncio
import csv
import sqlite3
from datetime import datetime

class CMPDetector:
    CMP_SELECTORS = {
        'OneTrust': {
            'banner': ['#onetrust-banner-sdk', '#onetrust-consent-sdk'],
            'verify': ['#onetrust-reject-all-handler', '#onetrust-accept-btn-handler', '#onetrust-pc-btn-handler'],
            'provider': 'OneTrust'
        },
        'CookieBot': {
            'banner': ['div#CybotCookiebotDialog', '.CookieDeclaration'],
            'verify': ['#CybotCookiebotDialogBodyButtonDecline', '#CybotCookiebotDialogBodyButtonAccept'],
            'provider': 'CookieBot'
        },
        'Quantcast': {
            'banner': ['div.qc-cmp2-container', 'div[class*="quantcast"]', 'div[class*="qc-cmp"]'],
            'verify': ['.qc-cmp2-buttons', '[class*="qc-cmp"]'],
            'provider': 'Quantcast'
        },
        'TrustArc': {
            'banner': ['div.truste_box_overlay', '.truste_overlay', '[class*="truste"]'],
            'verify': ['button#truste-consent-deny', '[class*="truste"]'],
            'provider': 'TrustArc'
        },
        'Google': {
            'banner': [
                'div[aria-label*="consent"]',
                '.fc-consent-root',
                'div[role="dialog"][aria-modal="true"]',
                '.consent-banner',
                '#consent-bump'
            ],
            'verify': [
                'button[aria-label*="Reject"]',
                'button[aria-label*="Accept"]',
                'button[contains(text(), "Reject")]',
                'button[contains(text(), "Accept")]'
            ],
            'provider': 'Google'
        },
        'Generic': {
            'banner': [
                '[class*="consent"]',
                '[class*="cookie"]',
                '[id*="consent"]',
                '[id*="cookie"]',
                '[class*="gdpr"]',
                '[id*="gdpr"]',
                'div[role="dialog"]'
            ],
            'verify': [
                'button[contains(text(), "Accept")]',
                'button[contains(text(), "Reject")]',
                'button[contains(text(), "Decline")]',
                'button[contains(text(), "Agree")]',
                'button[contains(text(), "Cookie")]',
                'button[contains(text(), "Consent")]'
            ],
            'provider': 'Generic'
        }
    }

    def __init__(self, db_path="cmp_detection.db"):
        self.db = sqlite3.connect(db_path)
        self.browser = None
        self.context = None
        self.playwright = None
        self.current_page = None  # Store current page
        sqlite3.register_adapter(datetime, lambda x: x.isoformat())
        sqlite3.register_converter('datetime', lambda x: datetime.fromisoformat(x.decode()))
        self.setup_database()

    def setup_database(self):
        cursor = self.db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY,
                rank INTEGER,
                domain TEXT,
                has_cmp BOOLEAN,
                cmp_provider TEXT,
                check_timestamp DATETIME
            )
        """)
        self.db.commit()

    async def setup_browser(self):
        print("🌟 Setting up new browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        self.current_page = await self.context.new_page()  # Create initial page
        print("✅ Browser setup complete")

    async def check_site(self, rank, domain):
        found_cmp = False
        
        if not self.browser:
            print("⚠️ Browser not found, creating new one...")
            await self.setup_browser()
        
        print(f"\n📍 Checking {domain}...")
        print("1️⃣ Loading page...")
        await self.current_page.goto(f"https://{domain}", timeout=30000)
        
        try:
            print("2️⃣ Waiting for page load states...")
            await self.current_page.wait_for_load_state('domcontentloaded', timeout=10000)
            await self.current_page.wait_for_load_state('load', timeout=10000)
            try:
                await self.current_page.wait_for_load_state('networkidle', timeout=5000)
            except:
                pass  # Continue if networkidle times out
            
            # Additional wait for dynamic content
            await asyncio.sleep(2)
            
            print("3️⃣ Checking for CMP banners...")
            for cmp, selectors in self.CMP_SELECTORS.items():
                if found_cmp:
                    break
                    
                banner_selectors = selectors['banner']
                for banner_selector in banner_selectors:
                    try:
                        print(f"   🔍 Looking for {cmp}: {banner_selector}")
                        if await self.current_page.locator(banner_selector).count() > 0:
                            # If we find a banner, we'll consider it a match
                            # but try to verify with buttons too
                            found_cmp = True
                            print(f"   ✅ Found {cmp} banner!")
                            
                            # Try to find verification buttons but don't require them
                            for verify_selector in selectors['verify']:
                                if await self.current_page.locator(verify_selector).count() > 0:
                                    print(f"   ✅✅ Verified with buttons!")
                                    break
                            
                            self.store_result(rank, domain, True, selectors['provider'])
                            break
                    except Exception as e:
                        continue
            
            if not found_cmp:
                print("❌ No GDPR/CMP found on this site")
                self.store_result(rank, domain, False, None)
            
        except Exception as e:
            print(f"❌ Error checking {domain}: {str(e)}")
            self.store_result(rank, domain, False, None)
            
        return found_cmp

    def store_result(self, rank, domain, has_cmp, provider):
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO sites (rank, domain, has_cmp, cmp_provider, check_timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (rank, domain, has_cmp, provider, datetime.now()))
        self.db.commit()

    async def cleanup(self):
        print("🧹 Starting cleanup...")
        if self.browser:
            print("   Closing browser...")
            await self.browser.close()
        if self.playwright:
            print("   Stopping playwright...")
            await self.playwright.stop()
        print("✅ Cleanup complete")

async def main():
    detector = CMPDetector()
    await detector.setup_browser()
    
    try:
        with open('data/top-1m.csv', 'r') as f:
            reader = csv.reader(f)
            for i, (rank, domain) in enumerate(reader):
                if i >= 10:  # Stop after 10 sites
                    break
                await detector.check_site(int(rank), domain)
    finally:
        await detector.cleanup()

if __name__ == "__main__":
    asyncio.run(main())