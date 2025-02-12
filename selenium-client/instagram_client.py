from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
import time
import logging
import urllib.parse
from messaging_client_base import MessagingClientBase

logger = logging.getLogger(__name__)

class InstagramClient(MessagingClientBase):
    def __init__(self, driver):
        super().__init__(driver)
        logger.info("Initialized InstagramClient")

    def get_current_chat_id(self):
        """Returns Instagram chat ID from the URL."""
        try:
            current_url = self.driver.current_url
            parts = urllib.parse.urlparse(current_url).path.strip('/').split('/')
            return parts[2] if len(parts) >= 3 and parts[0] == 'direct' else None
        except Exception as e:
            logger.exception("Error getting Instagram chat ID.")
            return None

    def collect_messages_after(self, last_message_from_me_ts_float):
        """Collects new Instagram messages."""
        message_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
        collected_messages = []

        for message in message_elements:
            try:
                sender = message.find_element(By.XPATH, './/h5/span').text.strip()
                content = message.find_element(By.XPATH, './/div[@dir="auto"]').text.strip()
                timestamp = time.time()  # No timestamp available, use system time

                collected_messages.append({
                    'message_id': str(timestamp),
                    'content': content,
                    'timestamp': timestamp,
                    'hashed_sender_name': sender
                })
            except NoSuchElementException:
                continue
        
        return collected_messages

    def detect_new_messages(self, last_processed_ts_float):
        return self.collect_messages_after(last_processed_ts_float)
