# messaging_client.py

import time
import socketio  # For WebSocket communication
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # For simulating key presses
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import logging
import signal
import sys
import uuid
import hmac
import hashlib

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
WEBSOCKET_SERVER_URL = os.getenv("WEBSOCKET_SERVER_URL", "http://localhost:3000")
USER_ID = os.getenv(
    "USER_ID", "pearl@easyspeak-aac.com"
)  # Replace with your actual user ID or email
PEPPER = os.getenv('PEPPER', 'SuperSecretPepperValue')  # Securely store this in production
POLL_INTERVAL = 5  # Seconds between polling requests

# Initialize Socket.IO client
sio = socketio.Client()

# Flag to control the main loop
running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutting down messaging client...")
    running = False
    sio.disconnect()
    try:
        driver.quit()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@sio.event(namespace="/messaging")
def connect():
    logger.info("Connected to WebSocket server.")

@sio.event(namespace="/messaging")
def connect_error(data):
    logger.error("Connection failed:", data)

@sio.event(namespace="/messaging")
def disconnect():
    logger.info("Disconnected from WebSocket server.")

def initialize_selenium():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "localhost:9222")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def find_last_message_from_me(driver):
    """
    Finds the last message sent by 'me' in Slack.

    Args:
        driver: Selenium WebDriver instance.

    Returns:
        last_message_from_me_id: The message ID (timestamp) of the last message sent by 'me'.
    """
    try:
        # Locate message elements
        messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")

        for message in reversed(messages):  # Start from oldest to newest
            # Extract sender name
            try:
                sender_element = message.find_element(By.CSS_SELECTOR, "button.c-message__sender_button")
                sender_name = sender_element.text.strip()
            except NoSuchElementException:
                try:
                    sender_span = message.find_element(
                        By.CSS_SELECTOR, 'span.offscreen[data-qa^="aria-labelledby"]'
                    )
                    sender_name = sender_span.text.strip()
                except NoSuchElementException:
                    sender_name = "Unknown"

            # Check if the sender is 'me'
            if "pearl" in sender_name.lower():
                # Extract message ID (timestamp)
                try:
                    timestamp_element = message.find_element(By.CSS_SELECTOR, "a.c-timestamp")
                    message_id = timestamp_element.get_attribute("data-ts")
                except NoSuchElementException:
                    message_id = None

                logger.info(f"Found last message from 'me' with ID: {message_id}")
                return message_id

        # If no message from 'me' is found
        logger.info("No previous message from 'me' found.")
        return None

    except Exception as e:
        logger.exception("Error finding last message from 'me'.")
        return None

