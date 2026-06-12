from selenium.webdriver.common.by import By
from app.config import settings
from dataclasses import dataclass
from time import sleep

@dataclass
class XpathsPost:
    post_card = '//li[@class="artdeco-card mb2"]'
    author_profile_url = '//div[contains(@class, "update-components-actor__meta")]/a[1]'
    author_name = '//div[contains(@class, "update-components-actor__meta")]/a[1]/span/span/span/span'
    post_content = '//div[contains(@class, "update-components-text relative update-components-update-v2__commentary")]/span/span'
    linkedin_job_url = '//a[contains(@href, "https://www.linkedin.com/jobs/view")]' # Optional
    post_preview_url = '//div[contains(@class, "update-components-article__link-container")]' # Optional

@dataclass
class QueryPost:
    default_endpoint = 'https://www.linkedin.com/search/results/content/?datePosted=%22past-week%22&keywords=%22{keywords}%22&sid=8gN&sortBy=%22relevance%22'
    extra = 'remote'
    
    data_engineer_endpoint = default_endpoint.format(keywords="SENIOR%20DATA%20ENGINEER")

def search_posts(driver):
    driver.get(QueryPost.data_engineer_endpoint)

    posts = driver.find_elements(By.XPATH, XpathsPost.post_card)

    for post in posts:
        author_profile_url = post.find_elements(By.XPATH, XpathsPost.author_profile_url)
        author_name = post.find_elements(By.XPATH, XpathsPost.author_name)
        post_content = post.find_elements(By.XPATH, XpathsPost.post_content)
        # linkedin_job_url = post.find_elements(By.XPATH, XpathsPost.linkedin_job_url)
        # post_preview_url = post.find_elements(By.XPATH, XpathsPost.post_preview_url)





def scroll_posts(driver): ...

def extract_posts(driver): ...
