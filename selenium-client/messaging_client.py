# messaging_client.py

import time
import socketio  # For WebSocket communication
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException
import os
import logging
import signal
import sys
import uuid

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
WEBSOCKET_SERVER_URL = os.getenv('WEBSOCKET_SERVER_URL', 'http://localhost:3000')
USER_ID = os.getenv('USER_ID', 'pearl@easyspeak-aac.com')  # Replace with your actual user ID or email
POLL_INTERVAL = 5  # Seconds between polling requests
MAX_POLLS = 60  # Maximum number of polls before timing out

# Initialize Socket.IO client
sio = socketio.Client()

# Flag to control the main loop
running = True

def signal_handler(sig, frame):
    global running
    logger.info('Shutting down messaging client...')
    running = False
    sio.disconnect()
    try:
        driver.quit()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@sio.event(namespace='/messaging')
def connect():
    logger.info('Connected to WebSocket server.')

@sio.event(namespace='/messaging')
def connect_error(data):
    logger.error('Connection failed:', data)

@sio.event(namespace='/messaging')
def disconnect():
    logger.info('Disconnected from WebSocket server.')

def initialize_selenium():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "localhost:9222")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def detect_new_message(driver, last_message_id):
    """
    Detects the latest message in Slack.

    Args:
        driver: Selenium WebDriver instance.
        last_message_id: The ID of the last processed message.

    Returns:
        Tuple (message_id, content) or (None, None) if no new message.
    """
    try:
        # Locate message elements
        messages = driver.find_elements(By.CSS_SELECTOR, 'div.c-message_kit__background')
        if not messages:
            return (None, None)

        # Assume the last message is the latest
        latest_message = messages[-1]

        # Extract message ID (timestamp)
        try:
            timestamp_element = latest_message.find_element(By.CSS_SELECTOR, 'a.c-timestamp')
            message_id = timestamp_element.get_attribute('data-ts')
        except NoSuchElementException:
            message_id = str(uuid.uuid4())  # Fallback to UUID if timestamp not found

        # Check if this message has been processed
        if message_id == last_message_id:
            return (None, None)

        # Extract sender name
        try:
            sender_element = latest_message.find_element(By.CSS_SELECTOR, 'button.c-message__sender_button')
            sender_name = sender_element.text.strip()
        except NoSuchElementException:
            try:
                sender_span = latest_message.find_element(By.CSS_SELECTOR, 'span.offscreen[data-qa^="aria-labelledby"]')
                sender_name = sender_span.text.strip()
            except NoSuchElementException:
                sender_name = 'Unknown'

        # Extract message content
        try:
            message_text_element = latest_message.find_element(By.CSS_SELECTOR, 'div.p-rich_text_section')
            message_text = message_text_element.text.strip()
        except NoSuchElementException:
            message_text = ''

        # Skip messages sent by self to prevent feedback loops
        if sender_name.lower() == USER_ID.lower():
            return (None, None)

        return (message_id, message_text)

    except Exception as e:
        logger.exception('Error detecting new message.')
        return (None, None)

def send_message_via_websocket(content):
    """
    Sends the new message to the back end via WebSocket.

    Args:
        content (str): The content of the message.
    """
    try:
        # Only send the content of the message
        sio.emit('newMessage', {
            'content': content,
            'user_id': USER_ID
        }, namespace='/messaging')
        logger.info(f'Sent message via WebSocket: {content}')
    except Exception as e:
        logger.exception('Failed to send message via WebSocket.')

def send_response_to_slack(response):
    """
    Uses Selenium to send the selected response to Slack.

    Args:
        response (str): The selected response to send.
    """
    try:
        # Locate the message input box
        message_input = driver.find_element(By.CSS_SELECTOR, 'div[data-qa="message_input"] div.ql-editor')

        # Click to focus
        message_input.click()

        # Clear any existing text (optional)
        # message_input.clear()

        # Type the response
        message_input.send_keys(response)

        # Locate the send button and click it
        send_button = driver.find_element(By.CSS_SELECTOR, 'button[data-qa="texty_send_button"]')
        send_button.click()

        logger.info(f'Sent response to Slack: {response}')

    except NoSuchElementException as e:
        logger.exception('Failed to locate Slack message input or send button.')
    except ElementNotInteractableException as e:
        logger.exception('Slack message input or send button not interactable.')
    except Exception as e:
        logger.exception('Failed to send response to Slack.')

@sio.on('sendSelectedResponse', namespace='/messaging')
def on_send_selected_response(data):
    selected_response = data.get('selected_response')
    if selected_response:
        logger.info(f'Received selected response: {selected_response}')
        send_response_to_slack(selected_response)
    else:
        logger.error('Received sendSelectedResponse event without selected_response')

def messaging_client():
    global driver

    # Connect to WebSocket server
    try:
        sio.connect(f'{WEBSOCKET_SERVER_URL}/messaging', namespaces=['/messaging'])
        logger.info(f'Connecting to WebSocket server: {WEBSOCKET_SERVER_URL}/messaging')
    except Exception as e:
        logger.exception('Failed to connect to WebSocket server.')
        sys.exit(1)

    # Initialize Selenium WebDriver
    driver = initialize_selenium()
    logger.info('Selenium WebDriver initialized and connected to Chrome.')

    # Initialize last_message_id
    last_message_id = None

    while running:
        try:
            message_id, content = detect_new_message(driver, last_message_id)
            if message_id and content:
                logger.info(f'New message detected: {content} (ID: {message_id})')
                # Send the message to the back end via WebSocket
                send_message_via_websocket(content)
                # Update the last_message_id
                last_message_id = message_id
            else:
                logger.debug('No new messages detected.')
        except Exception as e:
            logger.exception('Error in main loop.')

        # Poll every POLL_INTERVAL seconds
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    try:
        # Start the messaging client
        messaging_client()
    except Exception as e:
        logger.exception('Failed to start messaging client.')
