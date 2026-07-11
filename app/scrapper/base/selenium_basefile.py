from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from app.config import settings

# Persisted Chrome profile (cookies + localStorage) at the repo root's driver/.
# parents[3] = repo root: base -> scrapper -> app -> root.
PROFILE_DIR = Path(__file__).resolve().parents[3] / "driver" / "profile"


class SeleniumConfig():

    def __init__(self):
        self.config()

    def config(self):
        options = Options()

        # 0. Reuse a persistent profile so the LinkedIn session survives restarts.
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={PROFILE_DIR}")

        # When not debugging, run headless so it works under cron with no X
        # display; DEBUG=True keeps the browser visible to watch/troubleshoot.
        if not settings.DEBUG:
            options.add_argument("--headless=new")

        # 1. Anti-Bot and Masking Flags
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")

        # 1b. Memory containment. We only read post *text* and links, so the feed's
        # images/videos are pure memory waste — and on a long infinite-scroll session
        # the renderer's decoded-image cache, autoplay video buffers and JS heap grow
        # unbounded, which is what OOM-kills headless Chrome mid-run. Block media and
        # cap the V8 heap so peak memory stays bounded regardless of scroll depth.
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--autoplay-policy=document-user-activation-required")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-features=Translate,MediaRouter")
        options.add_argument("--js-flags=--max-old-space-size=512")
        # Belt-and-suspenders: also disable images via content prefs (covers paths
        # the blink-setting flag doesn't) while leaving JS enabled (LinkedIn needs it).
        options.add_experimental_option(
            "prefs", {"profile.managed_default_content_settings.images": 2}
        )

        # 2. Spoof User-Agent and Language
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--lang=en-US,en;q=0.9")

        # 3. Suppress WebDriver flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.options = options

    def get_driver(self):
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.options)

        # 5. Hide navigator.webdriver
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        return driver