from selenium import webdriver
from slack_client import SlackClient
from instagram_client import InstagramClient
import argparse
import time
import logging
from selenium.webdriver.chrome.options import Options

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_selenium():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "localhost:9222")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def messaging_client(mode='slack'):
    driver = initialize_selenium()
    client = SlackClient(driver) if mode == 'slack' else InstagramClient(driver)

    previous_chat_id = client.get_current_chat_id()
    last_processed_ts_float = 0

    while True:
        try:
            current_chat_id = client.get_current_chat_id()
            if current_chat_id != previous_chat_id:
                client.notify_chat_changed(current_chat_id)
                previous_chat_id = current_chat_id
                last_processed_ts_float = 0

            new_messages = client.detect_new_messages(last_processed_ts_float)
            for message in new_messages:
                client.send_message_via_websocket(message['content'], message['timestamp'], message['hashed_sender_name'])
                last_processed_ts_float = float(message['message_id'])

            time.sleep(5)
        except Exception as e:
            logger.exception("Error in main loop.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['slack', 'instagram'], default='slack')
    args = parser.parse_args()
    messaging_client(args.mode)
