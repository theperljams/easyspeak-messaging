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
        chrome_instance_path=CHROME_EXECUTABLE_PATH,
        extra_chromium_args=[
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "--disable-blink-features=AutomationControlled"  # Helps avoid detection
        ],
        headless=False  # Ensure it's running in a visible mode
    )
)


# Initialize the model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-preview-02-05", temperature=0.0)

# Define sensitive data
sensitive_data = {'google_name': 'email', 'google_password': 'password'}

# Use the placeholder names in your task description
task = '''go to https://slack.com/signin#/signin. Choose "Sign In with Google" login with google_name and google_password. 
Wait for the user to do the MFA on their end. Once login has succeeded, open the JustBuild worksapce (you may have to click on "show more workspaces). 
Press "Cancel" on the popup and choose "Use slack in the browser. Find the #saturdays-at-byu channel and send a message saying: "Guys look what I did with browser-use! 
(It logged in, found this channel, and sent this message all on its own!) It has a feature that allows you to pass sensitive data to the agent without the model ever seeing it."'''

# Pass the sensitive data to the agent
agent = Agent(task=task, llm=llm, sensitive_data=sensitive_data)

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