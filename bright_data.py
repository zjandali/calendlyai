#!/usr/bin/env python3
"""
Enhanced Calendly Booking Form Scraper with Bright Data Integration

This script provides an optimized version of the Calendly scraper with Bright Data
proxy and reCAPTCHA bypass capabilities for automated booking.
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
    
    def __init__(self, headless: bool = False, bright_username: Optional[str] = None, 
                 bright_password: Optional[str] = None, captcha_api_key: Optional[str] = None):
        """
        Initialize the Calendly scraper.
        
        Args:
            headless: Whether to run Chrome in headless mode
            bright_username: Bright Data username
            bright_password: Bright Data password
            captcha_api_key: API key for 2Captcha service (optional, as Bright Data handles reCAPTCHA)
        """
        self.headless = headless
        self.bright_username = bright_username
        self.bright_password = bright_password
        self.captcha_api_key = captcha_api_key
        self.driver = None
        self.ua = UserAgent()
        self.wait_time = 10  # Default wait time in seconds
        
    def setup_driver(self) -> None:
        """Set up the Chrome WebDriver with Bright Data proxy and anti-detection options."""
        import subprocess
        import os
        import time
        from selenium.webdriver.chrome.options import Options
        
        # Kill any existing Chrome processes to avoid conflicts
        try:
            subprocess.run(['pkill', 'chrome'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', 'chromedriver'], stderr=subprocess.DEVNULL)
            time.sleep(1)  # Give processes time to terminate
        except Exception as e:
            logger.warning(f"Error killing existing Chrome processes: {e}")
        
        options = Options()
        
        # Rotate user agent to avoid detection
        user_agent = self.ua.random
        logger.info(f"Using User-Agent: {user_agent}")
        options.add_argument(f'user-agent={user_agent}')
        
        # Create a completely fresh temporary directory for Chrome data
        import tempfile
        import shutil
        
        # Create a unique temporary directory
        temp_dir = tempfile.mkdtemp(prefix="chrome_data_")
        logger.info(f"Created temporary directory for Chrome: {temp_dir}")
        
        # Force Chrome to use this directory and disable any user profile loading
        options.add_argument(f"--user-data-dir={temp_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--disable-sync")
        options.add_argument("--incognito")
        
        if self.headless:
            options.add_argument('--headless=new')  # Using the new headless mode
        
        # Configure Bright Data proxy if credentials are provided
        if self.bright_username and self.bright_password:
            # Bright Data Proxy Configuration
            proxy_host = "brd.superproxy.io"
            proxy_port = "22225"  # Bright Data proxy port for CAPTCHA bypass
            proxy_username = f"{self.bright_username}-session-{random.randint(1000000, 9999999)}"  # Add session ID for consistent IP
            proxy_password = self.bright_password
            
            # Full Proxy URL
            bright_proxy = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
            logger.info(f"Using Bright Data proxy: {proxy_username}@{proxy_host}")
            
            options.add_argument(f'--proxy-server={bright_proxy}')
            options.add_argument('--ignore-certificate-errors')  # Ignore SSL errors
        
        # Additional options to avoid detection and prevent user data directory issues
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-first-run')
        options.add_argument('--no-default-browser-check')
        options.add_argument('--password-store=basic')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-features=UserDataDir')
        options.add_argument('--disable-application-cache')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Create and configure the WebDriver
        try:
            # Use a direct path to chromedriver to avoid WebDriver Manager issues
            chromedriver_path = ChromeDriverManager().install()
            logger.info(f"Using chromedriver at: {chromedriver_path}")
            
            service = Service(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            
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
            
            logger.info("WebDriver successfully initialized")
            
        except Exception as e:
            logger.error(f"Error initializing WebDriver: {e}")
            
            # Try an alternative approach if the first one fails
            try:
                logger.info("Trying alternative WebDriver initialization approach")
                
                # Clean up the temporary directory
                if 'temp_dir' in locals():
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"Removed temporary directory: {temp_dir}")
                    except:
                        pass
                
                # Try with minimal options
                minimal_options = Options()
                minimal_options.add_argument('--no-sandbox')
                minimal_options.add_argument('--disable-dev-shm-usage')
                
                if self.bright_username and self.bright_password:
                    proxy_host = "brd.superproxy.io"
                    proxy_port = "22225"
                    proxy_username = f"{self.bright_username}-session-{random.randint(1000000, 9999999)}"
                    proxy_password = self.bright_password
                    bright_proxy = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
                    minimal_options.add_argument(f'--proxy-server={bright_proxy}')
                
                self.driver = webdriver.Chrome(options=minimal_options)
                logger.info("WebDriver initialized with minimal options")
                
            except Exception as e2:
                logger.error(f"Error with alternative WebDriver initialization: {e2}")
                raise Exception(f"Failed to initialize WebDriver: {e}, {e2}")
        
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
                By.XPATH, "//div[contains(@class, 'phone') or contains(@class, 'country')]//select"
            )
            
            if country_selectors:
                # If found, select the appropriate country code
                from selenium.webdriver.support.ui import Select
                select = Select(country_selectors[0])
                
                # Try to find the option with the country code
                options = select.options
                for option in options:
                    if country_code in option.text:
                        select.select_by_visible_text(option.text)
                        logger.info(f"Selected country code: {option.text}")
                        break
            
            # Find the phone input field
            phone_input = self._find_element_with_retry(
                By.XPATH, "//input[contains(@placeholder, 'phone') or contains(@type, 'tel')]"
            )
            
            if phone_input:
                # Clear and fill the phone number
                phone_input.clear()
                self._human_like_typing(phone_input, phone_digits)
            else:
                logger.warning("Could not find phone input field")
                
        except Exception as e:
            logger.error(f"Error filling phone number: {e}")
            # Continue with form filling even if phone number fails
    
    def _handle_cookie_dialogs(self) -> None:
        """Handle common cookie consent dialogs."""
        try:
            # Look for common cookie accept buttons
            cookie_buttons = self.driver.find_elements(
                By.XPATH, 
                """//button[
                    contains(text(), 'Accept') or 
                    contains(text(), 'I agree') or 
                    contains(text(), 'Got it') or
                    contains(text(), 'OK') or
                    contains(text(), 'Allow')
                ]"""
            )
            
            if cookie_buttons:
                logger.info("Found cookie consent dialog, attempting to accept")
                for button in cookie_buttons:
                    try:
                        button.click()
                        logger.info("Clicked cookie accept button")
                        time.sleep(1)
                        break
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Error handling cookie dialogs: {e}")
    
    def _human_like_typing(self, element, text: str) -> None:
        """
        Type text into an element with random delays to mimic human typing.
        
        Args:
            element: The web element to type into
            text: The text to type
        """
        for char in text:
            element.send_keys(char)
            # Random delay between keystrokes (50-200ms)
            time.sleep(random.uniform(0.05, 0.2))
    
    def _find_element_with_retry(self, by, value, max_retries=3):
        """
        Find an element with retries and error handling.
        
        Args:
            by: The locator strategy
            value: The locator value
            max_retries: Maximum number of retry attempts
            
        Returns:
            The found element or None if not found
        """
        for attempt in range(max_retries):
            try:
                element = self.driver.find_element(by, value)
                return element
            except NoSuchElementException:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
    
    def _take_screenshot(self, filename: str) -> None:
        """
        Take a screenshot for debugging purposes.
        
        Args:
            filename: Name of the screenshot file
        """
        try:
            # Create screenshots directory if it doesn't exist
            os.makedirs("screenshots", exist_ok=True)
            
            # Save the screenshot
            screenshot_path = os.path.join("screenshots", filename)
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.warning(f"Error taking screenshot: {e}")
    
    def _check_and_handle_recaptcha(self) -> Any:
        """
        Check for reCAPTCHA and handle it if present.
        
        Returns:
            Union[bool, str]: True if no reCAPTCHA or handled successfully, 
                             "restart_needed" if reCAPTCHA couldn't be solved, False otherwise
        """
        try:
            if self._recaptcha_is_present():
                logger.info("reCAPTCHA detected, attempting to handle")
                return self._handle_recaptcha()
            return True
        except Exception as e:
            logger.error(f"Error checking and handling reCAPTCHA: {e}")
            return False
    
    def _recaptcha_is_present(self) -> bool:
        """
        Check if reCAPTCHA is present on the page.
        
        Returns:
            bool: True if reCAPTCHA is present, False otherwise
        """
        try:
            # Check for reCAPTCHA iframe
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@title, 'reCAPTCHA')]"
            )
            if recaptcha_frames:
                logger.info("reCAPTCHA iframe detected")
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
        Handle reCAPTCHA if present on the page using Bright Data's CAPTCHA bypass.
        With Bright Data proxies, most CAPTCHAs should be automatically bypassed.
        
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
            
            # 1. First try direct checkbox click (should work with Bright Data)
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
            
            # If we're using Bright Data and still hit a CAPTCHA, try refreshing the page
            if self.bright_username and self.bright_password:
                logger.info("Refreshing page to try Bright Data CAPTCHA bypass again")
                self.driver.refresh()
                time.sleep(5)
                
                # Check if CAPTCHA is still present
                if not self._recaptcha_is_present():
                    logger.info("CAPTCHA no longer present after refresh")
                    return True
            
            # 2. If checkbox click failed and we have a 2Captcha API key, use it as fallback
            if self.captcha_api_key:
                logger.info("Using 2Captcha as fallback for CAPTCHA solving")
                
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
            
            # Method 3: Try to extract using JavaScript
            site_key = self.driver.execute_script("""
                try {
                    return document.querySelector('.g-recaptcha').getAttribute('data-sitekey') || 
                           document.querySelector('div[data-sitekey]').getAttribute('data-sitekey') || 
                           document.querySelector('iframe[src*="recaptcha"]').getAttribute('src').match(/[?&]k=([^&]+)/)[1];
                } catch(e) {
                    return null;
                }
            """)
            
            if site_key:
                logger.info(f"Extracted reCAPTCHA site key using JavaScript: {site_key}")
                return site_key
            
            logger.error("Could not extract reCAPTCHA site key")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting reCAPTCHA site key: {e}")
            return None
    
    def _solve_recaptcha_with_2captcha(self, site_key: str) -> Optional[str]:
        """
        Solve reCAPTCHA using 2Captcha service.
        
        Args:
            site_key: The reCAPTCHA site key
            
        Returns:
            Optional[str]: The reCAPTCHA token or None if failed
        """
        try:
            # Get the current URL
            page_url = self.driver.current_url
            
            # 2Captcha API key
            api_key = self.captcha_api_key
            
            # Step 1: Create a task to solve the reCAPTCHA
            logger.info("Creating 2Captcha task")
            create_task_url = "https://api.2captcha.com/createTask"
            create_task_payload = {
                "clientKey": api_key,
                "task": {
                    "type": "RecaptchaV2TaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    "isInvisible": False
                }
            }
            
            response = requests.post(create_task_url, json=create_task_payload)
            response_data = response.json()
            
            if response_data.get("errorId") > 0:
                logger.error(f"Error creating 2Captcha task: {response_data.get('errorDescription')}")
                return None
            
            task_id = response_data.get("taskId")
            if not task_id:
                logger.error("No task ID returned from 2Captcha")
                return None
            
            logger.info(f"2Captcha task created with ID: {task_id}")
            
            # Step 2: Wait for the task to be solved
            logger.info("Waiting for 2Captcha to solve reCAPTCHA")
            get_result_url = "https://api.2captcha.com/getTaskResult"
            get_result_payload = {
                "clientKey": api_key,
                "taskId": task_id
            }
            
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(5)  # Wait 5 seconds between checks
                
                response = requests.post(get_result_url, json=get_result_payload)
                result_data = response.json()
                
                if result_data.get("errorId") > 0:
                    logger.error(f"Error getting 2Captcha result: {result_data.get('errorDescription')}")
                    return None
                
                if result_data.get("status") == "ready":
                    token = result_data.get("solution", {}).get("gRecaptchaResponse")
                    if token:
                        logger.info("2Captcha successfully solved reCAPTCHA")
                        return token
                    else:
                        logger.error("No reCAPTCHA token in 2Captcha response")
                        return None
                
                logger.info(f"2Captcha task not ready yet, waiting... (attempt {attempt+1}/{max_attempts})")
            
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
            bool: True if token was injected successfully, False otherwise
        """
        try:
            logger.info("Injecting reCAPTCHA token")
            
            # Method 1: Try to find and fill the g-recaptcha-response textarea
            g_response_elements = self.driver.find_elements(By.NAME, "g-recaptcha-response")
            if g_response_elements:
                # Make the element visible
                self.driver.execute_script("""
                    document.getElementsByName('g-recaptcha-response').forEach(function(el) {
                        el.style.display = 'block';
                        el.style.height = '100px';
                    });
                """)
                
                # Set the value
                self.driver.execute_script(f"""
                    document.getElementsByName('g-recaptcha-response').forEach(function(el) {{
                        el.innerHTML = '{token}';
                        el.value = '{token}';
                    }});
                """)
                
                logger.info("Injected token into g-recaptcha-response element")
                return True
            
            # Method 2: Try to find reCAPTCHA iframes and inject the token
            recaptcha_frames = []
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                try:
                    src = frame.get_attribute("src")
                    if src and ("recaptcha" in src or "recaptcha" in frame.get_attribute("title", "")):
                        recaptcha_frames.append(frame)
                except:
                    continue
            
            if recaptcha_frames:
                # Inject token into the main document
                self.driver.execute_script(f"""
                    // Set token in the g-recaptcha-response textarea
                    if (document.querySelector('[name="g-recaptcha-response"]')) {{
                        document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
                        document.querySelector('[name="g-recaptcha-response"]').value = '{token}';
                    }}
                """)
                
                # Try to inject into each frame
                for frame in recaptcha_frames:
                    try:
                        self.driver.switch_to.frame(frame)
                        self.driver.execute_script(f"""
                            if (document.querySelector('[name="g-recaptcha-response"]')) {{
                                document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
                                document.querySelector('[name="g-recaptcha-response"]').value = '{token}';
                            }}
                        """)
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue
            
            # Method 3: Use a more comprehensive JavaScript approach
            self.driver.execute_script(f"""
                // Set token in the g-recaptcha-response textarea
                var responses = document.getElementsByName('g-recaptcha-response');
                for (var i = 0; i < responses.length; i++) {{
                    responses[i].innerHTML = '{token}';
                    responses[i].value = '{token}';
                }}
                
                // Try to trigger the callback function
                if (typeof(___grecaptcha_cfg) !== 'undefined') {{
                    try {{
                        var widgetIds = Object.keys(___grecaptcha_cfg.clients);
                        for (var i = 0; i < widgetIds.length; i++) {{
                            var client = ___grecaptcha_cfg.clients[widgetIds[i]];
                            var widgets = Object.keys(client);
                            for (var j = 0; j < widgets.length; j++) {{
                                if (typeof(client[widgets[j]].callback) === 'function') {{
                                    client[widgets[j]].callback('{token}');
                                }}
                            }}
                        }}
                    }} catch(e) {{
                        console.error('Error triggering reCAPTCHA callback:', e);
                    }}
                }}
                
                // Try to trigger data-callback attribute
                var captchaElements = document.querySelectorAll('[data-callback]');
                for (var i = 0; i < captchaElements.length; i++) {{
                    var callback = captchaElements[i].getAttribute('data-callback');
                    if (callback && typeof(window[callback]) === 'function') {{
                        try {{
                            window[callback]('{token}');
                        }} catch(e) {{
                            console.error('Error calling data-callback function:', e);
                        }}
                    }}
                }}
            """)
            
            logger.info("Injected reCAPTCHA token using JavaScript")
            return True
            
        except Exception as e:
            logger.error(f"Error injecting reCAPTCHA token: {e}")
            return False
    
    def close(self) -> None:
        """Close the WebDriver and release resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")

def book_calendly_meeting(url: str, form_data: Dict[str, Any], 
                          bright_username: Optional[str] = None, 
                          bright_password: Optional[str] = None,
                          headless: bool = False, 
                          captcha_api_key: Optional[str] = None,
                          max_retries: int = 3) -> bool:
    """
    Book a Calendly meeting using the provided URL and form data.
    
    Args:
        url: The Calendly booking URL
        form_data: Dictionary containing form field values
        bright_username: Bright Data username
        bright_password: Bright Data password
        headless: Whether to run Chrome in headless mode
        captcha_api_key: API key for 2Captcha service (optional, as Bright Data handles reCAPTCHA)
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if booking was successful, False otherwise
    """
    logger.info(f"Attempting to book Calendly meeting at {url}")
    
    # Log the Bright Data credentials status
    if bright_username and bright_password:
        logger.info(f"Using Bright Data credentials: {bright_username}")
    else:
        logger.warning("No Bright Data credentials provided, proceeding without proxy")
    
    # Log the captcha API key status
    if captcha_api_key:
        logger.info(f"Using 2Captcha API key: {captcha_api_key[:5]}...{captcha_api_key[-5:]}")
    
    for attempt in range(max_retries):
        logger.info(f"Booking attempt {attempt+1}/{max_retries}")
        
        scraper = CalendlyScraper(
            headless=headless,
            bright_username=bright_username,
            bright_password=bright_password,
            captcha_api_key=captcha_api_key
        )
        
        try:
            # Set up the WebDriver
            scraper.setup_driver()
            
            # Navigate to the Calendly URL
            if not scraper.navigate_to_url(url):
                logger.error("Failed to navigate to Calendly URL")
                scraper.close()
                continue
            
            # Fill out the form
            if not scraper.fill_form(form_data):
                logger.error("Failed to fill out form")
                scraper.close()
                continue
            
            # Submit the form and handle any reCAPTCHA
            submit_result = scraper.submit_form()
            
            if submit_result == "restart_needed":
                logger.warning("reCAPTCHA detected, restarting with new session")
                scraper.close()
                continue
            elif submit_result is True:
                logger.info("Successfully booked Calendly meeting!")
                scraper.close()
                return True
            else:
                logger.error("Failed to submit form")
                scraper.close()
                continue
                
        except Exception as e:
            logger.error(f"Error during booking attempt: {e}")
            scraper.close()
            continue
    
    logger.error(f"Failed to book Calendly meeting after {max_retries} attempts")
    return False

def main():
    """Main function to parse arguments and run the scraper."""
    parser = argparse.ArgumentParser(description='Calendly Booking Form Scraper')
    
    # Required arguments
    parser.add_argument('--url', help='Calendly booking URL')
    
    # Form data arguments
    parser.add_argument('--name', required=True, help='Name to use for booking')
    parser.add_argument('--email', required=True, help='Email to use for booking')
    parser.add_argument('--phone', help='Phone number to use for booking')
    parser.add_argument('--additional-info', help='Additional information for booking')
    
    # Bright Data credentials
    bright_username = os.getenv('BRIGHT_USERNAME', 'hl_3b9ca4fa')
    bright_password = os.getenv('BRIGHT_PASSWORD', 'ga8f1xepto43')
    
    parser.add_argument('--bright-username', default=bright_username, 
                        help='Bright Data username')
    parser.add_argument('--bright-password', default=bright_password, 
                        help='Bright Data password')
    
    # Optional arguments
    parser.add_argument('--headless', action='store_true', help='Run Chrome in headless mode')
    
    # 2Captcha API key (as fallback)
    captcha_api_key = os.getenv('CAPTCHA_API_KEY')
    parser.add_argument('--captcha-api-key', default=captcha_api_key, 
                        help='2Captcha API key (optional, as Bright Data handles reCAPTCHA)')
    
    parser.add_argument('--max-retries', type=int, default=3, 
                        help='Maximum number of retry attempts')
    
    args = parser.parse_args()
    
    # Prepare form data
    form_data = {
        'name': args.name,
        'email': args.email
    }
    
    if args.phone:
        form_data['phone'] = args.phone
    
    if args.additional_info:
        form_data['additional_info'] = args.additional_info
    
    # Book the meeting
    success = book_calendly_meeting(
        url=args.url,
        form_data=form_data,
        bright_username=args.bright_username,
        bright_password=args.bright_password,
        headless=args.headless,
        captcha_api_key=args.captcha_api_key,
        max_retries=args.max_retries
    )
    
    if success:
        logger.info("Calendly meeting booked successfully!")
        sys.exit(0)
    else:
        logger.error("Failed to book Calendly meeting")
        sys.exit(1)

if __name__ == '__main__':
    main()
