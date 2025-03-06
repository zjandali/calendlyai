import os
import json
import time
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
    summary_file = "eval/summary.json"
    
    # Load existing results if the file exists
    existing_results = []
    if os.path.exists(results_file):
        try:
            with open(results_file, "r") as f:
                existing_results = json.load(f)
            print(f"Loaded {len(existing_results)} existing results from {results_file}")
        except json.JSONDecodeError:
            print(f"Error loading existing results from {results_file}, starting fresh")
    
    # Load existing summary if available
    all_runs = []
    if os.path.exists(summary_file):
        try:
            with open(summary_file, "r") as f:
                all_runs = json.load(f)
                if not isinstance(all_runs, list):
                    # Handle case where the summary file has old format
                    all_runs = []
            print(f"Loaded {len(all_runs)} existing runs from summary.json")
        except (json.JSONDecodeError, FileNotFoundError):
            print("Starting fresh summary.json file")
    
    # Start with existing results
    results = existing_results.copy()
    
    # Track new results for this run
    new_results = []
    
    # Track execution times for each run
    execution_times = []
    
    for i in range(num_runs):
        print(f"Running workflow {i+1}/{num_runs}...")
        
        # Start timer for this run
        start_time = time.time()
        
        result = await book_calendly_meeting(
            calendly_url, 
            anchor_api_key, 
            openai_api_key, 
            max_retries,
            contact_details
        )
        
        # End timer and calculate execution time
        end_time = time.time()
        execution_time = end_time - start_time
        execution_times.append(execution_time)
        
        # Add execution time to the result
        result["execution_time_seconds"] = execution_time
        
        results.append(result)
        new_results.append(result)
        
        # Print the time booked in PST and execution time
        if result.get("success", False):
            print(f"Successfully booked: {result.get('suggested_time_pst', 'Time not available')} (took {execution_time:.2f} seconds)")
        else:
            print(f"Booking failed: {result.get('error', 'Unknown error')} (took {execution_time:.2f} seconds)")
        
        # Save results after each run
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
    
    # Calculate success rate for this run
    new_successes = sum(1 for r in new_results if r.get("success", False))
    new_success_rate = (new_successes / num_runs) * 100 if num_runs > 0 else 0
    
    # Calculate overall success rate
    total_successes = sum(1 for r in results if r.get("success", False))
    total_success_rate = (total_successes / len(results)) * 100 if results else 0
    
    # Calculate average execution time for this run
    avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
    total_execution_time = sum(execution_times)
    
    run_summary = {
        "run_timestamp": datetime.now().isoformat(),
        "this_run": {
            "total_runs": num_runs,
            "successful_runs": new_successes,
            "success_rate": new_success_rate,
            "execution_times": {
                "per_run_seconds": execution_times,
                "average_seconds": avg_execution_time,
                "total_seconds": total_execution_time
            }
        },
        "overall": {
            "total_runs": len(results),
            "successful_runs": total_successes,
            "success_rate": total_success_rate
        }
    }
    
    # Add this run to the list of all runs
    all_runs.append(run_summary)
    
    # Save cumulative summary
    with open(summary_file, "w") as f:
        json.dump(all_runs, f, indent=2)
    
    # Save daily summary (for backward compatibility)
    with open(f"eval/summary_{today_date}.json", "w") as f:
        json.dump(run_summary, f, indent=2)
    
    return run_summary 