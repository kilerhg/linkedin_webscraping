import logging
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


from app.scrapper.utils.utils import wait_for_element
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class XpathsPost:
    post_card = '//*[@id="workspace"]/div/div/div/section/div/div[1]/div/div/div[not(@data-display-contents)]'
    # Three-dots ("⋯") control menu button inside a post card.
    control_menu_button = ('.//button[contains(@aria-label, "control menu") '
                           'or contains(@aria-label, "More actions") '
                           'or contains(@aria-label, "more options") '
                           'or contains(@aria-label, "Open menu") '
                           'or contains(@aria-label, "Open options")]')
    # "Copy link to post" entry of the opened menu (rendered at body level, so
    # matched from the document root). Deepest node holding the label, so we can
    # click its nearest clickable ancestor.
    copy_link_item = ('//*[contains(normalize-space(), "Copy link to post")]'
                      '[not(.//*[contains(normalize-space(), "Copy link to post")])]')
    # "Link copied to clipboard" toast carries a "View post" anchor whose href
    # embeds the post id (e.g. .../posts/...-share-7472547797725028352-...).
    copied_post_link = '//a[contains(@href, "/posts/") and contains(@href, "utm_source=share")]'
    author_profile_url = './/a[contains(@href, "https://www.linkedin.com/in/")]'
    author_name = './/a[contains(@href, "https://www.linkedin.com/in/")]//p/span[not(./*)]'
    post_content = './/span[@data-testid="expandable-text-box"]'
    linkedin_job_url = './/a[contains(@href, "https://www.linkedin.com/jobs/view")]' # Optional

@dataclass
class QueryPost:
    default_endpoint = 'https://www.linkedin.com/search/results/content/?datePosted=%22past-week%22&keywords={keywords}&sortBy=%22relevance%22'

    # Per-role search keyword strings; main.py iterates these to scrape each role.
    data_engineer = '"HIRING" "DATA ENGINEER"'
    python_engineer = '"HIRING" "PYTHON ENGINEER"'
    data_tech_lead = '"HIRING" "TECH LEAD" "DATA"'

    @classmethod
    def endpoint_for(cls, keywords):
        """Build the content-search endpoint URL for a keywords string."""
        return cls.default_endpoint.format(keywords=keywords)

    @classmethod
    def role_keywords(cls):
        """Map each defined role -> its search keywords string."""
        return {
            name: value
            for name, value in vars(cls).items()
            if isinstance(value, str) and not name.startswith("_")
            and name != "default_endpoint"
        }


def get_text_if_exists(post, xpath):
    """Return the text of the first element matching ``xpath`` inside ``post``, or ''."""
    elements = post.find_elements(By.XPATH, xpath)
    return elements[0].text if elements else ''


def get_attr_if_exists(post, xpath, attribute):
    """Return ``attribute`` of the first element matching ``xpath`` inside ``post``, or ''."""
    elements = post.find_elements(By.XPATH, xpath)
    return (elements[0].get_attribute(attribute) or '') if elements else ''


# Trailing "… more" / "…more" / "...more" label of the (unclicked) expander.
_SEE_MORE_SUFFIX_RE = re.compile(r"\s*(?:…|\.\.\.)\s*more\s*$", re.IGNORECASE)


def get_post_content(post):
    """Return the post's full text. The complete content is in the DOM even while
    LinkedIn visually truncates it, so we read the full rendered text (``innerText``,
    which keeps line breaks/spacing, falling back to ``textContent``) rather than
    the visible-only Selenium ``.text``, then strip the trailing "… more" label."""
    elements = post.find_elements(By.XPATH, XpathsPost.post_content)
    if not elements:
        return ''
    element = elements[0]
    text = element.get_attribute("innerText") or element.get_attribute("textContent") or ''
    return _SEE_MORE_SUFFIX_RE.sub("", text).strip()


def dismiss_copy_toast(driver):
    """Remove any lingering "Link copied" toast so it can't overlap the next
    post and cause us to read a stale "View post" link."""
    driver.execute_script(
        "document.querySelectorAll('a[href*=\"utm_source=share\"]').forEach(a => {"
        "  const toast = a.closest('[role=\"alert\"]') "
        "             || a.closest('[aria-live]') || a.parentElement;"
        "  if (toast) toast.remove();"
        "});"
    )


