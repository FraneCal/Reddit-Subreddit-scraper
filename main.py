import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from twocaptcha import TwoCaptcha

API_KEY = 'YOUR 2CAPTCHA API KEY'
URL = 'https://www.reddit.com/r/gambling/?captcha=1'
SITEKEY = '6LeTlV4oAAAAAGioktuFt-KvUtwKRJRfc8A7UJws'

def main():
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(URL)

        # wait until the recaptcha container is present
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'div.g-recaptcha[data-sitekey]')
        ))

        # --- ask 2captcha to solve recaptcha v2 ---
        solver = TwoCaptcha(API_KEY)

        result = solver.recaptcha(
            sitekey=SITEKEY,
            url=URL,
            invisible=0,   
        )
        token = result['code']
        print('Got token from 2Captcha')

        # --- inject token into textarea#g-recaptcha-response ---
        # Reddit keeps the textarea in the main document, not inside the iframe
        driver.execute_script(
            "document.getElementById('g-recaptcha-response').style.display='block';"
            "document.getElementById('g-recaptcha-response').value = arguments[0];",
            token,
        )

        # small delay to let any recaptcha callbacks fire
        time.sleep(1)

        # --- submit the form that contains the captcha ---
        form = driver.find_element(By.CSS_SELECTOR, "form[action*='captcha=1']")
        form.submit()

        # wait to be redirected to the subreddit
        time.sleep(5)

        print('Current URL:', driver.current_url)
        # you should now be on /r/gambling/ with normal content

        time.sleep(15)  # keep browser open to verify manually

    finally:
        driver.quit()

if __name__ == '__main__':
    main()
