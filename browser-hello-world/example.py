import os
import sys
from pathlib import Path

from browser_use.agent.views import ActionResult

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import logging

from langchain_openai import ChatOpenAI

from browser_use import Agent, Controller
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext

logger = logging.getLogger(__name__)

# Initialize controller first
browser = Browser(
    config=BrowserConfig(
        headless=False,
        cdp_url="http://localhost:9222"
    )
)
controller = Controller()


@controller.action(
    'Start a new Slack DM with a user',
)
async def start_slack_dm(user_name: str, browser: BrowserContext):
    """Starts a new direct message with a specified user in Slack."""
    print("Starting DM with", user_name)
    try:
        # 1. Click the "New Message" button
        new_message_button_selector = 'button[data-qa="composer_button"]'
        await browser.click_element(selector=new_message_button_selector)
        logger.info("Clicked 'New Message' button.")

        # 2. Type the user's name into the "To" field
        to_field_selector = 'div[data-qa="composer_page__destination-input"]'
        await browser.type_into_element(selector=to_field_selector, text=user_name)
        logger.info(f"Typed user name '{user_name}' into 'To' field.")

        # 3. Press Enter to submit the name
        await browser.press_key(selector=to_field_selector, key="Enter")
        logger.info("Pressed Enter to submit the name.")

        return ActionResult(extracted_content=f"Started DM with {user_name}", include_in_memory=True)

    except Exception as e:
        msg = f"Failed to start DM with {user_name}: {str(e)}"
        logger.exception(msg)
        return ActionResult(error=msg)


# @controller.action('Send a message to the current Slack conversation')
# async def send_slack_message(message_text: str, browser: BrowserContext):
#     """Sends a message to the currently open Slack conversation."""
#     try:
#         # 1. Locate the message input field (adjust selector as needed)
#         message_input_selector = 'div[data-qa="message_input"] div.ql-editor'
#         await browser.type_into_element(selector=message_input_selector, text=message_text)
#         logger.info(f"Typed message: '{message_text}' into input field.")

#         # 2. Press Enter to send the message
#         await browser.press_key(selector=message_input_selector, key="Enter")
#         logger.info("Pressed Enter to send message.")

#         return ActionResult(extracted_content="Message sent successfully.", include_in_memory=True)

#     except Exception as e:
#         msg = f"Failed to send message: {str(e)}"
#         logger.exception(msg)
#         return ActionResult(error=msg)


async def main():
    task = "Start a new Slack DM with recipient_name and send them a message saying 'Hello!'"

    sensitive_data = {"recipient_name": "Trisha"}

    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(
        task=task,
        llm=model,
        controller=controller,
        browser=browser,
        sensitive_data=sensitive_data,
    )

    await agent.run()

    await browser.close()

    input('Press Enter to close...')


if __name__ == '__main__':
    asyncio.run(main())