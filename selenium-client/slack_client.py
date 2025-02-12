from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import uuid
import urllib.parse
import logging
from messaging_client_base import MessagingClientBase

logger = logging.getLogger(__name__)

class SlackClient(MessagingClientBase):
    def __init__(self, driver):
        super().__init__(driver)
        logger.info("Initialized SlackClient")

    def get_current_chat_id(self):
        """Returns Slack chat ID from the URL."""
        try:
            current_url = self.driver.current_url
            parsed_url = urllib.parse.urlparse(current_url)
            channel_id = urllib.parse.parse_qs(parsed_url.query).get('channel', [None])[0]
            return channel_id or parsed_url.path
        except Exception as e:
            logger.exception("Error getting Slack chat ID.")
            return None

    def is_thread_open(self):
        """Checks if a Slack thread is open."""
        try:
            thread_pane = self.driver.find_element(By.CSS_SELECTOR, 'div.p-threads_view')
            return thread_pane.is_displayed()
        except NoSuchElementException:
            return False

    def collect_messages_after(self, last_message_from_me_ts_float):
        """Collects Slack messages after the last message from 'me'."""
        messages = self.driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
        collected_messages = []

        for message in messages:
            try:
                timestamp_element = message.find_element(By.CSS_SELECTOR, "a.c-timestamp")
                message_id = timestamp_element.get_attribute("data-ts")
                message_ts_float = float(message_id)

                if message_ts_float <= last_message_from_me_ts_float:
                    continue

                sender_name = message.find_element(By.CSS_SELECTOR, "span.c-message__sender").text
                content = message.find_element(By.CSS_SELECTOR, "div.c-message_kit__blocks").text.strip()

                collected_messages.append({
                    'message_id': message_id,
                    'content': content,
                    'timestamp': message_ts_float,
                    'hashed_sender_name': sender_name
                })
            except NoSuchElementException:
                continue
        
        return collected_messages

    def detect_new_messages(self, last_processed_ts_float):
        return self.collect_messages_after(last_processed_ts_float)
