from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

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

        # 1. Anti-Bot and Masking Flags
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")

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