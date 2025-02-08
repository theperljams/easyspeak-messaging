import logging
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

class InstagramClient:
    def __init__(self, driver):
        self.driver = driver
    
    def find_last_you_message_index_instagram(messages):
        """
        Find the index of the last message sent by 'You' or 'You sent'.
        """
        for i in range(len(messages)-1, -1, -1):  # Search backwards
            if messages[i]['sender_name'] in ['You', 'You sent']:
                return i
        return -1  # Return -1 if no "You" messages found

    def process_new_messages_instagram(messages):
        """
        Process only messages after the last 'You' message to avoid duplicates.
        """
        last_you_idx = find_last_you_message_index_instagram(messages)
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

    def handle_response_to_send_instagram(data):
        """
        Handle incoming responses from the back end to send to Instagram.
        """
        try:
            response = data.get('response')
            if response:
                send_response_to_instagram(response)
        except Exception as e:
            logger.exception("Error handling response to send.")

    def send_response_to_instagram(self, response):
        """
        Send the response message to Instagram.
        """
        try:
            wait = WebDriverWait(self.driver, 10)
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

    
    def get_current_chat_id(self):
        """
        Extract the chat ID from the current URL.
        """
        try:
            current_url = self.driver.current_url
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
            logger.exception("Failed to extract chat ID from URL.")
            return None
    
    def collect_new_messages(self):
        """Collect all messages from current chat"""
        try:
            # Messages are within div elements with role='row'
            message_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
            messages = []
            
            for index, element in enumerate(message_elements, start=1):
                try:
                    sender = self.extract_sender_name(element)
                    content = self.extract_message_text(element)
                    if sender != "You" and content and (sender, content) not in seen_messages:
                        messages.append({
                            'sender_name': sender,
                            'content': content
                        })
                except Exception as e:
                    logger.exception(f"Error processing message element {index}.")
            
            logger.info(f"Collected {len(messages)} new messages.")
            print(messages)
                    
            return messages
            
        except Exception as e:
            logger.error(f"Error collecting messages: {str(e)}")
            return []
    
    def extract_sender_name(self, message):
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

    def extract_message_text(self, message):
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