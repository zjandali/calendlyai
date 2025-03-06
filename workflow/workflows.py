import os
import json
from datetime import datetime
from tools.calendly_api import book_calendly_meeting


async def run_multiple_workflows(calendly_url, anchor_api_key, openai_api_key, 
                                 num_runs=5, max_retries=3, contact_details=None):
    """
    Run the workflow multiple times and evaluate success rate
    
    Args:
        calendly_url (str): Calendly URL to book
        anchor_api_key (str): API key for Anchor Browser
        openai_api_key (str): API key for OpenAI
        num_runs (int): Number of times to run the workflow
        max_retries (int): Maximum number of retries for Anchor Browser errors
        contact_details (dict, optional): Contact information for booking
            {
                "name": str,
                "email": str,
                "phone": str
            }
        
    Returns:
        dict: Summary of the evaluation
    """
    # Create eval directory if it doesn't exist
    os.makedirs("eval", exist_ok=True)
    
    # Get today's date for file naming
    today_date = datetime.now().strftime('%Y%m%d')
    results_file = f"eval/workflow_results_{today_date}.json"
    
    # Load existing results if the file exists
    existing_results = []
    if os.path.exists(results_file):
        try:
            with open(results_file, "r") as f:
                existing_results = json.load(f)
            print(f"Loaded {len(existing_results)} existing results from {results_file}")
        except json.JSONDecodeError:
            print(f"Error loading existing results from {results_file}, starting fresh")
    
    # Start with existing results
    results = existing_results.copy()
    
    # Track new results for this run
    new_results = []
    
    for i in range(num_runs):
        print(f"Running workflow {i+1}/{num_runs}...")
        result = await book_calendly_meeting(
            calendly_url, 
            anchor_api_key, 
            openai_api_key, 
            max_retries,
            contact_details
        )
        results.append(result)
        new_results.append(result)
        
        # Print the time booked in PST
        if result.get("success", False):
            print(f"Successfully booked: {result.get('suggested_time_pst', 'Time not available')}")
        else:
            print(f"Booking failed: {result.get('error', 'Unknown error')}")
        
        # Save results after each run
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
    
    # Calculate success rate for this run
    new_successes = sum(1 for r in new_results if r.get("success", False))
    new_success_rate = (new_successes / num_runs) * 100 if num_runs > 0 else 0
    
    # Calculate overall success rate
    total_successes = sum(1 for r in results if r.get("success", False))
    total_success_rate = (total_successes / len(results)) * 100 if results else 0
    
    summary = {
        "run_timestamp": datetime.now().isoformat(),
        "this_run": {
            "total_runs": num_runs,
            "successful_runs": new_successes,
            "success_rate": new_success_rate
        },
        "overall": {
            "total_runs": len(results),
            "successful_runs": total_successes,
            "success_rate": total_success_rate
        }
    }
    
    # Save summary
    with open(f"eval/summary_{today_date}.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    return summary 