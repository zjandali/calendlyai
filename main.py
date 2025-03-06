import os
import sys
import asyncio
import nest_asyncio
from config.settings import settings
from workflow.workflows import run_multiple_workflows
# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()


async def main(calendly_url=None, contact_name=None, contact_email=None, 
               contact_phone=None, num_runs=None, max_retries=None):
    """
    Main function to run the workflow
    
    Args:
        calendly_url (str, optional): Calendly URL to book (overrides settings)
        contact_name (str, optional): Name to use for booking (overrides hardcoded value)
        contact_email (str, optional): Email to use for booking (overrides hardcoded value)
        contact_phone (str, optional): Phone number to use for booking (overrides hardcoded value)
        num_runs (int, optional): Number of booking attempts (overrides settings)
        max_retries (int, optional): Maximum retries for browser errors (overrides settings)
    """
    # Get API keys from environment variables or settings
    anchor_api_key = settings.anchor_api_key or os.getenv("ANCHOR_API_KEY")
    openai_api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    
    if not anchor_api_key or not openai_api_key:
        print("Error: Missing required API keys. Please set ANCHOR_API_KEY and OPENAI_API_KEY environment variables.")
        return
    
    # Use provided values or fallback to settings/defaults
    calendly_url = calendly_url or settings.default_calendly_url
    num_runs = num_runs or settings.default_num_runs  # Default to 5 runs, can be changed via command line args
    max_retries = max_retries or settings.default_max_retries  # Default to 3 retries for Anchor Browser errors
    
    # Override with command line arguments if provided (legacy support)
    if len(sys.argv) > 1 and num_runs is None:
        try:
            num_runs = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number of runs: {sys.argv[1]}. Using default: {settings.default_num_runs}")
    
    if len(sys.argv) > 2 and max_retries is None:
        try:
            max_retries = int(sys.argv[2])
        except ValueError:
            print(f"Invalid number of retries: {sys.argv[2]}. Using default: {settings.default_max_retries}")
    
    # Create contact details dictionary
    contact_details = {
        "name": contact_name,
        "email": contact_email,
        "phone": contact_phone
    }
    
    # Run the evaluation
    summary = await run_multiple_workflows(
        calendly_url, 
        anchor_api_key, 
        openai_api_key, 
        num_runs, 
        max_retries,
        contact_details
    )
    print(f"Evaluation complete! Success rate: {summary['this_run']['success_rate']}%")
    print(f"Successful runs: {summary['this_run']['successful_runs']}/{summary['this_run']['total_runs']}")


if __name__ == "__main__":
    asyncio.run(main()) 