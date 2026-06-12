from selenium.webdriver.common.by import By
from app.config import settings
from dataclasses import dataclass
from time import sleep

@dataclass
class XpathsLogin:
    root_path_real_page = '//*[@id="workspace"]/div/div[2]/div/div[1]/div/div/div[2]'
    email_input = f"{root_path_real_page}//input[@type='email']"
    password_input = f"{root_path_real_page}//input[@type='password']"
    login_button = f"{root_path_real_page}/div/div/div/div[2]/div/div[3]/button"


def login_linkedin(driver):
    input()

    sleep(1.0)

    login = driver.find_element(By.XPATH, XpathsLogin.email_input)
    login.send_keys(settings.LINKEDIN_EMAIL)

    sleep(1.0)

    password = driver.find_element(By.XPATH, XpathsLogin.password_input)
    password.send_keys(settings.LINKEDIN_PASSWORD)

    sleep(1.0)

    log_in_button = driver.find_element(By.XPATH, XpathsLogin.login_button)
    log_in_button.click()

    input()