def derive_salt(sender_name, pepper):
    """
    Derives a deterministic salt based on the sender's name and a secret pepper.

    Args:
        sender_name (str): The sender's name.
        pepper (str): The secret pepper.

    Returns:
        bytes: A 16-byte salt derived from the sender's name and pepper.
    """
    return hmac.new(
        key=pepper.encode('utf-8'),
        msg=sender_name.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()[:16]  # Use the first 16 bytes as the salt

def hash_sender_name(sender_name, salt, pepper):
    """
    Hashes the sender's name using SHA-256 with a derived salt and pepper.

    Args:
        sender_name (str): The sender's name.
        salt (bytes): The salt derived from the sender's name.
        pepper (str): The secret pepper.

    Returns:
        str: The hexadecimal digest of the hashed sender's name.
    """
    hasher = hashlib.sha256()
    hasher.update(sender_name.encode('utf-8') + salt + pepper.encode('utf-8'))
    return hasher.hexdigest()

def collect_messages_after(driver, last_message_from_me_id):
    """
    Collects messages after the message with the given message ID.

    Args:
        driver: Selenium WebDriver instance.
        last_message_from_me_id: The message ID (timestamp) of the last message sent by 'me'.

    Returns:
        messages_list: A list of messages (dictionaries) sent after last_message_from_me_id.
    """
    try:
        # Locate message elements
        messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
        messages_list = []

        # Flag to start collecting messages
        collecting = False

        # Go through messages from oldest to newest
        for message in messages:
            # Extract message ID (timestamp)
            try:
                timestamp_element = message.find_element(By.CSS_SELECTOR, "a.c-timestamp")
                message_id = timestamp_element.get_attribute("data-ts")
            except NoSuchElementException:
                message_id = str(uuid.uuid4())  # Fallback to UUID if timestamp not found

            # If we have reached the last message from 'me', start collecting
            if last_message_from_me_id and message_id == last_message_from_me_id:
                collecting = True
                continue  # Skip the message from 'me'

            if collecting or last_message_from_me_id is None:
                # Extract sender name
                try:
                    sender_element = message.find_element(By.CSS_SELECTOR, "button.c-message__sender_button")
                    sender_name = sender_element.text.strip()
                except NoSuchElementException:
                    try:
                        sender_span = message.find_element(
                            By.CSS_SELECTOR, 'span.offscreen[data-qa^="aria-labelledby"]'
                        )
                        sender_name = sender_span.text.strip()
                    except NoSuchElementException:
                        sender_name = "Unknown"

                # Extract message content
                try:
                    message_text_element = message.find_element(By.CSS_SELECTOR, "div.p-rich_text_section")
                    message_text = message_text_element.text.strip()
                except NoSuchElementException:
                    message_text = ""

                # Extract timestamp
                try:
                    ts_float = float(message_id)
                    timestamp = int(ts_float * 1000)
                except ValueError:
                    timestamp = None

                # Skip messages sent by 'me' to prevent feedback loops
                if "pearl" in sender_name.lower():
                    continue

                # Derive the salt for this sender
                salt = derive_salt(sender_name, PEPPER)

                # Hash the sender's name
                hashed_sender_name = hash_sender_name(sender_name, salt, PEPPER)

                # Add message to the list
                messages_list.append({
                    'message_id': message_id,
                    'content': message_text,
                    'timestamp': timestamp,
                    'hashed_sender_name': hashed_sender_name,
                })

        return messages_list

    except Exception as e:
        logger.exception("Error collecting messages after last message from 'me'.")
        return []

def detect_new_messages(driver, last_processed_ts_float):
    """
    Detects new messages in Slack after the last processed message timestamp.

    Args:
        driver: Selenium WebDriver instance.
        last_processed_ts_float: The timestamp of the last processed message as float.

    Returns:
        new_messages: A list of new messages (dictionaries) after last_processed_ts_float.
    """
    try:
        # Locate message elements
        messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
        new_messages = []

        # Go through messages from oldest to newest
        for message in messages:
            # Extract message ID (timestamp)
            try:
                timestamp_element = message.find_element(By.CSS_SELECTOR, "a.c-timestamp")
                message_id = timestamp_element.get_attribute("data-ts")
                message_ts_float = float(message_id)
            except (NoSuchElementException, ValueError):
                message_id = str(uuid.uuid4())  # Fallback to UUID if timestamp not found
                message_ts_float = None

            # Skip messages before last_processed_ts_float
            if last_processed_ts_float is not None and message_ts_float is not None:
                if message_ts_float <= last_processed_ts_float:
                    continue

            # Extract sender name
            try:
                sender_element = message.find_element(By.CSS_SELECTOR, "button.c-message__sender_button")
                sender_name = sender_element.text.strip()
            except NoSuchElementException:
                try:
                    sender_span = message.find_element(
                        By.CSS_SELECTOR, 'span.offscreen[data-qa^="aria-labelledby"]'
                    )
                    sender_name = sender_span.text.strip()
                except NoSuchElementException:
                    sender_name = "Unknown"

            # Extract message content
            try:
                message_text_element = message.find_element(By.CSS_SELECTOR, "div.p-rich_text_section")
                message_text = message_text_element.text.strip()
            except NoSuchElementException:
                message_text = ""

            # Extract timestamp
            if message_ts_float is not None:
                timestamp = int(message_ts_float * 1000)
            else:
                timestamp = None

            # Skip messages sent by 'me' to prevent feedback loops
            if "pearl" in sender_name.lower():
                continue

            # Derive the salt for this sender
            salt = derive_salt(sender_name, PEPPER)

            # Hash the sender's name
            hashed_sender_name = hash_sender_name(sender_name, salt, PEPPER)

            # Add message to the list
            new_messages.append({
                'message_id': message_id,
                'content': message_text,
                'timestamp': timestamp,
                'hashed_sender_name': hashed_sender_name,
            })

        # Return new messages sorted by timestamp
        new_messages.sort(key=lambda x: float(x['message_id']))
        return new_messages

    except Exception as e:
        logger.exception("Error detecting new messages.")
        return []

def send_message_via_websocket(content, timestamp, hashed_sender_name):
    """
    Sends the new message to the back end via WebSocket.

    Args:
        content (str): The content of the message.
        timestamp (int): The timestamp of the message in milliseconds since epoch.
        hashed_sender_name (str): The hashed sender's name.
    """
    try:
        # Send the content, timestamp, and hashed sender's name
        sio.emit(
            "newMessage",
            {
                "content": content,
                "timestamp": timestamp,
                "user_id": USER_ID,
                "hashed_sender_name": hashed_sender_name,
            },
            namespace="/messaging",
        )
        logger.info(f'Sent message via WebSocket: "{content}" at {timestamp}')
    except Exception as e:
        logger.exception("Failed to send message via WebSocket.")

def send_response_to_slack(response):
    """
    Uses Selenium to send the selected response to Slack.

    Args:
        response (str): The selected response to send.
    """
    try:
        # Wait for the message input to be available
        wait = WebDriverWait(driver, 10)

        # Check if a thread is open by looking for the thread input box
        try:
            # Locate the thread input box
            message_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        'div.p-threads_footer__input div[data-qa="message_input"] div.ql-editor',
                    )
                )
            )
            logger.info("Thread input box found. Sending response to thread.")
        except (TimeoutException, NoSuchElementException):
            # If thread input box is not found, use the main message input box
            message_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        'div[data-qa="message_input"] div.ql-editor',
                    )
                )
            )
            logger.info("Thread input box not found. Sending response to main chat.")

        # Click to focus
        message_input.click()

        # Type the response
        message_input.send_keys(response)

        # Manually trigger input events (if necessary)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", message_input
        )
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('keyup', { bubbles: true }));", message_input
        )

        # Wait a moment for the input to be processed
        time.sleep(0.5)

        # Simulate pressing Enter to send the message
        message_input.send_keys(Keys.ENTER)

        logger.info(f"Sent response to Slack: {response}")

    except NoSuchElementException as e:
        logger.exception("Failed to locate Slack message input.")
    except ElementNotInteractableException as e:
        logger.exception("Slack message input not interactable.")
    except Exception as e:
        logger.exception("Failed to send response to Slack.")

