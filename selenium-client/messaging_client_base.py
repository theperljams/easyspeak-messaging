import logging
import socketio
import os
import time
import urllib.parse
import hmac
import hashlib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

WEBSOCKET_SERVER_URL = os.getenv("WEBSOCKET_SERVER_URL", "http://localhost:3000")
USER_ID = os.getenv("USER_ID", "pearl@easyspeak-aac.com")
POLL_INTERVAL = 5  # Polling interval in seconds
PEPPER = os.getenv("PEPPER", "SuperSecretPepperValue")

# Initialize WebSocket Client
sio = socketio.Client()

def hash_sender_name(sender_name, pepper):
    """Hashes the sender's name using HMAC with SHA-256."""
    return hmac.new(pepper.encode('utf-8'), sender_name.encode('utf-8'), hashlib.sha256).hexdigest()

class MessagingClientBase:
    def __init__(self, driver):
        self.driver = driver
        self.previous_chat_id = None
        self.last_processed_ts_float = 0
        logger.info("Initialized MessagingClientBase")

    def get_current_chat_id(self):
        """Should be implemented by subclasses."""
        raise NotImplementedError

    def is_thread_open(self):
        """Should be implemented by subclasses."""
        return False  # Default behavior (for Instagram)

    def collect_messages_after(self, last_message_from_me_ts_float):
        """Should be implemented by subclasses."""
        raise NotImplementedError

    def detect_new_messages(self, last_processed_ts_float):
        """Should be implemented by subclasses."""
        raise NotImplementedError

    def send_message_via_websocket(self, content, timestamp, sender_name):
        """Sends the new message to the backend via WebSocket."""
        try:
            hashed_sender_name = hash_sender_name(sender_name, PEPPER)
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
            logger.info(f'Sent message via WebSocket: "{content}" at {timestamp}, Sender: {hashed_sender_name}')
        except Exception as e:
            logger.exception("Failed to send message via WebSocket.")

    def notify_chat_changed(self, new_chat_id):
        """Notify backend of chat change."""
        try:
            sio.emit("chatChanged", {"new_chat_id": new_chat_id}, namespace="/messaging")
            logger.info(f"Emitted 'chatChanged' event with new_chat_id: {new_chat_id}")
        except Exception as e:
            logger.exception("Failed to emit 'chatChanged' event.")