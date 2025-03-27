import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    with sync_playwright() as p:
        # Connect to browser using Playwright
        browser = p.chromium.connect_over_cdp(
            f"wss://connect.hyperbrowser.ai?apiKey={os.getenv('HYPERBROWSER_API_KEY')}"
        )

        # Get the default context and page
        default_context = browser.contexts[0]
        page = default_context.pages[0]

        # Navigate to various websites
        print("Navigating to Hacker News...")
        page.goto("https://news.ycombinator.com/")
        page_title = page.title()
        print("Page 1:", page_title)
        page.evaluate("() => { console.log('Page 1:', document.title); }")

        page.goto("https://example.com")
        print("Page 2:", page.title())
        page.evaluate("() => { console.log('Page 2:', document.title); }")

        page.goto("https://apple.com")
        print("Page 3:", page.title())
        page.evaluate("() => { console.log('Page 3:', document.title); }")

        page.goto("https://google.com")
        print("Page 4:", page.title())
        page.evaluate("() => { console.log('Page 4:', document.title); }")

        # Clean up
        default_context.close()
        browser.close()

if __name__ == "__main__":
    main()