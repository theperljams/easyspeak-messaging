import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys  # Import Keys for sending special keys

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

        last_processed_message_id = None  # ID of the last message processed

        # Main loop to check for new messages
        while True:
            # Wait for new messages to load
            time.sleep(2)

            # Locate the message elements
            messages = driver.find_elements(By.CSS_SELECTOR, 'div.c-message_kit__background')
            print(f"Found {len(messages)} messages.")

            # Process messages in reverse order (assuming newest messages are at the end)
            for message_element in messages[::-1]:
                # Extract message ID (timestamp)
                try:
                    timestamp_element = message_element.find_element(By.CSS_SELECTOR, 'a.c-timestamp')
                    message_id = timestamp_element.get_attribute('data-ts')
                    print(f"Current message ID: {message_id}")
                except NoSuchElementException:
                    print("Timestamp not found, skipping message.")
                    continue

                # If the current message ID is equal to last processed, no new messages
                if message_id == last_processed_message_id:
                    print("No new messages to process.")
                    break  # Exit the loop to wait and check again later

                # Extract sender name
                sender_name = ''
                try:
                    # Try to find the sender name in the button (for messages that include it)
                    sender_element = message_element.find_element(By.CSS_SELECTOR, 'button.c-message__sender_button')
                    sender_name = sender_element.text.strip()
                    print("Sender name found in button:", sender_name)
                except NoSuchElementException:
                    try:
                        # Try to find the sender name in the offscreen span (for messages without explicit sender name)
                        sender_span = message_element.find_element(By.CSS_SELECTOR, 'span.offscreen[data-qa^="aria-labelledby"]')
                        sender_name = sender_span.text.strip()
                        print("Sender name found in offscreen span:", sender_name)
                    except NoSuchElementException:
                        sender_name = ''
                        print("Sender name not found in message.")
                        # If we cannot find the sender name, skip this message
                        continue

                # Extract message text
                try:
                    message_text_element = message_element.find_element(By.CSS_SELECTOR, 'div.p-rich_text_section')
                    message_text = message_text_element.text.strip()
                    print("message_text:", message_text)
                except NoSuchElementException:
                    message_text = ''
                    print('Message text not found.')

                # Update the last processed message ID
                last_processed_message_id = message_id

                # Check if the message is from you
                if sender_name.lower() == 'pearl hulbert'.lower() and sender_name != '':
                    print(f'Message from self detected:')
                    print(f'Sender: {sender_name}')
                    print(f'Message: {message_text}')
                    print(f'Message ID: {message_id}')

                    # Ask the user if they want to send a follow-up message
                    send_follow_up = input('Do you want to send a follow-up message? (y/n): ').strip().lower()
                    if send_follow_up == 'y':
                        # Prompt the user for a follow-up message
                        user_response = input('Enter your follow-up message: ')

                        # Send the user's response in Slack
                        try:
                            # Find the message input area
                            message_input = driver.find_element(By.CSS_SELECTOR, 'div.ql-editor[contenteditable="true"]')
                            # Click on the message input area to focus
                            message_input.click()
                            # Enter the user's response
                            message_input.send_keys(user_response)
                            # Send the message by pressing Enter
                            message_input.send_keys(Keys.RETURN)
                            print('Follow-up message sent.')
                        except Exception as e:
                            print('Failed to send follow-up message:', e)
                    else:
                        print('Follow-up message not sent.')

                    # Since we prompted the user, break after processing
                    break

                else:
                    # Message from someone else
                    print(f'New message detected:')
                    print(f'Sender: {sender_name}')
                    print(f'Message: {message_text}')
                    print(f'Message ID: {message_id}')

                    # Ask the user if they want to reply
                    send_reply = input('Do you want to reply? (y/n): ').strip().lower()
                    if send_reply == 'y':
                        # Prompt the user for a reply
                        user_response = input('Enter your reply: ')

                        # Send the user's response in Slack
                        try:
                            # Find the message input area
                            message_input = driver.find_element(By.CSS_SELECTOR, 'div.ql-editor[contenteditable="true"]')
                            # Click on the message input area to focus
                            message_input.click()
                            # Enter the user's response
                            message_input.send_keys(user_response)
                            # Send the message by pressing Enter
                            message_input.send_keys(Keys.RETURN)
                            print('Message sent.')
                        except Exception as e:
                            print('Failed to send message:', e)
                    else:
                        print('Reply not sent.')

                    # Since we processed the new message, break after processing
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
