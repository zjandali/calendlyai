#!/usr/bin/env python3
"""
Integrated Calendly Booking System

This script combines the calendar availability matching from book2.py
with the form submission capabilities of browser_base_selenium.py
to create a streamlined booking system without reCAPTCHA handling.
"""

import json
import logging
import os
import traceback
import time
from datetime import datetime, timedelta
from typing import Optional

import pytz
import requests
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from twocaptcha import TwoCaptcha

# Import the CalendlyScraper class
# from browser_base_selenium import CalendlyScraper
from prompts.scheduling_prompts import scheduling_prompt
from utils.calendar_utils import (
    generate_mock_calendar,
    format_calendar_data,
    convert_to_unified_format,
    find_overlapping_times
)

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

def setup_calendly_api(calendly_url: str) -> tuple:
    """
    Set up the Calendly API connection and get event type UUID
    """
    logger.info(f"Setting up Calendly API for URL: {calendly_url}")
    
    try:
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
            
        logger.info(f"Successfully retrieved UUID: {uuid}")
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
        str: Formatted string of times
    """
    formatted_times = []
    for time in matching_times:
        iso_format = time.strftime("%Y-%m-%dT%H:%M:%S-07:00")
        readable_format = time.strftime("%A, %B %d, %Y at %I:%M %p")
        formatted_times.append(f"{readable_format} ({iso_format})")
    
    # Join the times with line breaks for better readability in the prompt
    return "\n".join(formatted_times)

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

def get_suggested_time(overlapping_calendar: str) -> str:
    """
    Get suggested meeting time from LLM
    """
    try:
        response_schema = ResponseSchema(
            name="suggested_time",
            description="The suggested meeting time in ISO 8601 format with UTC -07:00 timezone",
            type="string"
        )
        
        parser = StructuredOutputParser.from_response_schemas([response_schema])
        format_instructions = parser.get_format_instructions()
        
        # Make sure the prompt explicitly requests UTC time
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
        
        return suggested_time
    except Exception as e:
        logger.error(f"Error getting suggested time: {str(e)}")
        raise

def create_booking_url(calendly_url: str, suggested_time: str) -> str:
    """
    Create the final booking URL
    """
    logger.info("Creating booking URL")
    
    try:
        base_path = '/'.join(calendly_url.split('?')[0].split('/')[:-1]) if calendly_url.endswith('/') else '/'.join(calendly_url.split('?')[0].split('/'))
        final_url = f"{base_path}/{suggested_time}"
        
        logger.info(f"Created booking URL: {final_url}")
        return final_url
        
    except Exception as e:
        logger.error(f"Error creating booking URL: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

class CalendlyScraper:
    """Class to handle Calendly form filling and submission."""
    
    def __init__(self, headless: bool = False, proxy: Optional[str] = None, 
                 captcha_api_key: Optional[str] = None):
        """
        Initialize the Calendly scraper.
        
        Args:
            headless: Whether to run Chrome in headless mode
            proxy: Optional proxy server to use
            captcha_api_key: API key for 2Captcha service
        """
        self.headless = headless
        self.proxy = proxy
        self.captcha_api_key = captcha_api_key
        self.driver = None
        self.wait_time = 10  # Default wait time in seconds
        
        # Initialize 2Captcha solver if API key is provided
        self.solver = None
        if self.captcha_api_key:
            self.solver = TwoCaptcha(self.captcha_api_key)
    
    def initialize_browser(self):
        """Initialize the Chrome WebDriver."""
        try:
            logger.info("Setting up WebDriver")
            
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            # Use random user agent
            ua = UserAgent()
            user_agent = ua.random
            options.add_argument(f'user-agent={user_agent}')
            
            # Add proxy if specified
            if self.proxy:
                options.add_argument(f'--proxy-server={self.proxy}')
            
            # Initialize Chrome WebDriver
            self.driver = webdriver.Chrome(
                ChromeDriverManager().install(),
                options=options
            )
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            logger.info("WebDriver set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing browser: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def navigate_to_url(self, url):
        """Navigate to the specified URL."""
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Handle cookie consent if present
            self._handle_cookie_consent()
            
            return True
        except Exception as e:
            logger.error(f"Error navigating to URL: {str(e)}")
            return False
    
    def _handle_cookie_consent(self):
        """Handle cookie consent dialogs if they appear."""
        try:
            # Common cookie consent button selectors
            selectors = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'Allow')]",
                "//button[contains(@class, 'cookie-consent')]",
                "//div[contains(@class, 'cookie-banner')]//button"
            ]
            
            for selector in selectors:
                try:
                    cookie_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info(f"Found cookie dialog, clicking: {selector}")
                    cookie_button.click()
                    time.sleep(1)
                    return
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error handling cookie consent: {str(e)}")
            # Non-critical error, continue execution
    
    def fill_name(self, name):
        """Fill in the name field."""
        try:
            # Common name field selectors
            selectors = [
                "//input[contains(@name, 'name')]",
                "//input[contains(@id, 'name')]",
                "//input[contains(@placeholder, 'name')]",
                "//label[contains(text(), 'Name')]/following::input[1]"
            ]
            
            for selector in selectors:
                try:
                    name_field = WebDriverWait(self.driver, self.wait_time).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    name_field.clear()
                    name_field.send_keys(name)
                    logger.info("Name filled successfully")
                    return True
                except:
                    continue
                    
            logger.error("Name field not found")
            return False
            
        except Exception as e:
            logger.error(f"Error filling name: {str(e)}")
            return False
    
    def fill_email(self, email):
        """Fill in the email field."""
        try:
            # Common email field selectors
            selectors = [
                "//input[contains(@name, 'email')]",
                "//input[contains(@id, 'email')]",
                "//input[contains(@placeholder, 'email')]",
                "//input[@type='email']",
                "//label[contains(text(), 'Email')]/following::input[1]"
            ]
            
            for selector in selectors:
                try:
                    email_field = WebDriverWait(self.driver, self.wait_time).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    email_field.clear()
                    email_field.send_keys(email)
                    logger.info("Email filled successfully")
                    return True
                except:
                    continue
                    
            logger.error("Email field not found")
            return False
            
        except Exception as e:
            logger.error(f"Error filling email: {str(e)}")
            return False
    
    def fill_phone(self, phone):
        """Fill in the phone field."""
        try:
            # Common phone field selectors
            selectors = [
                "//input[contains(@name, 'phone')]",
                "//input[contains(@id, 'phone')]",
                "//input[contains(@placeholder, 'phone')]",
                "//input[@type='tel']",
                "//label[contains(text(), 'Phone')]/following::input[1]"
            ]
            
            # Process phone number to handle different formats
            phone = phone.strip()
            if not phone.startswith('+'):
                # Add US country code if not present
                phone = '+1' + phone.lstrip('1')
                
            logger.info(f"Processing phone: country code=+1, digits={phone}")
            
            for selector in selectors:
                try:
                    phone_field = WebDriverWait(self.driver, self.wait_time).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    phone_field.clear()
                    phone_field.send_keys(phone)
                    logger.info("Phone filled successfully")
                    return True
                except:
                    continue
                    
            logger.error("Phone field not found")
            return False
            
        except Exception as e:
            logger.error(f"Error filling phone: {str(e)}")
            return False
    
    def fill_additional_info(self, additional_info):
        """Fill in the additional information field."""
        try:
            # Common additional info field selectors
            selectors = [
                "//textarea",
                "//textarea[contains(@name, 'message')]",
                "//textarea[contains(@id, 'message')]",
                "//textarea[contains(@placeholder, 'message')]",
                "//label[contains(text(), 'Additional')]/following::textarea[1]"
            ]
            
            for selector in selectors:
                try:
                    info_field = WebDriverWait(self.driver, self.wait_time).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    info_field.clear()
                    info_field.send_keys(additional_info)
                    logger.info("Additional info filled successfully")
                    return True
                except:
                    continue
                    
            logger.warning("Additional info field not found, skipping")
            return True  # Not critical for form submission
            
        except Exception as e:
            logger.error(f"Error filling additional info: {str(e)}")
            return False
    
    def submit_form(self):
        """Submit the form and handle confirmation."""
        try:
            # Common submit button selectors
            selectors = [
                "//button[contains(text(), 'Schedule')]",
                "//button[contains(text(), 'Book')]",
                "//button[contains(text(), 'Confirm')]",
                "//button[@type='submit']",
                "//input[@type='submit']"
            ]
            
            # Try each selector
            for selector in selectors:
                try:
                    submit_button = WebDriverWait(self.driver, self.wait_time).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info(f"Found submit button with selector: {selector}")
                    submit_button.click()
                    logger.info("Form submitted")
                    break
                except:
                    continue
            else:
                logger.error("Submit button not found")
                return False
            
            # Wait for confirmation page
            confirmation_selectors = [
                "//h1[contains(text(), 'confirmed')]",
                "//div[contains(text(), 'confirmed')]",
                "//h1[contains(text(), 'Confirmed')]",
                "//div[contains(text(), 'confirmed')]",
                "//div[contains(@class, 'confirmation')]"
            ]
            
            for selector in confirmation_selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    logger.info("Confirmation page detected")
                    return True
                except:
                    continue
            
            # If we reach here, assume success even without confirmation page
            logger.info("Form submitted successfully but no explicit confirmation found")
            return True
            
        except Exception as e:
            logger.error(f"Error submitting form: {str(e)}")
            return False
    
    def close_browser(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")

def book_calendly_meeting(
    calendly_url: str,
    name: str,
    email: str,
    phone: str,
    additional_info: str = None,
    timezone: str = "America/Los_Angeles",
    headless: bool = False,
    captcha_api_key: str = None
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
        headless: Whether to run browser in headless mode
        captcha_api_key: API key for 2Captcha (only used if booking page contains captcha)
        
    Returns:
        str: URL of the booked appointment or None if booking failed
    """
    logger.info("Starting integrated Calendly workflow")
    
    try:
        # Get mock calendar data
        logger.info("Generating mock calendar data")
        mock_calendar = generate_mock_calendar()
        
        # Set up Calendly API and get availability
        uuid, profile_slug, event_type_slug = setup_calendly_api(calendly_url)
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
        logger.info("Creating CalendlyScraper instance")
        scraper = CalendlyScraper(
            headless=headless,
            captcha_api_key=captcha_api_key
        )
        
        # Initialize browser
        logger.info("Initializing browser")
        scraper.initialize_browser()
        
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
        additional_info=additional_info,
        headless=False
    )
    
    if result:
        print(f"Booking successful! URL: {result}")
    else:
        print("Booking failed.")

if __name__ == "__main__":
    main() 