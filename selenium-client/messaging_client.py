import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

def messaging_client():
    global driver

    # Configure Selenium WebDriver to connect to the existing Chrome session
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "localhost:9222")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Verify that we're connected to the browser
        print('Connected to existing Chrome session.')

        # Get all window handles (tabs)
        window_handles = driver.window_handles

        # Flag to indicate if the correct tab was found
        tab_found = False

        # Iterate over each tab to find the messaging platform
        for handle in window_handles:
            driver.switch_to.window(handle)
            current_url = driver.current_url
            current_title = driver.title
            print(f'Checking tab with URL: {current_url} and Title: {current_title}')

            # Identify the tab based on URL
            if 'slack.com' in current_url:
                print('Found the messaging platform tab based on URL.')
                tab_found = True
                break

        if not tab_found:
            print('Could not find the messaging platform tab. Please ensure it is open in your browser.')
            return

        last_processed_message_id = None

        # Main loop to check for new messages
        while True:
            # Wait for new messages to load
            time.sleep(2)

            # Locate the message elements
            messages = driver.find_elements(By.CSS_SELECTOR, 'div.c-message_kit__gutter__right')

            # Process messages in reverse order (assuming newest messages are at the end)
            # If messages are ordered newest first, you can remove the [::-1]
            for message_element in messages[::-1]:
                # Extract message ID (timestamp)
                try:
                    timestamp_element = message_element.find_element(By.CSS_SELECTOR, 'a.c-timestamp')
                    print("timestamp:", timestamp_element)
                    message_id = timestamp_element.get_attribute('data-ts')
                except NoSuchElementException:
                    continue

                # If we've already processed this message, skip it
                if message_id == last_processed_message_id:
                    break  # No new messages to process

                # Extract sender name
                try:
                    sender_element = message_element.find_element(By.CSS_SELECTOR, 'a.c-message__sender_link')
                    sender_name = sender_element.text.strip()
                except NoSuchElementException:
                    # Try alternative selector if needed
                    sender_name = ''

                # Check if the message is not from you
                if sender_name != 'Pearl Hulbert' and sender_name != '':
                    # Extract message text
                    try:
                        message_text_element = message_element.find_element(By.CSS_SELECTOR, 'div.p-rich_text_section')
                        message_text = message_text_element.text.strip()
                        print("message_text:", message_text)
                    except NoSuchElementException:
                        message_text = ''

                    print(f'New message detected:')
                    print(f'Sender: {sender_name}')
                    print(f'Message: {message_text}')
                    print(f'Message ID: {message_id}')

                    # Update the last processed message ID
                    last_processed_message_id = message_id

                    # Since we only want the most recent message, break after processing it
                    break

            # Wait before checking again
            time.sleep(5)

    except Exception as e:
        print('An error occurred:', e)
    finally:
        # Do not close the browser when done
        pass

if __name__ == '__main__':
    # Declare the driver variable globally
    global driver
    messaging_client()
