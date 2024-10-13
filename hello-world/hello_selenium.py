from selenium import webdriver
from selenium.webdriver.common.by import By
import time

def hello_world():
    # Create a new instance of the browser driver
    # For Chrome:
    driver = webdriver.Chrome()

    # For Firefox:
    # driver = webdriver.Firefox()

    try:
        # Navigate to the desired website
        driver.get('https://askubuntu.com/questions/1409496/how-to-safely-install-fuse-on-ubuntu-22-04')

        # Wait for the page to load (optional)
        time.sleep(2)

        # Get the page title
        title = driver.title
        print('Page Title:', title)

        # Additional actions can be performed here

    except Exception as e:
        print('An error occurred:', e)

    finally:
        # Close the browser
        driver.quit()

if __name__ == '__main__':
    hello_world()
