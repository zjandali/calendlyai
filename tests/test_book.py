#!/usr/bin/env python3
"""
Test Runner for Calendly Workflow

This script runs the book2.py script a specified number of times and tracks the results.
"""

import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Dict, Any

# Add the parent directory to the Python path to find the book2 module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now import the modules
try:
    from book2 import main as calendly_workflow
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this script from the correct directory")
    print("Current directory:", os.getcwd())
    print("Available files:", os.listdir('.'))
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calendly_test_runner.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def run_tests(runs: int, debug: bool = False) -> Dict[str, Any]:
    """
    Run the book2.py script multiple times.
    
    Args:
        runs: Number of times to run the script
        debug: Enable debug logging
        
    Returns:
        Dictionary with test results
    """
    if debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Starting test runner with {runs} runs")
    
    results = {
        "total_runs": runs,
        "successful_runs": 0,
        "failed_runs": 0,
        "run_details": []
    }
    
    for i in range(runs):
        run_number = i + 1
        logger.info(f"Starting run {run_number}/{runs}")
        
        start_time = datetime.now()
        
        run_result = {
            "run_number": run_number,
            "start_time": start_time.isoformat(),
            "success": False,
            "booking_url": None,
            "error": None
        }
        
        try:
            # Run the main function from book2.py
            booking_url = calendly_workflow()
            
            run_result["success"] = True
            run_result["booking_url"] = booking_url
            
            results["successful_runs"] += 1
            logger.info(f"Run {run_number} succeeded")
            
        except Exception as e:
            results["failed_runs"] += 1
            error_message = f"Error in run {run_number}: {str(e)}"
            run_result["error"] = error_message
            logger.error(error_message)
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        end_time = datetime.now()
        run_result["end_time"] = end_time.isoformat()
        run_result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        results["run_details"].append(run_result)
        
        # Save results after each run
        save_results(results)
    
    logger.info("Test runner completed")
    logger.info(f"Results: {results['successful_runs']} successful, {results['failed_runs']} failed")
    
    return results

def save_results(results: Dict[str, Any]) -> None:
    """Save test results to a JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Ensure the results directory exists
    os.makedirs("results", exist_ok=True)
    
    filename = f"results/calendly_test_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test results saved to {filename}")

def main():
    """Main function to run the test runner"""
    parser = argparse.ArgumentParser(description="Calendly Workflow Test Runner")
    
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs to perform (default: 1)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Run the tests
    results = run_tests(
        runs=args.runs,
        debug=args.debug
    )
    
    # Print summary
    print("\nTest Runner Summary:")
    print(f"Total runs: {results['total_runs']}")
    print(f"Successful runs: {results['successful_runs']}")
    print(f"Failed runs: {results['failed_runs']}")
    print(f"Success rate: {(results['successful_runs'] / results['total_runs']) * 100:.2f}%")
    
    # Return success if all tests passed
    return 0 if results['failed_runs'] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())