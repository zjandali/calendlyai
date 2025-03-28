"""
Browser automation utilities using Browserbase
"""

import os
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import RemoteConnection
from browserbase import Browserbase
import dotenv

dotenv.load_dotenv()


logger = logging.getLogger(__name__)

class BrowserbaseConnection(RemoteConnection):
    """Manage a single session with Browserbase."""

    def __init__(self, session_id, *args, **kwargs):
        self.session_id = session_id
        super().__init__(*args, **kwargs)

    def get_remote_connection_headers(self, parsed_url, keep_alive=False):
        headers = super().get_remote_connection_headers(parsed_url, keep_alive)
        headers.update({
            "x-bb-api-key": os.getenv('BROWSERBASE_API_KEY'),
            "session-id": self.session_id,
        })
        return headers

class CalendlyScraper:
    """Class to handle Calendly form filling and submission with Browserbase."""
    
    def __init__(self, browserbase_api_key=os.getenv('BROWSERBASE_API_KEY'), 
                 browserbase_project_id=os.getenv('BROWSERBASE_PROJECT_ID')):
        """
        Initialize the Calendly scraper with Browserbase.
        
        Args:
            browserbase_api_key: API key for Browserbase (defaults to environment variable)
            browserbase_project_id: Project ID for Browserbase (defaults to environment variable)
        """
        self.browserbase_api_key = browserbase_api_key
        self.browserbase_project_id = browserbase_project_id
        self.driver = None
        self.bb_session = None
    
    def initialize_browser(self):
        """Initialize the browser using Browserbase."""
        try:
            logger.info("Setting up Browserbase WebDriver")
            
            # Initialize Browserbase client
            bb = Browserbase(api_key=self.browserbase_api_key)
            
            # Create a new browser session with default settings
            self.bb_session = bb.sessions.create(project_id=self.browserbase_project_id)
            
            # Use the updated remote connection approach
            custom_conn = BrowserbaseConnection(
                self.bb_session.id, 
                self.bb_session.selenium_remote_url
            )
            options = webdriver.ChromeOptions()
            self.driver = webdriver.Remote(custom_conn, options=options)
            
            logger.info("Successfully set up Browserbase WebDriver")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Browserbase: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def navigate_to_url(self, url):
        """Navigate to the specified URL."""
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            return True
        except Exception as e:
            logger.error(f"Error navigating to URL: {str(e)}")
            return False
    
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
                    # Try to find and fill without explicit wait
                    name_field = self.driver.find_element(By.XPATH, selector)
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
                    # Try to find and fill without explicit wait
                    email_field = self.driver.find_element(By.XPATH, selector)
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
                
            logger.info(f"Processing phone: {phone}")
            
            for selector in selectors:
                try:
                    # Try to find and fill without explicit wait
                    phone_field = self.driver.find_element(By.XPATH, selector)
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
                    # Try to find and fill without explicit wait
                    info_field = self.driver.find_element(By.XPATH, selector)
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
                    # Try to find and click without explicit wait
                    submit_button = self.driver.find_element(By.XPATH, selector)
                    if submit_button.is_displayed() and submit_button.is_enabled():
                        logger.info(f"Found submit button with selector: {selector}")
                        submit_button.click()
                        logger.info("Form submitted")
                        break
                except:
                    continue
            else:
                logger.error("Submit button not found")
                return False
            
            # Check for confirmation without explicit wait
            confirmation_selectors = [
                "//h1[contains(text(), 'confirmed')]",
                "//div[contains(text(), 'confirmed')]",
                "//h1[contains(text(), 'Confirmed')]",
                "//div[contains(text(), 'Confirmed')]",
                "//div[contains(@class, 'confirmation')]"
            ]
            
            for selector in confirmation_selectors:
                try:
                    confirmed = self.driver.find_element(By.XPATH, selector)
                    if confirmed.is_displayed():
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
        """Close the browser and release resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")
        
        # Browserbase session is automatically closed when the driver quits
        self.bb_session = None 