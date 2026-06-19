import logging

from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from app.config import settings
from app.scrapper.utils.utils import wait_for_element
from dataclasses import dataclass

logger = logging.getLogger(__name__)

FEED_URL = "https://www.linkedin.com/feed/"
LOGIN_URL = "https://www.linkedin.com/login"
# URL fragments that mean the session is NOT an authenticated feed.
UNAUTH_URL_MARKERS = ("/login", "/authwall", "/checkpoint", "/uas/login")

@dataclass
class XpathsLogin:
    root_path_real_page = '//*[@id="workspace"]/div/div[2]/div/div[1]/div/div/div[2]'
    email_input = f"{root_path_real_page}//input[@type='email']"
    password_input = f"{root_path_real_page}//input[@type='password']"
    login_button = f"{root_path_real_page}/div/div/div/div[2]/div/div[3]/button"


def is_logged_in(driver):
    """Return True when the persisted session lands on an authenticated feed.

    Navigates to the feed and inspects the settled URL: when not authenticated,
    LinkedIn redirects to a login/authwall/checkpoint page; when authenticated it
    stays on /feed/."""
    driver.get(FEED_URL)
    try:
        WebDriverWait(driver, 10).until(
            lambda d: "/feed" in d.current_url
            or any(marker in d.current_url for marker in UNAUTH_URL_MARKERS)
        )
    except TimeoutException:
        pass

    return "/feed" in driver.current_url and not any(
        marker in driver.current_url for marker in UNAUTH_URL_MARKERS
    )


def ensure_logged_in(driver):
    """Reuse an existing session when possible, otherwise run the form login."""
    if is_logged_in(driver):
        logger.info("Reusing existing LinkedIn session.")
        return True

    logger.info("No active session; logging in with credentials.")
    driver.get(LOGIN_URL)
    login_linkedin(driver)

    # Let the login submission settle (feed, or a checkpoint/2FA page) before we
    # re-check; otherwise navigating to the feed can abort the in-flight login.
    try:
        WebDriverWait(driver, 20).until(lambda d: "/login" not in d.current_url)
    except TimeoutException:
        pass

    if is_logged_in(driver):
        logger.info("Login successful.")
        return True

    logger.warning(
        "Login did not reach the feed (current url: %s). A manual challenge "
        "(checkpoint/2FA) may be required; the persistent profile will remember "
        "it next run.",
        driver.current_url,
    )
    return False


def login_linkedin(driver):
    email = wait_for_element(driver, XpathsLogin.email_input, clickable=True)
    password = wait_for_element(driver, XpathsLogin.password_input, clickable=True)
    login_button = wait_for_element(driver, XpathsLogin.login_button, clickable=True)

    if not (email and password and login_button):
        logger.warning("Login form did not render fully; aborting login attempt.")
        return

    email.send_keys(settings.LINKEDIN_EMAIL)
    password.send_keys(settings.LINKEDIN_PASSWORD)
    login_button.click()