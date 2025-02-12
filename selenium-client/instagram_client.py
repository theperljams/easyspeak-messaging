import logging
import time
import urllib.parse
import socketio
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# WebSocket Client Initialization
sio = socketio.Client()
WEBSOCKET_SERVER_URL = "http://localhost:3000"
USER_ID = "pearl@easyspeak-aac.com"
POLL_INTERVAL = 5  # Polling interval in seconds

# Flag to control the main loop
running = True

def initialize_selenium(driver):
    return driver  # Assume driver is already connected

def get_current_chat_id(driver):
    """ Extract chat ID from the Instagram URL. """
    try:
        current_url = driver.current_url
        logger.info(f"Current URL: {current_url}")
        parsed_url = urllib.parse.urlparse(current_url)
        parts = parsed_url.path.strip('/').split('/')
        if len(parts) >= 3 and parts[0] == 'direct' and parts[1] == 't':
            chat_id = parts[2]
            logger.info(f"Current chat ID: {chat_id}")
            return chat_id
        return None
    except Exception as e:
        logger.exception("Failed to extract chat ID.")
        return None

def notify_chat_changed(chat_id):
    """ Notify backend of chat ID change. """
    try:
        sio.emit("chatChanged", {"new_chat_id": chat_id})
        logger.info(f"Emitted chatChanged event for chat_id: {chat_id}")
    except Exception as e:
        logger.exception("Failed to emit chatChanged event.")

def extract_sender_name(message):
    """ Extract sender name from message element. """
    try:
        sender_element = message.find_element(By.XPATH, './/h5/span')
        return sender_element.text.strip()
    except NoSuchElementException:
        return "Unknown"

def extract_message_text(message):
    """ Extract message text from message element. """
    try:
        text_element = message.find_element(By.XPATH, './/div[@dir="auto" and not(ancestor::h5)]')
        return text_element.text.strip()
    except NoSuchElementException:
        return ""

def collect_new_messages(driver, last_processed_time):
    """ Collect new messages after the last processed timestamp. """
    try:
        message_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
        messages = []
        
        for message in message_elements:
            sender = extract_sender_name(message)
            content = extract_message_text(message)
            timestamp = time.time()  # Instagram messages lack timestamps, so use current time
            
            if sender and content and timestamp > last_processed_time:
                messages.append({
                    'sender_name': sender,
                    'content': content,
                    'timestamp': timestamp
                })
                last_processed_time = timestamp
        
        return messages, last_processed_time
    except Exception as e:
        logger.exception("Error collecting messages.")
        return [], last_processed_time

def send_message_to_backend(content, timestamp, sender_name):
    """ Send new messages to the WebSocket backend. """
    try:
        sio.emit("newMessage", {
            "content": content,
            "timestamp": timestamp,
            "user_id": USER_ID,
            "hashed_sender_name": sender_name
        })
        logger.info(f"Sent message via WebSocket: {content}")
    except Exception as e:
        logger.exception("Failed to send message via WebSocket.")

def send_response_to_instagram(driver, response):
    """ Send response message to Instagram. """
    try:
        wait = WebDriverWait(driver, 10)
        message_input = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[contains(@aria-label,'Message')]")))
        message_input.click()
        message_input.send_keys(response)
        message_input.send_keys(Keys.ENTER)
        logger.info(f"Sent response to Instagram: {response}")
    except Exception as e:
        logger.exception("Failed to send response to Instagram.")

@sio.on("sendSelectedResponse")
def on_send_selected_response(data):
    """ Handle response from backend and send to Instagram. """
    response = data.get("selected_response")
    if response:
        send_response_to_instagram(driver, response)
    else:
        logger.error("Received sendSelectedResponse event without content.")

def messaging_client(driver):
    global running
    
    try:
        sio.connect(f"{WEBSOCKET_SERVER_URL}")
        logger.info("Connected to WebSocket server.")
    except Exception as e:
        logger.exception("Failed to connect to WebSocket.")
        return
    
    driver = initialize_selenium(driver)
    previous_chat_id = get_current_chat_id(driver)
    last_processed_time = 0
    
    while running:
        try:
            current_chat_id = get_current_chat_id(driver)
            
            if current_chat_id != previous_chat_id:
                logger.info("Chat changed. Resetting state.")
                notify_chat_changed(current_chat_id)
                previous_chat_id = current_chat_id
                last_processed_time = 0  # Reset message tracking
            
            new_messages, last_processed_time = collect_new_messages(driver, last_processed_time)
            for message in new_messages:
                send_message_to_backend(message['content'], message['timestamp'], message['sender_name'])
            
        except Exception as e:
            logger.exception("Error in main loop.")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    from selenium import webdriver
    driver = webdriver.Chrome()
    messaging_client(driver)
