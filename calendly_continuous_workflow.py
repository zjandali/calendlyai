import json
import logging
import os
import traceback
from datetime import datetime, timedelta
import time
import pytz
import requests
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
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

def run_calendly_workflow(
    calendly_url="https://calendly.com/robertjandali/30min",
    name="John Doe",
    email="john@doe.com",
    phone="5109198404",
    additional_info="This is a test booking",
    timezone="America/Los_Angeles",
    max_retries=3
):
    """
    Continuous workflow for Calendly booking process
    """
    #logger.info("Starting Calendly continuous workflow")
    
    try:
        # Step 1: Generate mock calendar data
        #logger.info("Generating mock calendar data")
        mock_calendar = generate_mock_calendar()
        #print(f"\nmock_calendar4234234234234234234234234234234: {mock_calendar}")
        # Step 2: Set up Calendly API and get event type UUID
        #logger.info(f"Setting up Calendly API for URL: {calendly_url}")
        url_parts = calendly_url.split('/')
        profile_slug = url_parts[-2]
        event_type_slug = url_parts[-1].split('?')[0]
        
        id_url = f"https://calendly.com/api/booking/event_types/lookup?event_type_slug={event_type_slug}&profile_slug={profile_slug}"
        response = requests.get(id_url)
        response.raise_for_status()
        
        event_data = response.json()
        uuid = event_data.get("uuid")
        
        if not uuid:
            raise ValueError("UUID not found in response")
        #logger.info(f"Successfully retrieved UUID: {uuid}")
        
        # Step 3: Get Calendly availability
        logger.info(f"Getting Calendly availability for UUID: {uuid}")
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
        calendly_data = calendar_response.json()
        #logger.info(f"Calendly data: {calendly_data}")
        # Step 4: Find matching times between calendars
        #logger.info("Finding matching available time slots")
        # Extract timezones
        tz1 = pytz.timezone(mock_calendar.get('availability_timezone', 'UTC'))
        tz2 = pytz.timezone(calendly_data.get('availability_timezone', tz1.zone))
        
        # Create sets of available times from both calendars
        times1 = set()
        times2 = set()
        
        # Extract times from mock calendar
        for day in mock_calendar.get('days', []):
            if day['status'] == 'available' and day.get('enabled', True):
                for spot in day.get('spots', []):
                    if spot['status'] == 'available' and spot.get('invitees_remaining', 0) > 0:
                        time = datetime.fromisoformat(spot['start_time'])
                        times1.add(time)
        
        # Extract times from Calendly calendar
        for day in calendly_data.get('days', []):
            if day['status'] == 'available' and day.get('enabled', True):
                for spot in day.get('spots', []):
                    if spot['status'] == 'available' and spot.get('invitees_remaining', 0) > 0:
                        time = datetime.fromisoformat(spot['start_time'])
                        times2.add(time)
        
        # Find intersection of available times
        matching_times = sorted(times1.intersection(times2))
        logger.info(f"Matching times: {matching_times}")
        # Step 5: Format matching times
        #logger.info(f"Formatting {len(matching_times)} matching time slots")
        formatted_times = []
        for time in matching_times:
            # Store the original ISO format for the actual booking
            iso_format = time.strftime("%Y-%m-%dT%H:%M:%S-07:00")
            readable_format = time.strftime("%A, %B %d, %Y at %I:%M %p")
            formatted_times.append({
                "iso": iso_format,
                "readable": readable_format
            })
        
        # Create a string representation for the LLM
        overlapping_calendar = "\n".join([f"{t['readable']} ({t['iso']})" for t in formatted_times])
        
        # If no matching times are available, return early
        if not formatted_times:
            logger.error("No matching available times found between calendars")
            logger.info(32235234234234234234234)
            return None
        
        # Step 6: Get suggested time from LLM
        #logger.info("Getting suggested meeting time from LLM")
        response_schema = ResponseSchema(
            name="suggested_time",
            description="The suggested meeting time in ISO 8601 format with UTC -07:00 timezone",
            type="string"
        )
        
        parser = StructuredOutputParser.from_response_schemas([response_schema])
        format_instructions = parser.get_format_instructions()
        
        prompt_template = scheduling_prompt()
        messages = prompt_template.format_messages(
            overlapping_availability=overlapping_calendar,
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
        logger.info(f"Suggested time: {suggested_time}")
        
        # Validate that the suggested time is actually in our available times
        suggested_time_valid = False
        for time_option in formatted_times:
            if suggested_time in time_option["iso"]:
                suggested_time_valid = True
                suggested_time = time_option["iso"]  # Use the exact format from our list
                break
        
        if not suggested_time_valid:
            logger.error(f"LLM suggested time {suggested_time} is not in available slots")
            # Fall back to the first available time
            suggested_time = formatted_times[0]["iso"]
            logger.info(f"Falling back to first available time: {suggested_time}")
        
        # Step 7: Create final booking URL
        #logger.info("Creating booking URL")
        # Extract the base URL without any parameters
        base_path = '/'.join(calendly_url.split('?')[0].split('/')[:-1]) 
        if calendly_url.endswith('/'):
            base_path = base_path[:-1]  # Remove trailing slash if present
            
        # Format the date for the URL parameters
        time_obj = datetime.fromisoformat(suggested_time.replace("-07:00", "+00:00"))
        date_str = time_obj.strftime("%Y-%m-%d")
        month_str = time_obj.strftime("%Y-%m")
        
        # Construct the URL with the proper format that Calendly expects
        final_url = f"{base_path}/{event_type_slug}/{suggested_time}?month={month_str}&date={date_str}"
        logger.info(f"Created booking URL: {final_url}")
        
        # Step 8: Book appointment with retry logic for reCAPTCHA
        #logger.info(f"Attempting to book appointment at {final_url} with up to {max_retries} retries")
        
        booking_success = False
        for attempt in range(1, max_retries + 1):
            
            #logger.info(f"Booking attempt {attempt} of {max_retries}")
            
            # Set up a new browser instance for each attempt
            #logger.info("Setting up Selenium with reCAPTCHA solver")
            test_ua = 'Mozilla/5.0 (Windows NT 4.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36'
            
            options = Options()
            options.add_argument("--headless")  # Remove for visible browser
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f'--user-agent={test_ua}')
            options.add_argument('--no-sandbox')
            options.add_argument("--disable-extensions")
            
            driver = webdriver.Chrome(options=options)
            solver = RecaptchaSolver(driver=driver)
            
            try:
                # Check for reCAPTCHA
                #logger.info(f"Navigating to {final_url} to check for reCAPTCHA")
                driver.get(final_url)
                
                # Check for multiple indicators of reCAPTCHA presence
                recaptcha_iframes = driver.find_elements(By.XPATH, '//iframe[contains(@src, "recaptcha")]')
                recaptcha_divs = driver.find_elements(By.XPATH, '//div[contains(@class, "g-recaptcha")]')
                recaptcha_scripts = driver.find_elements(By.XPATH, '//script[contains(@src, "recaptcha")]')
                
                recaptcha_solved = True
                if recaptcha_iframes and (recaptcha_divs or recaptcha_scripts):
                    #logger.info("reCAPTCHA confirmed on the page")
                    recaptcha_solved = False
                else:
                    logger.info("No reCAPTCHA detected on the page")
                
                if not recaptcha_solved:
                    #logger.warning(f"reCAPTCHA detected and could not be solved on attempt {attempt}")
                    # Close the browser before retrying
                    driver.quit()
                    
                    if attempt < max_retries:
                       # logger.info(f"Waiting 5 seconds before retry {attempt + 1}")
                        time.sleep(5)  # Add a delay before retrying
                        continue
                    else:
                        logger.error("Max retries reached, falling back to direct booking method")
                
                # If we get here, either no reCAPTCHA was detected or it was solved
                #logger.info("Proceeding with booking using current browser session")
                
                # Close this browser and use the imported function
                driver.quit()
                
                booking_success = book_calendly_appointment(
                    url=final_url,
                    name=name,
                    email=email,
                    phone=phone,
                    additional_info=additional_info,
                    debug=True,
                    headless=False
                )
                
                if booking_success:
                    #logger.info("Calendly appointment booked successfully")
                    break
                else:
                    #logger.error(f"Booking failed on attempt {attempt}")
                    if attempt < max_retries:
                        continue
            
            except Exception as e:
                #logger.error(f"Error during booking attempt {attempt}: {str(e)}")
                #logger.error(traceback.format_exc())
                
                # Make sure to close the browser before retrying
                try:
                    driver.quit()
                except:
                    pass
                
                if attempt < max_retries:
                    #logger.info(f"Waiting 5 seconds before retry {attempt + 1}")
                    time.sleep(5)
                    continue
        
        if booking_success:
            #logger.info("Calendly workflow completed successfully")
            return final_url
        else:
            #logger.error("All booking attempts failed")
            return None
            
    except Exception as e:
        #logger.error(f"Workflow failed: {str(e)}")
        #logger.error(f"Traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    run_calendly_workflow() 