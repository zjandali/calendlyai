#!/usr/bin/env python3
"""
Test Suite for Calendly Workflow

This script provides a comprehensive test suite for the Calendly booking workflow,
allowing multiple test runs and measuring success based on successful bookings.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

# Add the parent directory to the Python path to find the book2 module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now import the modules
try:
    from book2 import main as calendly_workflow
    from book2 import setup_calendly_api, get_calendly_availability, get_suggested_time, create_booking_url, book_calendly_appointment
    from utils.calendar_utils import generate_mock_calendar, convert_to_unified_format, find_overlapping_times
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
        logging.FileHandler('calendly_test_suite.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class CalendlyTestSuite:
    """Test suite for Calendly workflow"""
    
    def __init__(
        self,
        calendly_url: str,
        test_runs: int = 1,
        test_data: Optional[List[Dict[str, Any]]] = None,
        debug: bool = False
    ):
        """
        Initialize the test suite.
        
        Args:
            calendly_url: The Calendly URL to test
            test_runs: Number of test runs to perform
            test_data: Optional list of test data dictionaries
            debug: Enable debug logging
        """
        self.calendly_url = calendly_url
        self.test_runs = test_runs
        self.test_data = test_data or self._generate_test_data(test_runs)
        self.debug = debug
        
        # Always run in visible mode
        self.headless = False
            
        if debug:
            logger.setLevel(logging.DEBUG)
            
        self.results = {
            "total_runs": test_runs,
            "successful_runs": 0,
            "failed_runs": 0,
            "run_details": []
        }
        
        # Validate the Calendly URL
        try:
            setup_calendly_api(calendly_url)
            logger.info(f"Validated Calendly URL: {calendly_url}")
        except Exception as e:
            logger.error(f"Invalid Calendly URL: {calendly_url}")
            logger.error(f"Error: {str(e)}")
            raise ValueError(f"Invalid Calendly URL: {calendly_url}")
    
    def _generate_test_data(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate test data for the specified number of runs.
        
        Args:
            count: Number of test data entries to generate
            
        Returns:
            List of test data dictionaries
        """
        logger.info(f"Generating test data for {count} runs")
        
        test_data = []
        
        # List of realistic test names
        first_names = ["John", "Jane", "Michael", "Emily", "David", "Sarah", "Robert", "Lisa"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia"]
        
        # Generate unique email domains
        email_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "example.com"]
        
        for i in range(count):
            # Generate a unique name and email for each test
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            name = f"{first_name} {last_name}"
            
            # Create a unique email with timestamp to avoid duplicates
            timestamp = int(time.time()) + i
            email_domain = random.choice(email_domains)
            email = f"{first_name.lower()}.{last_name.lower()}.{timestamp}@{email_domain}"
            
            # Generate a realistic US phone number
            area_code = random.randint(200, 999)
            prefix = random.randint(200, 999)
            line_number = random.randint(1000, 9999)
            phone = f"{area_code}{prefix}{line_number}"
            
            # Generate some additional info
            additional_info = f"Test booking {i+1} created by automated test suite"
            
            test_data.append({
                "name": name,
                "email": email,
                "phone": phone,
                "additional_info": additional_info
            })
        
        logger.debug(f"Generated test data: {test_data}")
        return test_data
    
    def run_tests(self) -> Dict[str, Any]:
        """
        Run the test suite.
        
        Returns:
            Dictionary with test results
        """
        logger.info(f"Starting test suite with {self.test_runs} runs")
        
        for i in range(self.test_runs):
            run_number = i + 1
            logger.info(f"Starting test run {run_number}/{self.test_runs}")
            
            test_data = self.test_data[i]
            start_time = datetime.now()
            
            run_result = {
                "run_number": run_number,
                "test_data": test_data,
                "start_time": start_time.isoformat(),
                "success": False,
                "booking_url": None,
                "error": None
            }
            
            try:
                # Patch the main function to use our test data
                def patched_main():
                    try:
                        # Get mock calendar data
                        logger.info("Generating mock calendar data for test")
                        mock_calendar = generate_mock_calendar()
                        
                        # Set up Calendly API and get availability
                        uuid, profile_slug, event_type_slug = setup_calendly_api(self.calendly_url)
                        calendly_formatted = get_calendly_availability(uuid)
                        
                        # Convert calendars to unified format
                        calendly_timezone = calendly_formatted.get("timezone", "America/Los_Angeles")
                        unified_mock = convert_to_unified_format(mock_calendar, 'mock', calendly_timezone)
                        unified_calendly = convert_to_unified_format(calendly_formatted, 'calendly')
                        
                        # Find overlapping times
                        overlapping_calendar = find_overlapping_times(unified_mock, unified_calendly)
                        
                        # Get suggested time from LLM
                        suggested_time = get_suggested_time(overlapping_calendar)
                        
                        # Create final booking URL
                        final_url = create_booking_url(self.calendly_url, suggested_time)
                        
                        # Book the appointment
                        logger.info(f"Booking Calendly appointment at URL: {final_url}")
                        booking_success = book_calendly_appointment(
                            url=final_url,
                            name=test_data["name"],
                            email=test_data["email"],
                            phone=test_data["phone"],
                            additional_info=test_data["additional_info"],
                            debug=self.debug,
                            headless=self.headless  # Always False for visible mode
                        )
                        
                        if booking_success:
                            logger.info("Calendly appointment booked successfully")
                        else:
                            logger.error("Failed to book Calendly appointment")
                        
                        return final_url, booking_success
                    except Exception as e:
                        logger.error(f"Error in patched_main: {str(e)}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                
                # Run the patched main function
                booking_url, success = patched_main()
                
                run_result["success"] = success
                run_result["booking_url"] = booking_url
                
                if success:
                    self.results["successful_runs"] += 1
                    logger.info(f"Test run {run_number} succeeded")
                else:
                    self.results["failed_runs"] += 1
                    logger.error(f"Test run {run_number} failed")
                
            except Exception as e:
                self.results["failed_runs"] += 1
                error_message = f"Error in test run {run_number}: {str(e)}"
                run_result["error"] = error_message
                logger.error(error_message)
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            end_time = datetime.now()
            run_result["end_time"] = end_time.isoformat()
            run_result["duration_seconds"] = (end_time - start_time).total_seconds()
            
            self.results["run_details"].append(run_result)
            
            # Save results after each run
            self._save_results()
            
            # No delay between runs
        
        logger.info("Test suite completed")
        logger.info(f"Results: {self.results['successful_runs']} successful, {self.results['failed_runs']} failed")
        
        return self.results
    
    def _save_results(self) -> None:
        """Save test results to a JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"calendly_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Test results saved to {filename}")

def main():
    """Main function to run the test suite"""
    parser = argparse.ArgumentParser(description="Calendly Workflow Test Suite")
    
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Calendly URL to test"
    )
    
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of test runs to perform (default: 1)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--test-data",
        type=str,
        help="Path to JSON file with test data"
    )
    
    args = parser.parse_args()
    
    # Load test data if provided
    test_data = None
    if args.test_data:
        try:
            with open(args.test_data, 'r') as f:
                test_data = json.load(f)
            logger.info(f"Loaded test data from {args.test_data}")
        except Exception as e:
            logger.error(f"Error loading test data: {str(e)}")
            sys.exit(1)
    
    # Initialize and run the test suite
    test_suite = CalendlyTestSuite(
        calendly_url=args.url,
        test_runs=args.runs,
        test_data=test_data,
        debug=args.debug
    )
    
    results = test_suite.run_tests()
    
    # Print summary
    print("\nTest Suite Summary:")
    print(f"Total runs: {results['total_runs']}")
    print(f"Successful runs: {results['successful_runs']}")
    print(f"Failed runs: {results['failed_runs']}")
    print(f"Success rate: {(results['successful_runs'] / results['total_runs']) * 100:.2f}%")
    
    # Return success if all tests passed
    return 0 if results['failed_runs'] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())