def get_post_id_via_menu(driver, post):
    """Fetch a post's id by opening its "⋯" menu and clicking "Copy link to post".

    The id is not present in the rendered card markup, so this mirrors the manual
    flow: clicking "Copy link to post" shows a "Link copied to clipboard" toast
    whose "View post" anchor embeds the id in its href. Returns a
    ``(post_id, post_url)`` tuple, or ``('', '')`` if the menu/link is unavailable.
    """
    # Clear any leftover toast so the wait below resolves to this post's toast.
    dismiss_copy_toast(driver)

    menu_buttons = post.find_elements(By.XPATH, XpathsPost.control_menu_button)
    if not menu_buttons:
        return '', ''

    driver.execute_script("arguments[0].click();", menu_buttons[0])

    # Wait until the menu pop-up is fully rendered before reading its entries.
    try:
        copy_item = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, XpathsPost.copy_link_item))
        )
    except TimeoutException:
        # Entry never appeared; close the menu so it won't block the next post.
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        return '', ''

    # Click the nearest clickable ancestor of the label (falls back to the node).
    driver.execute_script(
        "(arguments[0].closest('[role=\"button\"],[role=\"menuitem\"],button,a,li') "
        "|| arguments[0]).click();",
        copy_item,
    )

    # Read the post id from the "View post" link in the confirmation toast.
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, XpathsPost.copied_post_link))
        )
        # The toast is appended last, so the freshest link is the final match.
        links = driver.find_elements(By.XPATH, XpathsPost.copied_post_link)
        href = links[-1].get_attribute('href') if links else ''
    except TimeoutException:
        href = ''

    # Clear the toast now that we've read it, so the next post starts clean.
    dismiss_copy_toast(driver)

    match = re.search(r'(?:activity|share)[:-](\d{15,})', href)
    if not match:
        return '', ''

    # Drop tracking query params for a clean canonical post url.
    post_url = href.split('?')[0]
    return match.group(1), post_url


def extract_linkedin_time(post_id):
    # The first 41 bits of the id are the creation timestamp in ms; the low 22
    # bits are sequence/worker, so shifting right by 22 yields the unix ms.
    unix_ms = int(post_id) >> 22

    # Convert milliseconds to a human-readable UTC date
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc)


def search_posts(driver, keywords, goal_post=1000, max_idle_scrolls=30, known_ids=None):
    """Scrape job posts for the search ``keywords`` and return them as a
    ``{post_id: record}`` dict.

    Skips any id in ``known_ids`` (already collected this run or on a previous
    one), so only new posts are returned. Scoring, persistence and summary
    generation are the caller's responsibility (see ``main.run_scrapper``)."""
    known_ids = known_ids or set()

    driver.get(QueryPost.endpoint_for(keywords))
    # Wait for the first result card to render before scraping.
    wait_for_element(driver, XpathsPost.post_card, timeout=15)

    dict_posts = {}  # only this run's new posts
    idle_scrolls = 0

    while len(dict_posts) < goal_post and idle_scrolls < max_idle_scrolls:
        posts = driver.find_elements(By.XPATH, XpathsPost.post_card)
        count_before = len(dict_posts)

        for post in posts:
            try:
                # Skip cards already visited on an earlier scroll pass.
                if post.get_attribute('data-scrapped'):
                    continue

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post)
                # Wait for the card's menu button to render after the scroll.
                wait_for_element(driver, XpathsPost.control_menu_button, clickable=True, context=post)

                post_id, post_url = get_post_id_via_menu(driver, post)
                driver.execute_script("arguments[0].setAttribute('data-scrapped', '1');", post)
            except StaleElementReferenceException:
                # LinkedIn re-rendered the feed under us; close any stray menu and
                # move on. This card will be re-fetched on the next pass.
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                continue

            # Skip posts without an id, already collected on a previous run, or
            # already collected this run (dedup by post id).
            if not post_id or post_id in known_ids or post_id in dict_posts:
                continue

            dict_posts[post_id] = {
                'post_id': post_id,
                'post_url': post_url,
                'posted_at': extract_linkedin_time(post_id).isoformat(),
                'author_profile_url': get_attr_if_exists(post, XpathsPost.author_profile_url, 'href'),
                'author_name': get_text_if_exists(post, XpathsPost.author_name),
                'post_content': get_post_content(post),
                'linkedin_job_url': get_attr_if_exists(post, XpathsPost.linkedin_job_url, 'href'),
            }
            logger.debug('Scrapped post %s (%d/%d)', post_id, len(dict_posts), goal_post)

            if len(dict_posts) >= goal_post:
                break

        # Nothing new collected this pass: we likely hit the bottom, scroll to load more.
        if len(dict_posts) > count_before:
            idle_scrolls = 0
        else:
            idle_scrolls += 1

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # Wait for more cards to lazy-load; idle detection handles a timeout.
        try:
            WebDriverWait(driver, 5).until(
                lambda d: len(d.find_elements(By.XPATH, XpathsPost.post_card)) > len(posts)
            )
        except TimeoutException:
            pass

    logger.info('Scraped %d new posts', len(dict_posts))
    return dict_posts
