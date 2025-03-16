import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from pprint import pformat

import pytz
import requests
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
# Add imports for reCAPTCHA solving
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_recaptcha_solver import RecaptchaSolver

from prompts.scheduling_prompts import scheduling_prompt
from utils.calendar_utils import (
    generate_mock_calendar,
    format_calendar_data,
    convert_to_unified_format,
    find_overlapping_times
)
# Import the booking function from scrape.py
from scrape import book_calendly_appointment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calendly_workflow.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def setup_calendly_api(calendly_url: str) -> tuple:
    """
    Set up the Calendly API connection and get event type UUID
    """
    #logger.info(f"Setting up Calendly API for URL: {calendly_url}")
    
    try:
        url_parts = calendly_url.split('/')
        profile_slug = url_parts[-2]
        event_type_slug = url_parts[-1].split('?')[0]
        
        id_url = f"https://calendly.com/api/booking/event_types/lookup?event_type_slug={event_type_slug}&profile_slug={profile_slug}"
        
        #logger.debug(f"Making request to: {id_url}")
        response = requests.get(id_url)
        response.raise_for_status()
        
        event_data = response.json()
        uuid = event_data.get("uuid")
        
        if not uuid:
            raise ValueError("UUID not found in response")
            
        #logger.info(f"Successfully retrieved UUID: {uuid}")
        return uuid, profile_slug, event_type_slug
        
    except Exception as e:
        logger.error(f"Error setting up Calendly API: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def find_matching_times(calendar1, calendar2):
    """
    Find matching available time slots between two calendars with Calendly-like structure.
    
    Args:
        calendar1 (dict): First calendar data in Calendly format
        calendar2 (dict): Second calendar data in Calendly format
        
    Returns:
        list: List of matching datetime objects that are available in both calendars
    """
    # Extract timezones (use the first calendar's timezone if second doesn't specify)
    tz1 = pytz.timezone(calendar1.get('availability_timezone', 'UTC'))
    tz2 = pytz.timezone(calendar2.get('availability_timezone', tz1.zone))
    
    # Create sets of available times from both calendars
    times1 = set()
    times2 = set()
    
    # Helper function to extract times from a calendar
    def extract_times(calendar, time_set):
        for day in calendar.get('days', []):
            if day['status'] == 'available' and day.get('enabled', True):
                for spot in day.get('spots', []):
                    if spot['status'] == 'available' and spot.get('invitees_remaining', 0) > 0:
                        # Parse the ISO format time string
                        time = datetime.fromisoformat(spot['start_time'])
                        time_set.add(time)
    
    # Extract times from both calendars
    extract_times(calendar1, times1)
    extract_times(calendar2, times2)
    
    # Find intersection of available times
    matching_times = sorted(times1.intersection(times2))
    
    return matching_times

def format_matches(matching_times):
    """
    Format matching times in a readable way.
    
    Args:
        matching_times (list): List of datetime objects
        
    Returns:
        list: List of formatted time strings
    """
    return [time.strftime("%Y-%m-%d %H:%M %Z") for time in matching_times]

def get_calendly_availability(uuid: str, timezone: str = "America/Los_Angeles") -> dict:
    """
    Get availability data from Calendly
    """
    try:
        range_url = f"https://calendly.com/api/booking/event_types/{uuid}/calendar/range"
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)
        
        params = {
            "timezone": timezone,
            "diagnostics": "false",
            "range_start": start_date.strftime("%Y-%m-%d"),
            "range_end": end_date.strftime("%Y-%m-%d")
        }
        
        calendar_response = requests.get(range_url, params=params)
        calendar_response.raise_for_status()
        
        return calendar_response.json()
        
    except Exception as e:
        logger.error(f"Error getting Calendly availability: {str(e)}")
        raise

def get_suggested_time(overlapping_calendar: dict) -> str:
    """
    Get suggested meeting time from LLM
    """
    try:
        response_schema = ResponseSchema(
            name="suggested_time",
            description="The suggested meeting time in ISO 8601 format with UTC timezone",
            type="string"
        )
        
        parser = StructuredOutputParser.from_response_schemas([response_schema])
        format_instructions = parser.get_format_instructions()
        
        # Make sure the prompt explicitly requests UTC time
        prompt_template = scheduling_prompt()
        messages = prompt_template.format_messages(
            overlapping_availability=json.dumps(overlapping_calendar, indent=2),
            format_instructions=format_instructions
        )
        
        llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        response = llm.invoke(messages)
        parsed_response = parser.parse(response.content)
        suggested_time = parsed_response['suggested_time']
        
        # Ensure the suggested time is in UTC format with 'Z' suffix
        # If it doesn't already have a timezone indicator
        if 'Z' not in suggested_time and '+' not in suggested_time and '-' not in suggested_time:
            suggested_time = f"{suggested_time}Z"
        
        return suggested_time
    except Exception as e:
        raise

