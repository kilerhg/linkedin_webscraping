import logging
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


from app.config import settings
from dataclasses import dataclass
from time import sleep
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
    default_endpoint = 'https://www.linkedin.com/search/results/content/?datePosted=%22past-week%22&keywords=%22{keywords}%22&sid=8gN&sortBy=%22relevance%22'
    extra = 'remote'
    
    data_engineer_endpoint = default_endpoint.format(keywords="SENIOR%20DATA%20ENGINEER")


def get_text_if_exists(post, xpath):
    """Return the text of the first element matching ``xpath`` inside ``post``, or ''."""
    elements = post.find_elements(By.XPATH, xpath)
    return elements[0].text if elements else ''


def get_attr_if_exists(post, xpath, attribute):
    """Return ``attribute`` of the first element matching ``xpath`` inside ``post``, or ''."""
    elements = post.find_elements(By.XPATH, xpath)
    return (elements[0].get_attribute(attribute) or '') if elements else ''


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


def search_posts(driver, goal_post=20, max_idle_scrolls=3):
    sleep(1)
    driver.get(QueryPost.data_engineer_endpoint)
    sleep(1)

    dict_posts = {}
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
                sleep(0.5)

                post_id, post_url = get_post_id_via_menu(driver, post)
                driver.execute_script("arguments[0].setAttribute('data-scrapped', '1');", post)
            except StaleElementReferenceException:
                # LinkedIn re-rendered the feed under us; close any stray menu and
                # move on. This card will be re-fetched on the next pass.
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                continue

            # Skip posts without an id or ones we already collected (dedup).
            if not post_id or post_id in dict_posts:
                continue

            dict_posts[post_id] = {
                'post_id': post_id,
                'post_url': post_url,
                'posted_at': extract_linkedin_time(post_id).isoformat(),
                'author_profile_url': get_attr_if_exists(post, XpathsPost.author_profile_url, 'href'),
                'author_name': get_text_if_exists(post, XpathsPost.author_name),
                'post_content': get_text_if_exists(post, XpathsPost.post_content),
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
        sleep(2)

    logger.info('Collected %d posts (goal %d)', len(dict_posts), goal_post)
    return dict_posts





def scroll_posts(driver): ...

def extract_posts(driver): ...
