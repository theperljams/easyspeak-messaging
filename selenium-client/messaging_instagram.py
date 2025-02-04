import time
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
import urllib.parse  # For parsing URLs
import socketio  # For WebSocket communication

# Setup Logging with INFO level for concise output
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
USER_ID = os.getenv("USER_ID", "pearl@easyspeak-aac.com")  # Replace with your actual user ID or email
WEBSOCKET_SERVER_URL = os.getenv("WEBSOCKET_SERVER_URL", "http://localhost:5000")  # Replace with your backend URL

# Initialize a set to keep track of seen messages to avoid duplicates
seen_messages = set()

# Initialize Socket.IO client
sio = socketio.Client()

@sio.event
def connect():
    logger.info("Connected to WebSocket server.")

@sio.event
def connect_error(data):
    logger.error(f"Connection failed: {data}")

@sio.event
def disconnect():
    logger.info("Disconnected from WebSocket server.")

def signal_handler(sig, frame):
    logger.info("Shutting down messaging client...")
    try:
        sio.disconnect()
        driver.quit()
    except Exception:
        pass
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    
    # Connect to the existing Chrome instance with remote debugging
    chrome_options.add_experimental_option("debuggerAddress", "localhost:9222")
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def extract_sender_name_instagram(message):
    """
    Extract the sender's name from a message element.
    """
    try:
        sender_element = message.find_element(By.XPATH, './/h5/span')
        sender_name = sender_element.text.strip()
        logger.info(f"Extracted sender name: {sender_name}")
    except NoSuchElementException:
        sender_name = "Unknown"
        logger.info("Sender name not found; defaulting to 'Unknown'.")
    except Exception as e:
        logger.exception("Unexpected error while extracting sender name.")
        sender_name = "Unknown"
    return sender_name

def extract_message_text_instagram(message):
    """
    Extract the message text from a message element.
    """
    try:
        # This XPath finds divs with dir="auto" that are not ancestors of h5 (i.e., not the sender's name)
        text_element = message.find_element(By.XPATH, './/div[@dir="auto" and not(ancestor::h5)]')
        message_text = text_element.text.strip()
        logger.info(f"Extracted message text: {message_text}")
    except NoSuchElementException:
        message_text = ""
        logger.info("Message text not found.")
    except Exception as e:
        logger.exception("Unexpected error while extracting message text.")
        message_text = ""
    return message_text

def collect_new_messages_instagram(driver):
    """Collect all messages from current chat"""
    try:
        # Messages are within div elements with role='row'
        message_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
        messages = []
        
        for index, element in enumerate(message_elements, start=1):
            try:
                sender = extract_sender_name_instagram(element)
                content = extract_message_text_instagram(element)
                if sender != "You" and content and (sender, content) not in seen_messages:
                    messages.append({
                        'sender_name': sender,
                        'content': content
                    })
                    seen_messages.add((sender, content))
            except Exception as e:
                logger.info(f"Skipped message element {index}: {str(e)}")
                continue

        
        logger.info(f"Collected {len(messages)} new messages.")
        print(messages)
                
        return messages
        
    except Exception as e:
        logger.error(f"Error collecting messages: {str(e)}")
        return []

def send_message_via_print(sender_name, content):
    """
    Instead of sending message via WebSocket, just print it.
    """
    logger.info(f'New message received: "{content}" from {sender_name}')

def get_current_chat_id_instagram(driver):
    """
    Extract the chat ID from the current URL.
    """
    try:
        current_url = driver.current_url
        logger.info(f"Current URL: {current_url}")
        parsed_url = urllib.parse.urlparse(current_url)
        parts = parsed_url.path.strip('/').split('/')
        if len(parts) >= 3 and parts[0] == 'direct' and parts[1] == 't':
            chat_id = parts[2]
            logger.info(f"Current chat ID: {chat_id}")
            return chat_id
        else:
            logger.warning("Unable to determine current chat ID from URL.")
            return None
    except Exception as e:
        logger.exception("Error getting current chat ID.")
        return None