def create_booking_url(calendly_url: str, suggested_time: str) -> str:
    """
    Create the final booking URL
    """
    #logger.info("Creating booking URL")
    
    try:
        base_path = '/'.join(calendly_url.split('?')[0].split('/')[:-1]) if calendly_url.endswith('/') else '/'.join(calendly_url.split('?')[0].split('/'))
        final_url = f"{base_path}/{suggested_time}"
        
        #logger.info(f"Created booking URL: {final_url}")
        return final_url
        
    except Exception as e:
        logger.error(f"Error creating booking URL: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def setup_selenium_with_recaptcha_solver():
    """
    Set up Selenium WebDriver with reCAPTCHA solver
    """
    #logger.info("Setting up Selenium with reCAPTCHA solver")
    
    try:
        test_ua = 'Mozilla/5.0 (Windows NT 4.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36'
        
        options = Options()
        options.add_argument("--headless")  # Remove for visible browser
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f'--user-agent={test_ua}')
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")
        
        driver = webdriver.Chrome(options=options)
        solver = RecaptchaSolver(driver=driver)
        
        #logger.info("Selenium and reCAPTCHA solver setup complete")
        return driver, solver
        
    except Exception as e:
        logger.error(f"Error setting up Selenium with reCAPTCHA solver: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def solve_recaptcha(driver, solver, url):
    """
    Navigate to URL and solve reCAPTCHA if present
    """
    #logger.info(f"Navigating to {url} to solve reCAPTCHA")
    
    try:
        driver.get(url)
        
        # Check if reCAPTCHA is present
        recaptcha_iframes = driver.find_elements(By.XPATH, '//iframe[@title="reCAPTCHA"]')
        
        if recaptcha_iframes:
            logger.info("reCAPTCHA detected, closing browser to retry")
            return False
        else:
            logger.info("No reCAPTCHA detected on the page")
            
        return True
        
    except Exception as e:
        logger.error(f"Error checking for reCAPTCHA: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """
    Main workflow function
    """
    logger.info("Starting Calendly workflow")
    
    try:
        # Example inputs
        calendly_url = "https://calendly.com/robertjandali/30min"
        name = "John Doe"
        email = "john@doe.com"
        phone = "5109198404"
        additional_info = "This is a test booking"
        
        # Get mock calendar data
        logger.info("Generating mock calendar data")
        mock_calendar = generate_mock_calendar()
        
        # Set up Calendly API and get availability
        uuid, profile_slug, event_type_slug = setup_calendly_api(calendly_url)
        calendly_data = get_calendly_availability(uuid)
        
        # Find matching times
        matches = find_matching_times(mock_calendar, calendly_data)
        formatted_matches = format_matches(matches)
        
        # Get suggested time from LLM
        suggested_time = get_suggested_time(formatted_matches)
        logger.info(f"Suggested time: {suggested_time}")
        # Create final booking URL
        final_url = create_booking_url(calendly_url, suggested_time)
        
        # Set up Selenium with reCAPTCHA solver and check for reCAPTCHA
        driver, solver = setup_selenium_with_recaptcha_solver()
        recaptcha_check = solve_recaptcha(driver, solver, final_url)
        
        if not recaptcha_check:
            logger.warning("reCAPTCHA detected, closing browser and retrying with direct booking")
            driver.quit()
            
            # Book the appointment using the imported function from scrape.py
            logger.info(f"Booking Calendly appointment at URL: {final_url}")
            booking_success = book_calendly_appointment(
                url=final_url,
                name=name,
                email=email,
                phone=phone,
                additional_info=additional_info,
                debug=True,  # Enable debug logging
                headless=False  # Use headless mode since you were using it before
            )
        else:
            # No reCAPTCHA detected, proceed with current browser session
            logger.info("No reCAPTCHA detected, proceeding with current browser session")
            driver.quit()  # Close the browser we used for checking
            
            # Book the appointment using the imported function from scrape.py
            logger.info(f"Booking Calendly appointment at URL: {final_url}")
            booking_success = book_calendly_appointment(
                url=final_url,
                name=name,
                email=email,
                phone=phone,
                additional_info=additional_info,
                debug=True,  # Enable debug logging
                headless=False  # Use headless mode since you were using it before
            )
        
        if booking_success:
            logger.info("Calendly appointment booked successfully")
        else:
            logger.error("Failed to book Calendly appointment")
        
        logger.info("Workflow completed successfully")
        return final_url
        
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    main()