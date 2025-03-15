#!/usr/bin/env python3
"""
Enhanced Calendly Booking Form Scraper

This script provides an optimized version of the Calendly scraper with additional
error handling and performance improvements.
"""

import time
import random
import argparse
import logging
import sys
import os
from typing import Dict, Any, Optional, List, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calendly_scraper.log'))
    ]
)
logger = logging.getLogger(__name__)

class CalendlyScraper:
    """Class to handle Calendly form filling and submission with reCAPTCHA handling."""
    
    def __init__(self, headless: bool = False, proxy: Optional[str] = None, captcha_api_key: Optional[str] = None):
        """
        Initialize the Calendly scraper.
        
        Args:
            headless: Whether to run Chrome in headless mode
            proxy: Optional proxy server to use
            captcha_api_key: Optional API key for CAPTCHA solving service
        """
        self.headless = headless
        self.proxy = proxy
        self.captcha_api_key = captcha_api_key
        self.driver = None
        self.ua = UserAgent()
        self.wait_time = 10  # Default wait time in seconds
        
    def setup_driver(self) -> None:
        """Set up the Chrome WebDriver with appropriate options to avoid detection."""
        options = Options()
        
        # Rotate user agent to avoid detection
        user_agent = self.ua.random
        logger.info(f"Using User-Agent: {user_agent}")
        options.add_argument(f'user-agent={user_agent}')
        
        if self.headless:
            options.add_argument('--headless=new')  # Using the new headless mode
        
        # Add proxy if specified
        if self.proxy:
            options.add_argument(f'--proxy-server={self.proxy}')
        
        # Additional options to avoid detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--disable-gpu')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Create and configure the WebDriver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
        # Set window size to a common resolution
        self.driver.set_window_size(1366, 768)
        
        # Execute JavaScript to hide automation indicators
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        # Add additional JavaScript to mask automation
        self.driver.execute_script("""
            // Overwrite the 'navigator.languages' property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'es'],
            });
            
            // Overwrite the 'plugins' property
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)
        
        # Set up cookies to appear more like a returning user
        self.driver.execute_cdp_cmd('Network.enable', {})
        self.driver.execute_cdp_cmd('Network.setCacheDisabled', {'cacheDisabled': False})
        
    def navigate_to_url(self, url: str) -> bool:
        """
        Navigate to the specified Calendly URL.
        
        Args:
            url: The Calendly booking URL
            
        Returns:
            bool: True if navigation was successful, False otherwise
        """
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            
            # Wait for the page to load
            WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check for cookie consent dialogs and handle them
            self._handle_cookie_dialogs()
            
            # Take a screenshot for debugging
            self._take_screenshot("initial_page_load.png")
            
            return True
        except Exception as e:
            logger.error(f"Error navigating to URL: {e}")
            self._take_screenshot("navigation_error.png")
            return False
    
    def fill_form(self, form_data: Dict[str, Any]) -> bool:
        """
        Fill out the Calendly booking form with the provided data.
        
        Args:
            form_data: Dictionary containing form field values
            
        Returns:
            bool: True if form was filled successfully, False otherwise
        """
        try:
            logger.info("Filling out Calendly form")
            
            # Fill name field
            self._fill_input_field("Name", form_data.get("name", ""))
            
            # Fill email field
            self._fill_input_field("Email", form_data.get("email", ""))
            
            # Handle country code and phone number
            self._fill_phone_number(form_data.get("phone", ""))
            
            # Fill additional information if provided
            if "additional_info" in form_data and form_data["additional_info"]:
                self._fill_textarea("Please share anything", form_data["additional_info"])
            
            # Take a screenshot after filling the form
            self._take_screenshot("form_filled.png")
            
            logger.info("Form filled successfully")
            return True
        except Exception as e:
            logger.error(f"Error filling form: {e}")
            self._take_screenshot("form_fill_error.png")
            return False
    
    def submit_form(self) -> bool:
        """
        Submit the Calendly form and handle any reCAPTCHA challenges.
        
        Returns:
            bool: True if form was submitted successfully, False otherwise
        """
        try:
            logger.info("Attempting to submit form")
            
            # Debug: Print all buttons on the page
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                try:
                    button_text = button.text
                    button_class = button.get_attribute('class')
                    logger.debug(f"Found button: text='{button_text}', class='{button_class}'")
                except:
                    continue
            
            # Find and click the Schedule Event button using multiple selectors
            schedule_button = self._find_element_with_retry(
                By.XPATH, 
                """//button[
                    contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'schedule event') or 
                    contains(@class, 'submit') or 
                    contains(@type, 'submit')
                ]""",
                max_retries=3
            )
            
            if not schedule_button:
                logger.error("Could not find Schedule Event button")
                return False
            
            # Scroll to the button to ensure it's in view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", schedule_button)
            
            # Click the button
            try:
                schedule_button.click()
            except ElementClickInterceptedException:
                # Try using JavaScript to click if normal click is intercepted
                self.driver.execute_script("arguments[0].click();", schedule_button)
            
            # Take a screenshot after clicking submit
            self._take_screenshot("after_submit_click.png")
            
            # Check for reCAPTCHA and handle it if present
            recaptcha_result = self._handle_recaptcha()
            if recaptcha_result:
                logger.info("reCAPTCHA handled successfully")
                return True
            
            # Wait for confirmation page or error message
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda driver: "confirmed" in driver.current_url.lower() or 
                    "success" in driver.current_url.lower() or
                    "scheduled" in driver.current_url.lower() or
                    len(driver.find_elements(By.XPATH, "//div[contains(text(), 'confirmed')]")) > 0 or
                    len(driver.find_elements(By.XPATH, "//div[contains(text(), 'success')]")) > 0 or
                    len(driver.find_elements(By.XPATH, "//div[contains(text(), 'scheduled')]")) > 0
                )
                logger.info("Form submitted successfully")
                self._take_screenshot("submission_success.png")
                return True
            except TimeoutException:
                logger.warning("Could not confirm successful submission")
                self._take_screenshot("submission_timeout.png")
                
                # Check for error messages
                error_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'error')]")
                if error_elements:
                    for error in error_elements:
                        logger.error(f"Form error: {error.text}")
                
                return False
                
        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            self._take_screenshot("submission_error.png")
            return False
    
    def _fill_input_field(self, label_text: str, value: str) -> None:
        """
        Fill an input field identified by its label text.
        
        Args:
            label_text: Text of the label associated with the input field
            value: Value to enter in the field
        """
        try:
            # Find the label element
            label = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.XPATH, f"//label[contains(text(), '{label_text}')]"))
            )
            
            # Get the input field associated with the label
            input_field = self._find_element_with_retry(
                By.XPATH, f"//label[contains(text(), '{label_text}')]/following::input[1]"
            )
            
            if not input_field:
                # Try alternative XPath strategies
                input_field = self._find_element_with_retry(
                    By.XPATH, f"//label[contains(text(), '{label_text}')]/..//input"
                )
            
            if not input_field:
                raise Exception(f"Could not find input field for label: {label_text}")
            
            # Clear the field and enter the value with human-like typing
            input_field.clear()
            self._human_like_typing(input_field, value)
            
        except Exception as e:
            logger.error(f"Error filling input field '{label_text}': {e}")
            raise
    
    def _fill_textarea(self, label_text: str, value: str) -> None:
        """
        Fill a textarea field identified by its label text.
        
        Args:
            label_text: Text of the label associated with the textarea
            value: Value to enter in the field
        """
        try:
            # Find the label element
            label = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.XPATH, f"//label[contains(text(), '{label_text}')]"))
            )
            
            # Get the textarea field associated with the label
            textarea = self._find_element_with_retry(
                By.XPATH, f"//label[contains(text(), '{label_text}')]/following::textarea[1]"
            )
            
            if not textarea:
                # Try alternative XPath strategies
                textarea = self._find_element_with_retry(
                    By.XPATH, f"//label[contains(text(), '{label_text}')]/..//textarea"
                )
            
            if not textarea:
                raise Exception(f"Could not find textarea for label: {label_text}")
            
            # Clear the field and enter the value with human-like typing
            textarea.clear()
            self._human_like_typing(textarea, value)
            
        except Exception as e:
            logger.error(f"Error filling textarea '{label_text}': {e}")
            raise
    
    def _fill_phone_number(self, phone_number: str) -> None:
        """
        Fill the phone number field, handling country code selection if needed.
        
        Args:
            phone_number: Phone number to enter (with or without country code)
        """
        try:
            # Format phone number if it doesn't have a country code
            if not phone_number.startswith("+"):
                # Assume US number if no country code is provided
                phone_number = "+1 " + phone_number
            
            # Extract country code and phone digits
            parts = phone_number.split(" ", 1)
            country_code = parts[0]
            phone_digits = parts[1] if len(parts) > 1 else phone_number[len(country_code):]
            
            logger.info(f"Processing phone: country code={country_code}, digits={phone_digits}")
            
            # Find the country code selector - try multiple approaches
            country_selectors = self.driver.find_elements(
                By.XPATH, 
                """//div[contains(@class, 'phone-field-flag') or 
                      contains(@class, 'country-select') or 
                      contains(@role, 'combobox')]"""
            )
            
            if not country_selectors:
                # Try alternative selectors
                country_selectors = self.driver.find_elements(
                    By.XPATH,
                    """//div[contains(@class, 'flag')] | 
                       //div[contains(@class, 'country')] |
                       //div[contains(@class, 'phone')]//div[contains(@class, 'select')]"""
                )
            
            if country_selectors:
                # Take screenshot before clicking
                self._take_screenshot("before_country_select.png")
                
                # Click on the country code selector
                try:
                    # Try JavaScript click first as it's more reliable
                    self.driver.execute_script("arguments[0].click();", country_selectors[0])
                except:
                    try:
                        country_selectors[0].click()
                    except:
                        logger.warning("Could not click country selector, trying alternative methods")
                        # Try to find and click the flag directly
                        flags = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'flag')]")
                        if flags:
                            self.driver.execute_script("arguments[0].click();", flags[0])
                
                # Wait for dropdown to appear
                
                # Take screenshot after clicking
                self._take_screenshot("after_country_select_click.png")
                
                # For US numbers, explicitly search for United States
                if country_code == "+1":
                    # Try multiple approaches to find United States
                    us_found = False
                    
                    # First try: search for United States in the dropdown
                    search_inputs = self.driver.find_elements(
                        By.XPATH, "//input[contains(@placeholder, 'Search')]"
                    )
                    
                    if search_inputs:
                        try:
                            search_input = search_inputs[0]
                            search_input.clear()
                            self._human_like_typing(search_input, "United States")
                            
                            # Look for United States in the filtered results
                            us_options = self.driver.find_elements(
                                By.XPATH, "//span[contains(text(), 'United States')]"
                            )
                            
                            if us_options:
                                self.driver.execute_script("arguments[0].click();", us_options[0])
                                us_found = True
                        except Exception as e:
                            logger.warning(f"Error using search input: {e}")
                    
                    # Second try: scroll and find
                    if not us_found:
                        try:
                            # Try to find United States by scrolling
                            for _ in range(3):  # Try scrolling a few times
                                us_options = self.driver.find_elements(
                                    By.XPATH, 
                                    """//span[contains(text(), 'United States')] | 
                                       //div[contains(text(), 'United States')] |
                                       //li[contains(text(), 'United States')]"""
                                )
                                
                                if us_options:
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", us_options[0])
                                    self.driver.execute_script("arguments[0].click();", us_options[0])
                                    us_found = True
                                    break
                                
                                # Scroll down in the dropdown
                                dropdown = self.driver.find_elements(
                                    By.XPATH, "//ul[contains(@class, 'country') or contains(@role, 'listbox')]"
                                )
                                if dropdown:
                                    self.driver.execute_script(
                                        "arguments[0].scrollTop += 300;", dropdown[0]
                                    )
                                
                        except Exception as e:
                            logger.warning(f"Error scrolling to find United States: {e}")
                    
                    # If still not found, try clicking on +1 directly
                    if not us_found:
                        try:
                            plus_one_options = self.driver.find_elements(
                                By.XPATH, "//span[contains(text(), '+1')] | //div[contains(text(), '+1')]"
                            )
                            if plus_one_options:
                                self.driver.execute_script("arguments[0].click();", plus_one_options[0])
                        except Exception as e:
                            logger.warning(f"Error clicking +1 option: {e}")
                
                # If we couldn't select the country, close the dropdown
                try:
                    # Click outside to close dropdown
                    self.driver.find_element(By.TAG_NAME, "body").click()
                except:
                    pass
            
            # Find the phone number input field
            phone_input = self._find_element_with_retry(
                By.XPATH,
                """//input[
                    contains(@type, 'tel') or
                    contains(@id, 'phone') or
                    contains(@name, 'phone') or
                    contains(@placeholder, 'phone') or
                    preceding::label[contains(text(), 'Phone')]
                ]""",
                max_retries=3
            )
            
            if not phone_input:
                # Try alternative selectors
                phone_input = self._find_element_with_retry(
                    By.XPATH,
                    "//div[contains(@class, 'phone')]//input",
                    max_retries=2
                )
            
            if not phone_input:
                raise Exception("Could not find phone number input field")
            
            # Clear the field and enter the phone number with human-like typing
            phone_input.clear()
            self._human_like_typing(phone_input, phone_digits)
            
        except Exception as e:
            logger.error(f"Error filling phone number: {e}")
            raise
    
    def _handle_recaptcha(self) -> bool:
        """
        Handle reCAPTCHA if present on the page.
        
        Returns:
            bool: True if reCAPTCHA was handled successfully or not present, False otherwise
        """
        try:
            # Wait a moment to see if page title changes
            try:
                WebDriverWait(self.driver, 2).until(
                    lambda driver: "confirmed" in driver.title.lower() or 
                    "confirmed" in driver.title.lower() or 
                    "scheduled" in driver.title.lower() or
                    "thank" in driver.title.lower() or 
                    "confirmation" in driver.title.lower()
                )
                logger.info("Page title changed to indicate successful submission")
                self._take_screenshot("title_change_success.png")
                return True
            except TimeoutException:
                # Continue with normal flow if title doesn't change
                pass
            
            # Check if URL has changed to success/confirmation page
            current_url = self.driver.current_url.lower()
            page_title = self.driver.title.lower()
            
            # Check if URL or page title indicates successful submission
            if ("confirmed" in current_url or "success" in current_url or "scheduled" in current_url or
                "confirmed" in page_title or "success" in page_title or "scheduled" in page_title or
                "thank" in page_title or "confirmation" in page_title):
                logger.info("URL or page title indicates successful submission")
                self._take_screenshot("submission_success_before_recaptcha.png")
                return True
            
            # Check if reCAPTCHA iframe exists using multiple selectors
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, 
                """//iframe[
                    contains(@src, 'recaptcha') or 
                    contains(@title, 'reCAPTCHA') or
                    contains(@class, 'g-recaptcha')
                ]"""
            )
            
            if not recaptcha_frames:
                logger.info("No visible reCAPTCHA detected")
                return True
            
            logger.info("reCAPTCHA detected, attempting to handle")
            self._take_screenshot("recaptcha_detected.png")
            
            # Try each frame until we find the checkbox
            for frame in recaptcha_frames:
                try:
                    # Check URL again before switching frame
                    current_url = self.driver.current_url.lower()
                    if "confirmed" in current_url or "success" in current_url or "scheduled" in current_url:
                        logger.info("URL indicates successful submission during frame handling")
                        return True
                        
                    # Switch to the frame
                    self.driver.switch_to.frame(frame)
                    
                    # Try to find the checkbox using multiple selectors
                    checkbox = None
                    selectors = [
                        (By.ID, "recaptcha-anchor"),
                        (By.CLASS_NAME, "recaptcha-checkbox-border"),
                        (By.XPATH, "//div[@class='recaptcha-checkbox-border']"),
                        (By.XPATH, "//span[@id='recaptcha-anchor']")
                    ]
                    
                    for by, selector in selectors:
                        try:
                            checkbox = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((by, selector))
                            )
                            if checkbox and checkbox.is_displayed():
                                break
                        except:
                            continue
                    
                    if checkbox and checkbox.is_displayed():
                        # Try JavaScript click first
                        try:
                            self.driver.execute_script("arguments[0].click();", checkbox)
                        except:
                            # If JavaScript click fails, try regular click
                            checkbox.click()
                        
                        # Switch back to default content
                        self.driver.switch_to.default_content()
                        
                        # Check URL again after clicking
                        current_url = self.driver.current_url.lower()
                        if "confirmed" in current_url or "success" in current_url or "scheduled" in current_url:
                            logger.info("URL indicates successful submission after checkbox click")
                            return True
                        
                        # Check for challenge frame
                        challenge_frames = self.driver.find_elements(
                            By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/bframe')]"
                        )
                        
                        if challenge_frames:
                            logger.warning("reCAPTCHA challenge detected")
                            self._take_screenshot("recaptcha_challenge.png")
                            
                            if self.captcha_api_key:
                                logger.info("Attempting to solve reCAPTCHA challenge using API")
                                # Here you would integrate with a CAPTCHA solving service
                                return False
                            else:
                                logger.warning("No CAPTCHA API key provided, cannot solve challenge")
                                return False
                        
                        return True
                    
                except Exception as frame_error:
                    logger.debug(f"Error in frame {frame}: {frame_error}")
                    # Switch back to default content before trying next frame
                    try:
                        self.driver.switch_to.default_content()
                    except:
                        pass
                    continue
            
            # Check URL one final time
            current_url = self.driver.current_url.lower()
            if "confirmed" in current_url or "success" in current_url or "scheduled" in current_url:
                logger.info("URL indicates successful submission after frame checks")
                return True
                
            # If we get here, we couldn't find the checkbox in any frame
            logger.error("Could not find reCAPTCHA checkbox in any frame")
            return False
            
        except Exception as e:
            logger.error(f"Error handling reCAPTCHA: {e}")
            self._take_screenshot("recaptcha_error.png")
            # Make sure we switch back to default content
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False
    
    def _handle_cookie_dialogs(self) -> None:
        """Handle common cookie consent dialogs that might appear on the page."""
        try:
            # Look for common cookie accept buttons
            cookie_buttons = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'I understand')]",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Got it')]",
                "//button[contains(text(), 'Allow')]",
                "//button[contains(@id, 'cookie') and contains(text(), 'Accept')]",
                "//div[contains(@id, 'cookie')]//button[contains(text(), 'Accept')]"
            ]
            
            for xpath in cookie_buttons:
                buttons = self.driver.find_elements(By.XPATH, xpath)
                if buttons:
                    logger.info(f"Found cookie dialog, clicking: {xpath}")
                    try:
                        buttons[0].click()
                        return
                    except Exception as e:
                        logger.warning(f"Error clicking cookie button: {e}")
                        continue
        
        except Exception as e:
            logger.warning(f"Error handling cookie dialogs: {e}")
    
    def _human_like_typing(self, element, text: str) -> None:
        """
        Type text into an element without delays.
        
        Args:
            element: The web element to type into
            text: The text to type
        """
        element.send_keys(text)
    
    def _find_element_with_retry(self, by: By, value: str, max_retries: int = 3) -> Optional[Any]:
        """
        Find an element with retries and error handling.
        
        Args:
            by: Selenium By locator strategy
            value: Locator value
            max_retries: Maximum number of retry attempts
            
        Returns:
            The found element or None if not found
        """
        for attempt in range(max_retries):
            try:
                element = WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_element_located((by, value))
                )
                return element
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"Could not find element {by}={value} after {max_retries} attempts: {e}")
                    return None
                else:
                    logger.debug(f"Retry {attempt+1}/{max_retries} finding element {by}={value}")
    
    def _take_screenshot(self, filename: str) -> None:
        """
        Take a screenshot for debugging purposes.
        
        Args:
            filename: Name of the screenshot file
        """
        try:
            if self.driver:
                screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, filename)
                self.driver.save_screenshot(screenshot_path)
                logger.debug(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.warning(f"Error taking screenshot: {e}")
    
    def close(self) -> None:
        """Close the WebDriver and release resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None

def book_calendly_appointment(url: str, name: str, email: str, phone: str, 
                             additional_info: Optional[str] = None, 
                             headless: bool = False,
                             proxy: Optional[str] = None,
                             captcha_api_key: Optional[str] = None,
                             debug: bool = False) -> bool:
    """
    Book a Calendly appointment using the CalendlyScraper.
    
    Args:
        url: The Calendly booking URL
        name: Name to enter in the form
        email: Email to enter in the form
        phone: Phone number to enter in the form
        additional_info: Optional additional information to provide
        headless: Whether to run in headless mode
        proxy: Optional proxy server to use
        captcha_api_key: Optional API key for CAPTCHA solving service
        debug: Enable debug logging
        
    Returns:
        bool: True if booking was successful, False otherwise
    """
    # Set debug logging if requested
    if debug:
        logger.setLevel(logging.DEBUG)
    
    # Create form data dictionary
    form_data = {
        'name': name,
        'email': email,
        'phone': phone
    }
    
    if additional_info:
        form_data['additional_info'] = additional_info
    
    # Initialize the scraper
    scraper = CalendlyScraper(
        headless=headless, 
        proxy=proxy,
        captcha_api_key=captcha_api_key
    )
    
    try:
        # Set up the WebDriver
        scraper.setup_driver()
        
        # Navigate to the Calendly URL
        if not scraper.navigate_to_url(url):
            logger.error("Failed to navigate to the Calendly URL")
            return False
        
        # Fill out the form
        if not scraper.fill_form(form_data):
            logger.error("Failed to fill out the form")
            return False
        
        # Submit the form
        if scraper.submit_form():
            logger.info("Successfully submitted the Calendly booking form")
            return True
        else:
            logger.error("Failed to submit the form")
            return False
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False
    
    finally:
        # Clean up
        scraper.close()

def main():
    """Main function to run the Calendly scraper."""
    parser = argparse.ArgumentParser(description='Calendly Booking Form Scraper')
    parser.add_argument('--url', required=True, help='Calendly booking URL')
    parser.add_argument('--name', required=True, help='Name to enter in the form')
    parser.add_argument('--email', required=True, help='Email to enter in the form')
    parser.add_argument('--phone', required=True, help='Phone number to enter in the form')
    parser.add_argument('--info', help='Additional information to provide (optional)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--proxy', help='Proxy server to use (optional)')
    parser.add_argument('--captcha-api-key', help='API key for CAPTCHA solving service (optional)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    success = book_calendly_appointment(
        url=args.url,
        name=args.name,
        email=args.email,
        phone=args.phone,
        additional_info=args.info,
        headless=args.headless,
        proxy=args.proxy,
        captcha_api_key=args.captcha_api_key,
        debug=args.debug
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