def notify_chat_changed_instagram(new_chat_id):
    """
    Notify that the chat has changed. Currently, it logs the change.
    """
    logger.info(f"Chat changed to: {new_chat_id}")

def find_last_you_message_index(messages):
    """
    Find the index of the last message sent by 'You' or 'You sent'.
    """
    for i in range(len(messages)-1, -1, -1):  # Search backwards
        if messages[i]['sender_name'] in ['You', 'You sent']:
            return i
    return -1  # Return -1 if no "You" messages found

def process_new_messages(messages):
    """
    Process only messages after the last 'You' message to avoid duplicates.
    """
    last_you_idx = find_last_you_message_index(messages)
    messages_to_process = messages[last_you_idx + 1:] if last_you_idx >= 0 else messages
    
    for message in messages_to_process:
        sender_name = message['sender_name']
        content = message['content']
        logger.info(f'Processing message: "{content}" from {sender_name}')
        
        if sender_name == "Unknown":
            # Assume it's not 'You' and send it
            sio.emit('newMessage', {'content': content, 'user_id': USER_ID})
            logger.info(f'Message from "Unknown" sent to back end via WebSocket: "{content}"')
        elif sender_name not in ['You', 'You sent']:
            # It's a message from someone else, send via WebSocket
            sio.emit('newMessage', {'content': content, 'user_id': USER_ID})
            logger.info(f'Message from "{sender_name}" sent to back end via WebSocket: "{content}"')
        else:
            # It's a message from 'You', skip
            logger.info("Skipping message from 'You'.")

@sio.on('response_to_send')
def on_response_to_send(data):
    """
    Receive response to send from back end and send to Instagram.
    """
    logger.info(f"Received response to send: {data}")
    handle_response_to_send(data)

@sio.on('send_message_to_client')
def on_send_message_to_client(data):
    """
    Receive message from back end (front end user) to send to Instagram.
    """
    message = data.get('message')
    if message:
        try:
            send_response_to_instagram(message)
            logger.info(f"Sent message from front end to Instagram: {message}")
        except Exception as e:
            logger.exception("Failed to send message from front end to Instagram.")

def handle_response_to_send(data):
    """
    Handle incoming responses from the back end to send to Instagram.
    """
    try:
        response = data.get('response')
        if response:
            send_response_to_instagram(response)
    except Exception as e:
        logger.exception("Error handling response to send.")

def send_response_to_instagram(response):
    """
    Send the response message to Instagram.
    """
    try:
        wait = WebDriverWait(driver, 10)
        message_input = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//textarea[contains(@aria-label,'Message')]")
            )
        )
        message_input.click()
        message_input.send_keys(response)
        message_input.send_keys(Keys.ENTER)
        logger.info(f"Sent response to Instagram: {response}")
    except NoSuchElementException:
        logger.exception("Failed to locate Instagram message input.")
    except ElementNotInteractableException:
        logger.exception("Instagram message input not interactable.")
    except Exception as e:
        logger.exception("Failed to send response to Instagram.")

def main():
    global driver
    try:
        # Initialize Selenium WebDriver
        driver = initialize_selenium()
        logger.info("Selenium WebDriver initialized.")
        
        # Connect to WebSocket server
        sio.connect(WEBSOCKET_SERVER_URL)
        logger.info(f"Connected to WebSocket server at {WEBSOCKET_SERVER_URL}")
        
        # Allow some time for the page to load
        time.sleep(5)
        
        # Continuously collect and send messages until WebSocket connection is broken
        while sio.connected:
            current_chat_id = get_current_chat_id_instagram(driver)
            if current_chat_id:
                notify_chat_changed_instagram(current_chat_id)
            messages = collect_new_messages_instagram(driver)
            process_new_messages(messages)
            time.sleep(5)  # Adjust the sleep time as needed
        
    except Exception as e:
        logger.exception("Error in main loop.")
    finally:
        if 'driver' in locals():
            driver.quit()
        if sio.connected:
            sio.disconnect()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Failed to start messaging client.")
