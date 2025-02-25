import signal
import asyncio
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Browser, BrowserConfig

load_dotenv()

CHROME_EXECUTABLE_PATH = "/usr/bin/google-chrome"  # Confirmed path

browser = Browser(
    config=BrowserConfig(
        cdp_url="http://localhost:9222",
        headless=False
    )
)

# Initialize the model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-preview-02-05", temperature=0.0)

# Define sensitive data
sensitive_data = {'google_name': 'email', 'google_password': 'password'}

# Use the placeholder names in your task description
# task = '''Go to the slack tab that is already open and logged in. Find the #saturdays-at-byu channel and send a message saying: "Guys look what I did with browser use!
# I had to log in manually from a debug window but it was able to find the channel and send this message." '''

task = '''Go to the instagram tab that is already open and logged in. Find Ananya Kumaresh in my dms.
If you can't find their name, bring up their chat by starting a new dm with them. DO NOT send a message 
to anyone who is not Ananya Kumaresh. You should check and make sure it says their name at the top of the page.
Then respond to their message as best you can.
If you aren't sure, just come up with something that seems about right.'''

# Pass the sensitive data to the agent
agent = Agent(task=task, llm=llm, browser=browser)

# Global flag to signal shutdown
shutdown_flag = False

def signal_handler(sig, frame):
    """Handles interrupt signals (e.g., Ctrl+C)."""
    global shutdown_flag
    print("Received interrupt signal. Shutting down...")
    shutdown_flag = True
    # You might want to add more cleanup here, like closing the browser
    # if it's safe to do so at this point.

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)

async def main():
    try:
        await agent.run()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Closing the browser...")
        await browser.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This handles the asyncio.run's own KeyboardInterrupt
        print("Asyncio run interrupted.")
    finally:
        print("Exiting.")