import logging
from datetime import datetime
from app.scrapper.base.selenium_basefile import SeleniumConfig
from app.scrapper.linkedin_roles import login

logging.basicConfig(level=logging.DEBUG)

def run_scrapper():
    driver = SeleniumConfig().get_driver()  
    driver.get('https://www.linkedin.com/login')
    
    login.login_linkedin(driver)

    




logging.info(f'Starting Scrapper - {str(datetime.now())}')

run_scrapper()