@sio.on("sendSelectedResponse", namespace="/messaging")
def on_send_selected_response(data):
    selected_response = data.get("selected_response")
    if selected_response:
        logger.info(f"Received selected response: {selected_response}")
        send_response_to_slack(selected_response)
    else:
        logger.error("Received sendSelectedResponse event without selected_response")

def messaging_client():
    global driver

    # Connect to WebSocket server
    try:
        sio.connect(f"{WEBSOCKET_SERVER_URL}/messaging", namespaces=["/messaging"])
        logger.info(f"Connecting to WebSocket server: {WEBSOCKET_SERVER_URL}/messaging")
    except Exception as e:
        logger.exception("Failed to connect to WebSocket server.")
        sys.exit(1)

    # Initialize Selenium WebDriver
    driver = initialize_selenium()
    logger.info("Selenium WebDriver initialized and connected to Chrome.")

    # Initialize last_message_from_me_id
    last_message_from_me_id = find_last_message_from_me(driver)

    # Initialize last_processed_ts_float
    last_processed_ts_float = None

    # Collect messages after last message from 'me'
    messages_to_process = collect_messages_after(driver, last_message_from_me_id)

    # Process messages in chronological order
    for message in messages_to_process:
        message_id = message['message_id']
        content = message['content']
        timestamp = message['timestamp']
        hashed_sender_name = message['hashed_sender_name']

        logger.info(f'Processing message: "{content}" at {timestamp} (ID: {message_id})')
        # Send the message to the back end via WebSocket
        send_message_via_websocket(content, timestamp, hashed_sender_name)

        # Update the last_processed_ts_float
        last_processed_ts_float = float(message_id)

    # Main loop
    while running:
        try:
            # Detect new messages after last_processed_ts_float
            new_messages = detect_new_messages(driver, last_processed_ts_float)
            if new_messages:
                for message in new_messages:
                    message_id = message['message_id']
                    content = message['content']
                    timestamp = message['timestamp']
                    hashed_sender_name = message['hashed_sender_name']

                    logger.info(f'New message detected: "{content}" at {timestamp} (ID: {message_id})')

                    # Send the message to the back end via WebSocket
                    send_message_via_websocket(content, timestamp, hashed_sender_name)

                    # Update the last_processed_ts_float
                    last_processed_ts_float = float(message_id)
            else:
                logger.debug("No new messages detected.")
        except Exception as e:
            logger.exception("Error in main loop.")

        # Poll every POLL_INTERVAL seconds
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        # Start the messaging client
        messaging_client()
    except Exception as e:
        logger.exception("Failed to start messaging client.")
