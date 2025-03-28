#!/usr/bin/env python3
"""
Integrated Calendly Booking System with Browserbase

This script combines calendar availability matching with Browserbase
for a streamlined booking system.
"""

import logging
import os
from datetime import datetime

# Import components from organized modules
from utils.calendar_utils import generate_mock_calendar, find_matching_times, format_matches
from utils.calendly_api import setup_calendly_api, get_calendly_availability, create_booking_url, get_suggested_time
from browser.browserbase_handler import CalendlyScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calendly_integrated.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def book_calendly_meeting(
    calendly_url: str,
    name: str,
    email: str,
    phone: str,
    additional_info: str = None,
    timezone: str = "America/Los_Angeles"
):
    """
    Main integrated workflow function
    
    Args:
        calendly_url: Calendly URL to book
        name: Name for the booking
        email: Email for the booking
        phone: Phone number for the booking
        additional_info: Additional information for the booking
        timezone: Timezone to use for booking
        
    Returns:
        str: URL of the booked appointment or None if booking failed
    """
    logger.info("Starting integrated Calendly workflow")
    
    try:
        # Get mock calendar data
        logger.info("Generating mock calendar data")
        mock_calendar = generate_mock_calendar()
        
        # Set up Calendly API and get availability
        uuid = setup_calendly_api(calendly_url)
        calendly_data = get_calendly_availability(uuid, timezone)
        
        # Find matching times
        matches = find_matching_times(mock_calendar, calendly_data)
        formatted_matches = format_matches(matches)
        
        # Get suggested time from LLM
        suggested_time = get_suggested_time(formatted_matches)
        logger.info(f"Suggested time: {suggested_time}")
        
        # Create final booking URL
        final_url = create_booking_url(calendly_url, suggested_time)
        
        # Create CalendlyScraper instance for form filling and submission
        logger.info("Creating CalendlyScraper instance with Browserbase")
        scraper = CalendlyScraper()
        
        # Initialize browser
        logger.info("Initializing Browserbase browser")
        if not scraper.initialize_browser():
            logger.error("Failed to initialize Browserbase browser")
            return None
        
        try:
            # Navigate to the booking URL
            logger.info(f"Navigating to booking URL: {final_url}")
            scraper.navigate_to_url(final_url)
            
            # Fill in the form
            logger.info("Filling out booking form")
            scraper.fill_name(name)
            scraper.fill_email(email)
            scraper.fill_phone(phone)
            
            if additional_info:
                scraper.fill_additional_info(additional_info)
            
            # Submit the form
            logger.info("Submitting booking form")
            success = scraper.submit_form()
            
            if success:
                logger.info("Booking successful")
                return final_url
            else:
                logger.error("Booking failed")
                return None
                
        finally:
            # Close the browser regardless of success or failure
            logger.info("Closing browser")
            scraper.close_browser()
        
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def main():
    """
    Main function to run the integrated Calendly booking workflow
    """
    # Example usage
    calendly_url = "https://calendly.com/robertjandali/30min"
    name = "John Doe"
    email = "john@doe.com"
    phone = "5109198404"
    additional_info = "This is a test booking"
    
    result = book_calendly_meeting(
        calendly_url=calendly_url,
        name=name,
        email=email,
        phone=phone,
        additional_info=additional_info
    )
    
    if result:
        print(f"Booking successful! URL: {result}")
    else:
        print("Booking failed.")

if __name__ == "__main__":
    main() 