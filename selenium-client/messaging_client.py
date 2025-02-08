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
import urllib.parse  # For parsing URLs

from slack_client import SlackClient
from instagram_client import InstagramClient

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
   

def derive_salt(sender_name, pepper):
    """
    Derives a deterministic salt based on the sender's name and a secret pepper.
    """
    return hmac.new(
        key=pepper.encode('utf-8'),
        msg=sender_name.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()[:16]  # Use the first 16 bytes as the salt

def hash_sender_name(sender_name, salt, pepper):
    """
    Hashes the sender's name using SHA-256 with a derived salt and pepper.
    """
    hasher = hashlib.sha256()
    hasher.update(sender_name.encode('utf-8') + salt + pepper.encode('utf-8'))
    return hasher.hexdigest()

def hash_sender_name_with_salt(sender_name):
    # Derive the salt for this sender
    salt = derive_salt(sender_name, PEPPER)
    # Hash the sender's name
    hashed_sender_name = hash_sender_name(sender_name, salt, PEPPER)
    return hashed_sender_name


@sio.on("sendSelectedResponse", namespace="/messaging")
def on_send_selected_response(data):
    selected_response = data.get("selected_response")
    if selected_response:
        logger.info(f"Received selected response: {selected_response}")
        send_response_to_slack(selected_response)
    else:
        logger.error("Received sendSelectedResponse event without selected_response")


def notify_chat_changed_instagram(new_chat_id):
    """
    Notify that the chat has changed. Currently, it logs the change.
    """
    logger.info(f"Chat changed to: {new_chat_id}")


def messaging_client(mode='slack'):
    if mode == 'instagram':
        logger.info("Using Instagram logic.")
        driver = initialize_selenium_instagram()
        client = InstagramClient(driver)
    else:
        logger.info("Using Slack logic.")
        driver = initialize_selenium_slack()
        client = SlackClient(driver)

    # Now reuse the same flow:
    previous_chat_id = client.get_current_chat_id()
    previous_thread_open = client.is_thread_open()
    last_message_from_me_ts_float = client.find_last_message_from_me()
    last_processed_ts_float = last_message_from_me_ts_float

    messages_to_process = client.collect_messages_after(None) if previous_thread_open else client.collect_messages_after(last_message_from_me_ts_float)
    if messages_to_process:
        last_processed_ts_float = float(messages_to_process[-1]['message_id'])

    for message in messages_to_process:
        content = message['content']
        timestamp = message['timestamp']
        hashed_sender_name = message['hashed_sender_name']
        logger.info(f'Processing message: "{content}" at {timestamp} from {hashed_sender_name}')
        client.send_message_via_websocket(content, timestamp, hashed_sender_name)

    while running:
        try:
            current_chat_id = client.get_current_chat_id()
            current_thread_open = client.is_thread_open()

            if current_chat_id != previous_chat_id or current_thread_open != previous_thread_open:
                logger.info("Chat or thread state changed. Resetting state.")
                previous_chat_id = current_chat_id
                client.notify_chat_changed(current_chat_id)
                last_message_from_me_ts_float = client.find_last_message_from_me()
                last_processed_ts_float = last_message_from_me_ts_float
                messages_to_process = client.collect_messages_after(None) if current_thread_open else client.collect_messages_after(last_message_from_me_ts_float)
                if messages_to_process:
                    last_processed_ts_float = float(messages_to_process[-1]['message_id'])

                for message in messages_to_process:
                    content = message['content']
                    timestamp = message['timestamp']
                    hashed_sender_name = message['hashed_sender_name']
                    logger.info(f'Processing message: "{content}" at {timestamp} from {hashed_sender_name}')
                    client.send_message_via_websocket(content, timestamp, hashed_sender_name)

            else:
                new_messages = client.detect_new_messages(last_processed_ts_float)
                if new_messages:
                    for message in new_messages:
                        message_id = message['message_id']
                        content = message['content']
                        timestamp = message['timestamp']
                        hashed_sender_name = message['hashed_sender_name']
                        logger.info(f'New message detected: "{content}" at {timestamp}')
                        client.send_message_via_websocket(content, timestamp, hashed_sender_name)
                        last_processed_ts_float = float(message_id)
                else:
                    logger.debug("No new messages detected.")

            previous_thread_open = current_thread_open
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            logger.exception("Error in main loop.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['slack', 'instagram'], default='slack',
                        help='Messaging client mode (slack or instagram).')
    args = parser.parse_args()

    try:
        messaging_client(mode=args.mode)
    except Exception as e:
        logger.exception("Failed to start messaging client.")
