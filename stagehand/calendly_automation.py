from solutions.stagehand import Stagehand
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def init_stagehand():
    try:
        # Initialize Stagehand with configuration
        stagehand = Stagehand(
            model_name='gpt-4-mini',
            env='BROWSERBASE',
            api_key=os.getenv('BROWSERBASE_API_KEY'),
            browserbase_session_create_params={
                'project_id': os.getenv('BROWSERBASE_PROJECT_ID'),
                'browser_settings': {
                    'solve_captchas': True
                }
            }
        )

        # Initialize the browser
        await stagehand.init()

        # Get the page object
        page = stagehand.page

        # Navigate to the Calendly page
        await page.goto("https://calendly.com/robertjandali/30min/2025-03-10T09:30:00-08:00?month=2025-03&date=2025-03-10")

        # Fill out the form using act
        await page.act({
            'action': "enter %name% into the Name field, enter %email% into the Email field, enter %phone% into the Phone Number field and click on the Schedule Event Button",
            'variables': {
                'name': "John Doe",
                'email': "john.doe@example.com",
                'phone': "+15109198404",
            }
        })

        # Close the browser
        await stagehand.close()

    except Exception as error:
        print(f"Error occurred: {error}")

if __name__ == "__main__":
    # Run the async function
    asyncio.run(init_stagehand()) 