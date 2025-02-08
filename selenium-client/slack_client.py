import logging
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import time
import urllib.parse
import uuid
# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class SlackClient:
    def __init__(self, driver):
        self.driver = driver

    def send_response_to_slack(self, response):
        """
        Uses Selenium to send the selected response to Slack.
        """
        try:
            # Wait for the message input to be available
            wait = WebDriverWait(self.driver, 10)

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
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", message_input
            )
            self.driver.execute_script(
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



    def slack_detect_new_messages(self, last_processed_ts_float):

        """
        Detects new messages based on the current context: DM, channel, or thread.
        """
        try:
            # Determine context
            in_dm = is_slack_dm()
            thread_open = is_thread_open()
            new_messages = []

            if thread_open:
                logger.info("Thread is open. Detecting new messages in thread up to last message from 'me'.")
                # Find the last message from 'me' in the thread
                last_message_from_me_in_thread_ts_float = find_last_message_from_me()

                # Collect messages in the thread
                messages = driver.find_elements(By.CSS_SELECTOR, "div.c-virtual_list__item--thread div.c-message_kit__background")

                # Use the timestamp of the last message from 'me' in the thread
                new_messages = detect_new_messages_from_elements(messages, last_processed_ts_float, last_message_from_me_in_thread_ts_float)
            elif in_dm:
                if last_processed_ts_float is None:
                    logger.info("No previous message from 'me' found in DM. Not detecting new messages.")
                    new_messages = []
                else:
                    logger.info("In a DM. Detecting new messages.")
                    # Collect messages in the DM
                    messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
                    new_messages = detect_new_messages_from_elements(messages, last_processed_ts_float)
            else:
                if last_processed_ts_float is None:
                    logger.info("No previous message from 'me' found in channel. Not detecting new messages.")
                    new_messages = []
                else:
                    logger.info("In a channel. Detecting new messages.")
                    # Collect messages in the channel
                    messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
                    new_messages = detect_new_messages_from_elements(messages, last_processed_ts_float)

            return new_messages

        except Exception as e:
            logger.exception("Error detecting new messages.")
            return []    



    def slack_detect_new_messages_from_elements(messages, last_processed_ts_float, last_message_from_me_ts_float_in_thread=None):
        """
        Detects new messages from given message elements after last_processed_ts_float and before last_message_from_me_ts_float_in_thread.
        """
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

            # For threads, stop collecting if message_ts_float >= last_message_from_me_ts_float_in_thread
            if last_message_from_me_ts_float_in_thread is not None and message_ts_float is not None:
                if message_ts_float >= last_message_from_me_ts_float_in_thread:
                    break  # Stop collecting further messages

            # Skip messages before or equal to last_processed_ts_float
            if last_processed_ts_float is not None and message_ts_float is not None:
                if message_ts_float <= last_processed_ts_float:
                    continue

            # Extract sender name
            sender_name = slack_extract_sender_name(message)
            # Skip messages sent by 'me' to prevent feedback loops
            if "pearl" in sender_name.lower():
                continue
            # Extract message content
            message_text = slack_extract_message_text(message)
            # Extract timestamp
            timestamp = slack_extract_timestamp(message_id)
            # Hash the sender's name
            hashed_sender_name = hash_sender_name_with_salt(sender_name)
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
        


    def slack_collect_messages_from_elements(messages, last_message_from_me_ts_float, last_message_from_me_ts_float_in_thread=None):
        """
        Collect messages sent after the last message from 'me' (or up to last message from 'me' in thread), based on timestamps.
        """
        messages_list = []

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

            # For threads, stop collecting if message_ts_float >= last_message_from_me_ts_float_in_thread
            if last_message_from_me_ts_float_in_thread is not None and message_ts_float is not None:
                if message_ts_float >= last_message_from_me_ts_float_in_thread:
                    break  # Stop collecting further messages

            # For DMs, skip messages <= last_message_from_me_ts_float
            if last_message_from_me_ts_float is not None and message_ts_float is not None:
                if message_ts_float <= last_message_from_me_ts_float:
                    continue

            # Extract sender name
            sender_name = slack_extract_sender_name(message)
            # Skip messages sent by 'me' to prevent feedback loops
            if "pearl" in sender_name.lower():
                continue
            # Extract message content
            message_text = slack_extract_message_text(message)
            # Extract timestamp
            timestamp = slack_extract_timestamp(message_id)
            # Hash the sender's name
            hashed_sender_name = hash_sender_name_with_salt(sender_name)
            # Add message to the list
            messages_list.append({
                'message_id': message_id,
                'content': message_text,
                'timestamp': timestamp,
                'hashed_sender_name': hashed_sender_name,
            })

        return messages_list
        
    
    def slack_extract_sender_name(message):
        sender_name = "Unknown"

        possible_selectors = [
            "a.c-message__sender_link",
            "button.c-message__sender_button",
            "span.c-message__sender",
            "span.offscreen[data-qa^='aria-labelledby']",
        ]

        for selector in possible_selectors:
            try:
                sender_element = message.find_element(By.CSS_SELECTOR, selector)
                sender_name = sender_element.text.strip()
                break
            except NoSuchElementException:
                continue

        sender_name = slack_normalize_sender_name(sender_name)

        if sender_name == "Unknown":
            logger.warning("Could not extract sender name for a message.")

        return sender_name

    def slack_normalize_sender_name(sender_name):
        # Remove leading/trailing whitespace
        sender_name = sender_name.strip()

        # Convert to lowercase
        sender_name = sender_name.lower()

        # Replace multiple spaces with a single space
        sender_name = ' '.join(sender_name.split())

        # Remove zero-width spaces and other invisible characters if needed
        # sender_name = sender_name.replace('\u200b', '')

        return sender_name


    def slack_extract_message_text(message):
        try:
            message_text_element = message.find_element(By.CSS_SELECTOR, "div.c-message_kit__blocks")
            message_text = message_text_element.text.strip()
        except NoSuchElementException:
            message_text = ""
        return message_text

    def slack_extract_timestamp(message_id):
        try:
            ts_float = float(message_id)
            timestamp = int(ts_float * 1000)
        except ValueError:
            timestamp = None
        return timestamp

    
    def is_slack_dm(self):
        """
        Determines if the current chat is a DM or a channel based on the aria-label attribute.
        """
        try:
            main_content = self.driver.find_element(By.CSS_SELECTOR, 'div.p-view_contents.p-view_contents--primary')
            aria_label = main_content.get_attribute('aria-label')
            if (aria_label):
                if "Conversation with" in aria_label:
                    return True
                elif "Channel" in aria_label:
                    return False
            return False
        except NoSuchElementException:
            return False

    def is_thread_open(self):
        """
        Determines if a thread is open by checking for the presence of the thread pane.
        """
        try:
            thread_pane = self.driver.find_element(By.CSS_SELECTOR, 'div.p-threads_view')
            thread_pane = driver.find_element(By.CSS_SELECTOR, 'div.p-threads_view')
            if thread_pane.is_displayed():
                return True
            else:
                return False
        except NoSuchElementException:
            return False

    def find_last_message_from_me(self):
        """
        Finds the last message sent by 'me' (pearl) in Slack.
        Returns:
            last_message_from_me_ts_float: The timestamp (as float) of the last message sent by 'me'.
        """
        try:
            # Locate message elements
            messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")

            # Go through messages from newest to oldest
            for message in reversed(messages):
                logger.info(f"Message: {slack_extract_message_text(message)}")
                # Extract sender name
                sender_name = slack_extract_sender_name(message)
                logger.info(f"Sender name: {sender_name}")
                # Check if the sender is 'me'
                if "pearl" in sender_name.lower():
                    # Extract message ID (timestamp)
                    try:
                        timestamp_element = message.find_element(By.CSS_SELECTOR, "a.c-timestamp")
                        message_id = timestamp_element.get_attribute("data-ts")
                        message_ts_float = float(message_id)
                    except (NoSuchElementException, ValueError):
                        message_id = None
                        message_ts_float = None

                    logger.info(f"Found last message from 'me' with ID: {message_id}")
                    return message_ts_float

            # If no message from 'me' is found
            logger.info("No previous message from 'me' found.")
            return None

        except Exception as e:
            logger.exception("Error finding last message from 'me'.")
            return None

    def collect_messages_after(self, last_message_from_me_ts_float):
        """
        Collects messages based on the current context: DM, channel, or thread.
        """
        try:
            # Determine context
            in_dm = is_slack_dm(driver)
            thread_open = is_slack_thread_open(driver)
            messages_list = []

            if thread_open:
                logger.info("Thread is open. Collecting messages in thread up to last message from 'me'.")
                # Find the last message from 'me' in the thread
                last_message_from_me_in_thread_ts_float = slack_find_last_message_from_me_in_thread(driver)

                # Collect messages in the thread
                messages = driver.find_elements(By.CSS_SELECTOR, "div.c-virtual_list__item--thread div.c-message_kit__background")

                # Use the timestamp of the last message from 'me' in the thread
                messages_list = slack_collect_messages_from_elements(messages, None, last_message_from_me_in_thread_ts_float)
            elif in_dm:
                if last_message_from_me_ts_float is None:
                    logger.info("No previous message from 'me' found in DM. Not collecting any messages.")
                    messages_list = []
                else:
                    logger.info("In a DM. Collecting messages sent after last message from 'me'.")
                    # Collect messages in the DM
                    messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
                    messages_list = slack_collect_messages_from_elements(messages, last_message_from_me_ts_float)
            else:
                if last_message_from_me_ts_float is None:
                    logger.info("No previous message from 'me' found in channel. Not collecting any messages.")
                    messages_list = []
                else:
                    logger.info("In a channel. Collecting messages sent after last message from 'me'.")
                    # Collect messages in the channel
                    messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
                    messages_list = slack_collect_messages_from_elements(messages, last_message_from_me_ts_float)

            return messages_list

        except Exception as e:
            logger.exception("Error collecting messages.")
            return []

    def detect_new_messages(self, last_processed_ts_float):
        """
        Detects new messages based on the current context: DM, channel, or thread.
        """
        try:
            # Determine context
            in_dm = is_slack_dm(driver)
            thread_open = is_slack_thread_open(driver)
            new_messages = []

            if thread_open:
                logger.info("Thread is open. Detecting new messages in thread up to last message from 'me'.")
                # Find the last message from 'me' in the thread
                last_message_from_me_in_thread_ts_float = slack_find_last_message_from_me_in_thread(driver)

                # Collect messages in the thread
                messages = driver.find_elements(By.CSS_SELECTOR, "div.c-virtual_list__item--thread div.c-message_kit__background")

                # Use the timestamp of the last message from 'me' in the thread
                new_messages = slack_detect_new_messages_from_elements(messages, last_processed_ts_float, last_message_from_me_in_thread_ts_float)
            elif in_dm:
                if last_processed_ts_float is None:
                    logger.info("No previous message from 'me' found in DM. Not detecting new messages.")
                    new_messages = []
                else:
                    logger.info("In a DM. Detecting new messages.")
                    # Collect messages in the DM
                    messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
                    new_messages = slack_detect_new_messages_from_elements(messages, last_processed_ts_float)
            else:
                if last_processed_ts_float is None:
                    logger.info("No previous message from 'me' found in channel. Not detecting new messages.")
                    new_messages = []
                else:
                    logger.info("In a channel. Detecting new messages.")
                    # Collect messages in the channel
                    messages = driver.find_elements(By.CSS_SELECTOR, "div.c-message_kit__background")
                    new_messages = slack_detect_new_messages_from_elements(messages, last_processed_ts_float)

            return new_messages

        except Exception as e:
            logger.exception("Error detecting new messages.")
            return []

    def notify_chat_changed(self, new_chat_id):
        """
        Emits a 'chatChanged' event to the back-end via WebSocket.
        Args:
            new_chat_id (str): The identifier of the new chat.
        """
        try:
            # Emit the 'chatChanged' event to the backend's '/messaging' namespace
            sio.emit(
                "chatChanged",
                {"new_chat_id": new_chat_id},
                namespace="/messaging",
            )
            logger.info(f"Emitted 'chatChanged' event with new_chat_id: {new_chat_id}")
        except Exception as e:
            logger.exception("Failed to emit 'chatChanged' event.")

    def send_message_via_websocket(self, content, timestamp, hashed_sender_name):
        """
        Sends the new message to the back end via WebSocket.
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


    def get_current_chat_id(self):
        """
        Returns a unique identifier for the current chat, based on the URL.
        """
        try:
            current_url = self.driver.current_url
            parsed_url = urllib.parse.urlparse(current_url)
            channel_id = urllib.parse.parse_qs(parsed_url.query).get('channel', [None])[0]

            if channel_id:
                logger.info(f"Current chat ID: {channel_id}")
                return channel_id
            else:
                # Fallback: Use the path
                path = parsed_url.path
                if path:
                    logger.info(f"Current chat path: {path}")
                    return path
                else:
                    logger.warning("Unable to determine current chat ID.")
                    return None
        except Exception as e:
            logger.exception("Error getting current chat ID.")
            return None