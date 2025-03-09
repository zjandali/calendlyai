import { Stagehand } from "@browserbasehq/stagehand";

// Basic usage
// Defaults to Browserbase; if no API key is provided, it will default to LOCAL
// Default model is gpt-4
const stagehandlocal = new Stagehand({
    modelName: 'gpt-4o-mini',
    //apiKey: process.env.BROWSERBASE_API_KEY,
    env: 'LOCAL',
    
  });

  const stagehand = new Stagehand({
    modelName: 'gpt-4o-mini',
    env: 'BROWSERBASE',
    apiKey: process.env.BROWSERBASE_API_KEY,
    browserbaseSessionCreateParams: {
      projectId: process.env.BROWSERBASE_PROJECT_ID ?? '',
      browserSettings: {
        solveCaptchas: true
      }
    }
  });

// Create an async function to handle the Stagehand operations
async function initStagehand() {
    try {
        // Custom configuration
        await stagehand.init();

        const page = stagehand.page;
        await page.goto("https://calendly.com/robertjandali/30min/2025-03-10T09:30:00-08:00?month=2025-03&date=2025-03-10");
        await page.act({
            action: "enter %name% into the Name field, enter %email% into the Email field, enter %phone% into the Phone Number field and click on the Schedule Event Button",
            variables: {
                name: "John Doe",
                email: "john.doe@example.com",
                phone: "5109198404",
            },
        });

        // await page.act({
        //     action: "click on the Schedule Event Button",
        // });
        await stagehand.close();

    } catch (error) {
        console.error(error);
    }
}

// Execute the async function
initStagehand();




