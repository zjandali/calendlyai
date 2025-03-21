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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

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
import requests
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
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
            captcha_api_key: API key for 2Captcha service
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
            # Check if it's a Bright Data proxy (string starting with 'bright:')
            if self.proxy.startswith('bright:'):
                # Extract Bright Data credentials from the proxy string
                # Format: 'bright:username:password'
                _, proxy_username, proxy_password = self.proxy.split(':')
                
                # Bright Data Proxy Configuration
                proxy_host = "brd.superproxy.io"
                proxy_port = "33335"  # Default Bright Data super proxy port
                
                # Full Proxy URL
                bright_proxy = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
                logger.info(f"Using Bright Data proxy: {proxy_username}@{proxy_host}")
                
                options.add_argument(f'--proxy-server={bright_proxy}')
                options.add_argument('--ignore-certificate-errors')  # Ignore SSL errors
            else:
                # Regular proxy handling (existing code)
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
    
    def submit_form(self) -> Any:
        """
        Submit the Calendly form and handle any reCAPTCHA challenges.
        
        Returns:
            Union[bool, str]: True if form was submitted successfully, 
                             "restart_needed" if reCAPTCHA detected, False otherwise
        """
        try:
            logger.info("Checking for reCAPTCHA before submission")
            
            # Check for reCAPTCHA before attempting to submit
            recaptcha_result = self._check_and_handle_recaptcha()
            if recaptcha_result == "restart_needed":
                logger.info("reCAPTCHA detected, need restart with new session")
                return "restart_needed"
            elif recaptcha_result is False:
                logger.error("Failed to handle reCAPTCHA before submission")
                return False
                
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
            
            # Check for reCAPTCHA again after submission
            if self._recaptcha_is_present():
                logger.info("reCAPTCHA detected after submission, attempting to handle")
                recaptcha_result = self._handle_recaptcha()
                if recaptcha_result == "restart_needed":
                    logger.info("reCAPTCHA could not be handled, need restart with new session")
                    return "restart_needed"
                elif recaptcha_result is False:
                    logger.error("Failed to handle reCAPTCHA after submission")
                    return False
            
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
    
    def _check_and_handle_recaptcha(self) -> Any:
        """
        Check if reCAPTCHA is present on the page and handle it if needed.
        
        Returns:
            Union[bool, str]: True if reCAPTCHA was handled successfully or not present, 
                             "restart_needed" if reCAPTCHA couldn't be solved, False otherwise
        """
        try:
            # Check if reCAPTCHA is present on the page
            if not self._recaptcha_is_present():
                logger.info("No reCAPTCHA detected on the page before submission")
                return True
                
            logger.info("reCAPTCHA detected before form submission, attempting to solve")
            self._take_screenshot("recaptcha_detected_before_submit.png")
            
            return self._handle_recaptcha()
            
        except Exception as e:
            logger.error(f"Error checking for reCAPTCHA: {e}")
            self._take_screenshot("recaptcha_check_error.png")
            return False
            
    def _recaptcha_is_present(self) -> bool:
        """
        Check if reCAPTCHA is present on the page.
        
        Returns:
            bool: True if reCAPTCHA is detected, False otherwise
        """
        try:
            # Check for "Confirm you're human" modal
            confirm_human_headers = self.driver.find_elements(
                By.XPATH, "//h2[contains(text(), 'Confirm you') and contains(text(), 'human')]"
            )
            if confirm_human_headers:
                logger.info("'Confirm you're human' modal detected")
                return True
                
            # Check for reCAPTCHA iframes
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@title, 'reCAPTCHA')]"
            )
            if recaptcha_frames:
                logger.info("reCAPTCHA iframe detected")
                return True
                
            # Check for reCAPTCHA divs
            recaptcha_divs = self.driver.find_elements(
                By.XPATH, "//div[@class='g-recaptcha' or contains(@data-sitekey, 'recaptcha')]"
            )
            if recaptcha_divs:
                logger.info("reCAPTCHA div detected")
                return True
                
            # Check for CAPTCHA text
            captcha_text = self.driver.find_elements(
                By.XPATH, "//*[contains(text(), 'CAPTCHA') or contains(text(), 'captcha')]"
            )
            if captcha_text:
                logger.info("CAPTCHA text detected on page")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking for reCAPTCHA presence: {e}")
            return False
    
    def _handle_recaptcha(self) -> Any:
        """
        Handle reCAPTCHA if present on the page using 2Captcha API.
        
        Returns:
            Union[bool, str]: True if reCAPTCHA was handled successfully or not present, 
                             "restart_needed" if reCAPTCHA couldn't be solved, False otherwise
        """
        try:
            # Check if "Confirm you're human" modal is present
            confirm_human_headers = self.driver.find_elements(
                By.XPATH, "//h2[contains(text(), 'Confirm you') and contains(text(), 'human')]"
            )
            
            if not confirm_human_headers:
                logger.info("No 'Confirm you're human' modal detected")
                return True
            
            logger.info("reCAPTCHA modal detected, attempting to solve")
            self._take_screenshot("recaptcha_modal_detected.png")
            
            # Find the reCAPTCHA iframe
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@title, 'reCAPTCHA')]"
            )
            
            if not recaptcha_frames:
                logger.error("Could not find reCAPTCHA iframe in modal")
                return "restart_needed"
            
            # Check for error message
            error_message = self.driver.find_elements(
                By.XPATH, "//div[contains(text(), 'CAPTCHA check failed')]"
            )
            if error_message:
                logger.warning("Found 'CAPTCHA check failed' error message")
            
            # 1. First try direct checkbox click
            try:
                # Switch to the reCAPTCHA iframe
                self.driver.switch_to.frame(recaptcha_frames[0])
                
                # Find and click the checkbox
                checkbox = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".recaptcha-checkbox-border"))
                )
                
                logger.info("Clicking reCAPTCHA checkbox")
                checkbox.click()
                
                # Switch back to main content
                self.driver.switch_to.default_content()
                
                # Wait to see if checkbox was successful
                time.sleep(3)
                
                # Check if Continue button is enabled
                continue_button = self._find_element_with_retry(
                    By.XPATH, "//button[contains(text(), 'Continue')]", max_retries=2
                )
                
                if continue_button and continue_button.is_enabled():
                    logger.info("reCAPTCHA solved by checkbox click")
                    continue_button.click()
                    return True
                
            except Exception as e:
                logger.warning(f"Error during checkbox click: {e}")
                # Switch back to main content
                self.driver.switch_to.default_content()
            
            # 2. If checkbox click failed, use 2Captcha
            if not self.captcha_api_key:
                logger.error("No 2Captcha API key provided")
                return "restart_needed"
            
            # Extract the site key
            site_key = self._extract_recaptcha_site_key()
            if not site_key:
                logger.error("Could not extract reCAPTCHA site key")
                return "restart_needed"
            
            # Solve using 2Captcha
            logger.info(f"Attempting to solve reCAPTCHA with 2Captcha API key: {self.captcha_api_key[:5]}...{self.captcha_api_key[-5:]}")
            token = self._solve_recaptcha_with_2captcha(site_key)
            if not token:
                logger.error("Failed to solve reCAPTCHA with 2Captcha")
                return "restart_needed"
            
            # Inject the token
            token_injected = self._inject_recaptcha_token(token)
            if not token_injected:
                logger.error("Failed to inject reCAPTCHA token")
                return "restart_needed"
            
            # Wait a moment for the page to process
            time.sleep(2)
            
            # Find and click the Continue button
            continue_button = self._find_element_with_retry(
                By.XPATH, "//button[contains(text(), 'Continue')]", max_retries=2
            )
            
            if continue_button:
                logger.info("Found Continue button after solving reCAPTCHA")
                try:
                    # Take a screenshot before clicking
                    self._take_screenshot("before_continue_click.png")
                    
                    # Try several methods to click the button
                    try:
                        continue_button.click()
                    except:
                        try:
                            self.driver.execute_script("arguments[0].click();", continue_button)
                        except:
                            from selenium.webdriver.common.action_chains import ActionChains
                            ActionChains(self.driver).move_to_element(continue_button).click().perform()
                    
                    # Take a screenshot after clicking
                    self._take_screenshot("after_continue_click.png")
                    
                    # Wait to see if we get past the CAPTCHA modal
                    time.sleep(2)
                    
                    # Check if modal is still present
                    confirm_modal = self.driver.find_elements(
                        By.XPATH, "//h2[contains(text(), 'Confirm you') and contains(text(), 'human')]"
                    )
                    if not confirm_modal:
                        logger.info("Successfully passed reCAPTCHA verification")
                        return True
                    
                    # Check for error message again
                    error_message = self.driver.find_elements(
                        By.XPATH, "//div[contains(text(), 'CAPTCHA check failed')]"
                    )
                    if error_message:
                        logger.warning("Still seeing 'CAPTCHA check failed' error after token injection")
                        return "restart_needed"
                    
                except Exception as e:
                    logger.error(f"Error clicking Continue button: {e}")
                    return "restart_needed"
            
            return "restart_needed"
            
        except Exception as e:
            logger.error(f"Error handling reCAPTCHA: {e}")
            self._take_screenshot("recaptcha_error.png")
            # Make sure we switch back to default content
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return "restart_needed"
    
    def _extract_recaptcha_site_key(self) -> Optional[str]:
        """
        Extract the reCAPTCHA site key from the page.
        
        Returns:
            Optional[str]: The site key or None if not found
        """
        try:
            # Method 1: Try to find the site key in a div with data-sitekey attribute
            elements = self.driver.find_elements(
                By.XPATH, "//div[@data-sitekey]|//div[@class='g-recaptcha' and @data-sitekey]"
            )
            if elements:
                site_key = elements[0].get_attribute('data-sitekey')
                if site_key:
                    logger.info(f"Found reCAPTCHA site key: {site_key}")
                    return site_key
            
            # Method 2: Try to extract from the reCAPTCHA iframe src
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, "//iframe[contains(@src, 'recaptcha')]"
            )
            if recaptcha_frames:
                src = recaptcha_frames[0].get_attribute('src')
                if src:
                    import re
                    match = re.search(r'[?&]k=([^&]+)', src)
                    if match:
                        site_key = match.group(1)
                        logger.info(f"Extracted reCAPTCHA site key from iframe: {site_key}")
                        return site_key
            
            # Method 3: Execute JavaScript to find the site key
            site_key = self.driver.execute_script("""
                return document.querySelector('.g-recaptcha').getAttribute('data-sitekey') || 
                       document.querySelector('div[data-sitekey]').getAttribute('data-sitekey') || 
                       document.querySelector('iframe[src*="recaptcha"]').getAttribute('src').match(/[?&]k=([^&]+)/)[1];
            """)
            if site_key:
                logger.info(f"Found reCAPTCHA site key via JavaScript: {site_key}")
                return site_key
            
            logger.error("Could not extract reCAPTCHA site key")
            return None
        except Exception as e:
            logger.error(f"Error extracting reCAPTCHA site key: {e}")
            return None

    def _solve_recaptcha_with_2captcha(self, site_key: str) -> Optional[str]:
        """
        Solve reCAPTCHA using 2Captcha API.
        
        Args:
            site_key: The reCAPTCHA site key
            
        Returns:
            Optional[str]: The solved token or None if unsuccessful
        """
        try:
            api_key = self.captcha_api_key
            current_url = self.driver.current_url
            
            # Create the task
            create_task_url = "https://api.2captcha.com/createTask"
            create_task_payload = {
                "clientKey": api_key,
                "task": {
                    "type": "RecaptchaV2TaskProxyless",
                    "websiteURL": current_url,
                    "websiteKey": site_key,
                }
            }
            
            logger.info("Sending reCAPTCHA solving request to 2Captcha")
            response = requests.post(create_task_url, json=create_task_payload)
            
            if response.status_code != 200:
                logger.error(f"Error response from 2Captcha API: {response.text}")
                return None
            
            response_data = response.json()
            
            if response_data.get('errorId') != 0:
                logger.error(f"2Captcha API error: {response_data.get('errorDescription', 'Unknown error')}")
                return None
            
            task_id = response_data.get('taskId')
            if not task_id:
                logger.error("No task ID received from 2Captcha")
                return None
            
            logger.info(f"2Captcha task created with ID: {task_id}")
            
            # Poll for the result
            get_result_url = "https://api.2captcha.com/getTaskResult"
            max_attempts = 30
            polling_interval = 5  # seconds
            
            for attempt in range(max_attempts):
                logger.info(f"Polling for result (attempt {attempt+1}/{max_attempts})")
                time.sleep(polling_interval)
                
                get_result_payload = {
                    "clientKey": api_key,
                    "taskId": task_id
                }
                
                result_response = requests.post(get_result_url, json=get_result_payload)
                
                if result_response.status_code != 200:
                    logger.error(f"Error response when polling 2Captcha: {result_response.text}")
                    continue
                
                result_data = result_response.json()
                
                if result_data.get('errorId') != 0:
                    logger.error(f"2Captcha API error when polling: {result_data.get('errorDescription', 'Unknown error')}")
                    continue
                
                if result_data.get('status') == 'ready':
                    token = result_data.get('solution', {}).get('token')
                    if token:
                        logger.info("Successfully received reCAPTCHA token from 2Captcha")
                        return token
                    else:
                        logger.error("No token in the 2Captcha response")
                        return None
                
                logger.info(f"Status: {result_data.get('status', 'unknown')}, waiting...")
            
            logger.error("Timed out waiting for 2Captcha result")
            return None
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA with 2Captcha: {e}")
            return None

    def _inject_recaptcha_token(self, token: str) -> bool:
        """
        Inject the reCAPTCHA token into the page.
        
        Args:
            token: The reCAPTCHA token from 2Captcha
            
        Returns:
            bool: True if injection was successful, False otherwise
        """
        try:
            logger.info("Injecting reCAPTCHA token into the page")
            
            # Take a screenshot before injection
            self._take_screenshot("before_token_injection.png")
            
            # Method 1: Find all potential response elements and set the token
            all_frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            recaptcha_frames = []
            
            # Find all reCAPTCHA frames
            for frame in all_frames:
                src = frame.get_attribute("src")
                if src and ("recaptcha" in src or "recaptcha" in frame.get_attribute("title", "")):
                    recaptcha_frames.append(frame)
            
            # Try to set token in all frames
            success = False
            
            # First try setting it in the main document
            try:
                main_script = f"""
                document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
                return true;
                """
                success = self.driver.execute_script(main_script) or success
            except:
                pass
            
            # Then try in each iframe
            for frame in recaptcha_frames:
                try:
                    self.driver.switch_to.frame(frame)
                    frame_script = f"""
                    document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
                    return true;
                    """
                    success = self.driver.execute_script(frame_script) or success
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()
            
            # If we couldn't set it directly, try the comprehensive approach
            if not success:
                comprehensive_script = f"""
                // Set token in the g-recaptcha-response textarea
                var responses = document.getElementsByName('g-recaptcha-response');
                var success = false;
                
                for (var i = 0; i < responses.length; i++) {{
                    responses[i].innerHTML = '{token}';
                    success = true;
                }}
                
                // For invisible reCAPTCHA
                if (typeof(___grecaptcha_cfg) !== 'undefined') {{
                    try {{
                        var widgetIds = Object.keys(___grecaptcha_cfg.clients);
                        for (var i = 0; i < widgetIds.length; i++) {{
                            var client = ___grecaptcha_cfg.clients[widgetIds[i]];
                            
                            // Try multiple callback paths
                            for (var key in client) {{
                                if (client[key] && typeof client[key].callback === 'function') {{
                                    client[key].callback('{token}');
                                    success = true;
                                }}
                            }}
                        }}
                    }} catch (e) {{
                        console.error("Error in reCAPTCHA callback:", e);
                    }}
                }}
                
                // Try to trigger the callback directly
                var captchaElements = document.querySelectorAll('[data-callback]');
                for (var i = 0; i < captchaElements.length; i++) {{
                    var callback = captchaElements[i].getAttribute('data-callback');
                    if (callback && window[callback]) {{
                        window[callback]('{token}');
                        success = true;
                    }}
                }}
                
                return success;
                """
                
                success = self.driver.execute_script(comprehensive_script) or success
            
            # Take a screenshot after injection
            self._take_screenshot("after_token_injection.png")
            
            if success:
                logger.info("Successfully injected reCAPTCHA token")
                return True
            else:
                logger.warning("Could not inject reCAPTCHA token")
                return False
            
        except Exception as e:
            logger.error(f"Error injecting reCAPTCHA token: {e}")
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
                             debug: bool = False,
                             max_retries: int = 3,
                             proxy_list: Optional[List[str]] = None) -> bool:
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
        max_retries: Maximum number of retry attempts
        proxy_list: Optional list of proxy servers to rotate through
        
    Returns:
        bool: True if booking was successful, False otherwise
    """
    # Set debug logging if requested
    if debug:
        logger.setLevel(logging.DEBUG)
    
    # Log the captcha API key status
    if captcha_api_key:
        logger.info(f"Using 2Captcha API key: {captcha_api_key[:5]}...{captcha_api_key[-5:]}")
    else:
        logger.warning("No 2Captcha API key provided")
    
    # Create form data dictionary
    form_data = {
        'name': name,
        'email': email,
        'phone': phone
    }
    
    if additional_info:
        form_data['additional_info'] = additional_info
    
    # Initialize proxy rotation if proxy_list is provided
    current_proxy_index = 0
    if proxy_list and len(proxy_list) > 0:
        # Start with the provided proxy if any
        if proxy and proxy in proxy_list:
            current_proxy_index = proxy_list.index(proxy)
        proxy = proxy_list[current_proxy_index]
    
    for attempt in range(max_retries):
        logger.info(f"Attempt {attempt + 1}/{max_retries} to book appointment")
        
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
                # Rotate proxy and user agent before retry
                if proxy_list and len(proxy_list) > 1:
                    current_proxy_index = (current_proxy_index + 1) % len(proxy_list)
                    proxy = proxy_list[current_proxy_index]
                    logger.info(f"Rotating to new proxy: {proxy}")
                continue  # Try again with a new browser session
            
            # Fill out the form
            if not scraper.fill_form(form_data):
                logger.error("Failed to fill out the form")
                # Rotate proxy and user agent before retry
                if proxy_list and len(proxy_list) > 1:
                    current_proxy_index = (current_proxy_index + 1) % len(proxy_list)
                    proxy = proxy_list[current_proxy_index]
                    logger.info(f"Rotating to new proxy: {proxy}")
                continue  # Try again with a new browser session
            
            # Submit the form
            submit_result = scraper.submit_form()
            
            if submit_result == "restart_needed":
                logger.info(f"reCAPTCHA detected on attempt {attempt + 1}, restarting with new browser agent")
                # Properly close the current scraper
                scraper.close()
                
                # Rotate proxy if available
                if proxy_list and len(proxy_list) > 1:
                    current_proxy_index = (current_proxy_index + 1) % len(proxy_list)
                    proxy = proxy_list[current_proxy_index]
                    logger.info(f"Rotating to new proxy: {proxy}")
                    
                # Wait a bit before retry to avoid detection patterns
                time.sleep(random.uniform(3, 7))
                continue  # Try again with a new browser session
            
            if submit_result:
                logger.info("Successfully submitted the Calendly booking form")
                return True
            else:
                logger.error("Failed to submit the form")
                # Rotate proxy and user agent before retry
                if proxy_list and len(proxy_list) > 1:
                    current_proxy_index = (current_proxy_index + 1) % len(proxy_list)
                    proxy = proxy_list[current_proxy_index]
                    logger.info(f"Rotating to new proxy: {proxy}")
                continue  # Try again with a new browser session
        
        except Exception as e:
            logger.error(f"An error occurred on attempt {attempt + 1}: {e}")
            # Rotate proxy and user agent before retry
            if proxy_list and len(proxy_list) > 1:
                current_proxy_index = (current_proxy_index + 1) % len(proxy_list)
                proxy = proxy_list[current_proxy_index]
                logger.info(f"Rotating to new proxy: {proxy}")
            continue  # Try again with a new browser session
        
        finally:
            # Clean up
            scraper.close()
    
    logger.error(f"Failed to book appointment after {max_retries} attempts")
    return False

def main():
    """Main function to run the Calendly scraper."""
    # Load the API key directly
    captcha_api_key = '36483071b9fe06d051d4b66f3beca836'
    if captcha_api_key:
        logger.info(f"Found 2CAPTCHA_API_KEY in environment: {captcha_api_key[:5]}...{captcha_api_key[-5:]}")
    else:
        logger.warning("2CAPTCHA_API_KEY not found in environment variables")
    
    parser = argparse.ArgumentParser(description='Calendly Booking Form Scraper')
    parser.add_argument('--url', default='https://calendly.com/robertjandali/30min/2025-03-27T00:00:00-07:00', 
                        help='Calendly booking URL (default: %(default)s)')
    parser.add_argument('--name', default='Robert Jandali', 
                        help='Name to enter in the form (default: %(default)s)')
    parser.add_argument('--email', default='robert@jandali.com', 
                        help='Email to enter in the form (default: %(default)s)')
    parser.add_argument('--phone', default='5109198404', 
                        help='Phone number to enter in the form (default: %(default)s)')
    parser.add_argument('--info', default=None, 
                        help='Additional information to provide (optional)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--proxy', help='Proxy server to use (optional)')
    parser.add_argument('--bright-data', action='store_true', 
                        help='Use Bright Data proxy (requires --bright-username and --bright-password)')
    parser.add_argument('--bright-username', default='hl_3b9ca4fa', 
                        help='Bright Data username (default: %(default)s)')
    parser.add_argument('--bright-password', default='ga8f1xepto43', 
                        help='Bright Data password (default: %(default)s)')
    parser.add_argument('--captcha-api-key', default=captcha_api_key, 
                        help='API key for CAPTCHA solving service (default: %(default)s)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--max-retries', type=int, default=3, 
                        help='Maximum number of retry attempts (default: %(default)s)')
    parser.add_argument('--proxy-list', nargs='+', help='List of proxy servers to rotate through')
    
    args = parser.parse_args()
    
    # Convert the proxy list argument to a proper list
    proxy_list = args.proxy_list if args.proxy_list else None
    
    # Set up Bright Data proxy if requested
    if args.bright_data:
        proxy = f"bright:{args.bright_username}:{args.bright_password}"
        logger.info(f"Using Bright Data proxy with username: {args.bright_username}")
    else:
        proxy = args.proxy
    
    success = book_calendly_appointment(
        url=args.url,
        name=args.name,
        email=args.email,
        phone=args.phone,
        additional_info=args.info,
        headless=args.headless,
        proxy=proxy,
        captcha_api_key=args.captcha_api_key,
        debug=args.debug,
        max_retries=args.max_retries,
        proxy_list=proxy_list
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
