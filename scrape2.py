#!/usr/bin/env python3
"""
Enhanced Calendly Booking Form Scraper with 2Captcha Integration

This script automates filling out Calendly booking forms, handling reCAPTCHA challenges
using 2Captcha service, and automatically closes when the booking is confirmed.
"""

import time
import random
import argparse
import logging
import sys
import os
import re
from typing import Dict, Any, Optional, List, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from browserbase import Browserbase
from selenium.webdriver.remote.remote_connection import RemoteConnection
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from twocaptcha import TwoCaptcha
from selenium.webdriver.chrome.service import Service

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

# Add this custom connection class for Browserbase
class CustomRemoteConnection(RemoteConnection):
    def __init__(self, remote_server_addr: str, signing_key: str):
        super().__init__(remote_server_addr)
        self._signing_key = signing_key

    def get_remote_connection_headers(self, parsed_url, keep_alive=False):
        headers = super().get_remote_connection_headers(parsed_url, keep_alive)
        headers.update({'x-bb-signing-key': self._signing_key})
        return headers

class CalendlyScraper:
    """Class to handle Calendly form filling and submission with Browserbase integration."""
    
    def __init__(self, headless: bool = False, proxy: Optional[str] = None, captcha_api_key: Optional[str] = None,
                 browserbase_api_key: Optional[str] = None, browserbase_project_id: Optional[str] = None):
        """
        Initialize the Calendly scraper.
        
        Args:
            headless: Whether to run Chrome in headless mode
            proxy: Optional proxy server to use
            captcha_api_key: API key for 2Captcha service
            browserbase_api_key: API key for Browserbase
            browserbase_project_id: Project ID for Browserbase
        """
        self.headless = headless
        self.proxy = proxy
        self.captcha_api_key = captcha_api_key
        self.browserbase_api_key = browserbase_api_key
        self.browserbase_project_id = browserbase_project_id
        self.driver = None
        self.wait_time = 10  # Default wait time in seconds
        self.bb_session = None
        
        # Initialize 2Captcha solver if API key is provided and we're not using Browserbase
        self.solver = None
        if self.captcha_api_key and not self.browserbase_api_key:
            self.solver = TwoCaptcha(self.captcha_api_key)
        
    def setup_driver(self) -> None:
        """Set up the WebDriver with Browserbase if available, otherwise use standard Selenium setup."""
        if self.browserbase_api_key and self.browserbase_project_id:
            logger.info("Setting up WebDriver with Browserbase")
            try:
                # Initialize Browserbase client
                bb = Browserbase(api_key=self.browserbase_api_key)
                
                # Create a new browser session with advanced settings
                self.bb_session = bb.sessions.create(
                    project_id=self.browserbase_project_id,
                    browser_settings={
                        'fingerprint': {
                            'browsers': ['chrome', 'firefox', 'edge', 'safari'],
                            'devices': ['desktop', 'mobile'],
                            'locales': ['en-US', 'en-GB'],
                            'operatingSystems': ['android', 'ios', 'linux', 'macos', 'windows'],
                            'screen': {
                                'maxWidth': 1920,
                                'maxHeight': 1080,
                                'minWidth': 1024,
                                'minHeight': 768,
                            }
                        },
                        'viewport': {
                            'width': 1366,
                            'height': 768,
                        },
                        'solveCaptchas': True,  # Enable automatic CAPTCHA solving
                    },
                    proxies=True if self.proxy else False,  # Enable proxy usage if requested
                )
                
                # Use the updated remote connection approach
                custom_conn = CustomRemoteConnection(
                    self.bb_session.selenium_remote_url, 
                    self.bb_session.signing_key
                )
                options = webdriver.ChromeOptions()
                self.driver = webdriver.Remote(custom_conn, options=options)
                
                logger.info(f"Successfully set up Browserbase WebDriver")
            except Exception as e:
                logger.error(f"Error setting up Browserbase: {e}")
                logger.info("Falling back to standard WebDriver setup")
                self._setup_standard_driver()
        else:
            # Use the standard WebDriver setup
            self._setup_standard_driver()
    
    def _setup_standard_driver(self) -> None:
        """Set up a standard Chrome WebDriver with anti-detection measures."""
        options = Options()
        
        # Rotate user agent to avoid detection
        ua = UserAgent()
        user_agent = ua.random
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
            
            # Add a random delay to simulate human behavior
            
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
        Submit the Calendly form and handle any reCAPTCHA challenges using 2Captcha.
        
        Returns:
            bool: True if form was submitted successfully, False otherwise
        """
        try:
            logger.info("Attempting to submit form")
            
            # Find and click the Schedule Event button
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
            
            # Add a random delay before clicking to simulate human behavior
            
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
            if self._handle_recaptcha_with_2captcha():
                logger.info("reCAPTCHA handled successfully")
            
            # Wait for confirmation page or error message
            try:
                # Wait for the confirmation page to appear
                success = self._wait_for_confirmation_page()
                if success:
                    logger.info("Form submitted successfully and confirmation page detected")
                    self._take_screenshot("submission_success.png")
                    return True
                else:
                    logger.warning("Could not confirm successful submission")
                    self._take_screenshot("submission_timeout.png")
                    
                    # Check for error messages
                    error_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'error')]")
                    if error_elements:
                        for error in error_elements:
                            logger.error(f"Form error: {error.text}")
                    
                    return False
            except TimeoutException:
                logger.warning("Timeout waiting for confirmation page")
                self._take_screenshot("submission_timeout.png")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            self._take_screenshot("submission_error.png")
            return False
    
    def _wait_for_confirmation_page(self, timeout: int = 30) -> bool:
        """
        Wait for the confirmation page to appear after form submission.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if confirmation page was detected, False otherwise
        """
        try:
            logger.info("Waiting for confirmation page...")
            
            # Wait for the "You are scheduled" text to appear
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'You are scheduled')]"))
            )
            
            logger.info("Confirmation page detected")
            return True
        except TimeoutException:
            # Try alternative confirmation indicators
            try:
                # Check for calendar invitation text
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'calendar invitation')]"))
                )
                logger.info("Confirmation page detected (calendar invitation)")
                return True
            except TimeoutException:
                # Check for URL containing "confirmed" or "success"
                if "confirmed" in self.driver.current_url or "success" in self.driver.current_url:
                    logger.info("Confirmation page detected (URL)")
                    return True
                
                logger.warning("Could not detect confirmation page")
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
            
            # Move mouse away from the field after typing
            ActionChains(self.driver).move_by_offset(random.randint(50, 100), random.randint(50, 100)).perform()
            
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
            
            # Move mouse away from the field after typing
            ActionChains(self.driver).move_by_offset(random.randint(50, 100), random.randint(50, 100)).perform()
            
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
    
    def _handle_recaptcha_with_2captcha(self) -> bool:
        """
        Handle reCAPTCHA using 2Captcha service or Browserbase's built-in solver.
        
        Returns:
            bool: True if reCAPTCHA was handled successfully or not present, False otherwise
        """
        # If using Browserbase with captcha solving enabled, skip manual captcha solving
        if self.browserbase_api_key and self.bb_session:
            logger.info("Using Browserbase's built-in CAPTCHA solver")
            # Wait a bit for Browserbase to solve any CAPTCHA
            return True
            
        # Otherwise, use the original 2Captcha solving logic
        try:
            # Check if reCAPTCHA iframe exists
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, "//iframe[contains(@src, 'recaptcha')]"
            )
            
            if not recaptcha_frames:
                logger.info("No visible reCAPTCHA detected")
                return True
            
            logger.info("reCAPTCHA detected, attempting to handle with 2Captcha")
            self._take_screenshot("recaptcha_detected.png")
            
            # Check if we have a 2Captcha solver
            if not self.solver:
                logger.error("2Captcha solver not initialized. Please provide a valid API key.")
                return False
            
            # Get the site key from the page
            site_key = self._extract_recaptcha_site_key()
            if not site_key:
                logger.error("Could not extract reCAPTCHA site key")
                return False
            
            logger.info(f"Found reCAPTCHA site key: {site_key}")
            
            # Get the page URL
            page_url = self.driver.current_url
            
            # Send the reCAPTCHA to 2Captcha for solving
            logger.info("Sending reCAPTCHA to 2Captcha for solving...")
            try:
                result = self.solver.recaptcha(
                    sitekey=site_key,
                    url=page_url
                )
                
                # Get the solution token
                token = result.get('code')
                logger.info("Received solution from 2Captcha")
                
                # Apply the solution token to the page
                self._apply_recaptcha_token(token)
                
                # Wait for the reCAPTCHA to be verified
                
                return True
                
            except Exception as e:
                logger.error(f"Error solving reCAPTCHA with 2Captcha: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error handling reCAPTCHA: {e}")
            self._take_screenshot("recaptcha_error.png")
            return False
    
    def _extract_recaptcha_site_key(self) -> Optional[str]:
        """
        Extract the reCAPTCHA site key from the page.
        
        Returns:
            str: The reCAPTCHA site key, or None if not found
        """
        try:
            # Method 1: Look for the site key in the reCAPTCHA iframe src
            recaptcha_frames = self.driver.find_elements(
                By.XPATH, "//iframe[contains(@src, 'recaptcha')]"
            )
            
            if recaptcha_frames:
                for frame in recaptcha_frames:
                    src = frame.get_attribute('src')
                    if src:
                        # Extract site key from the iframe src
                        match = re.search(r'k=([^&]+)', src)
                        if match:
                            return match.group(1)
            
            # Method 2: Look for the site key in the div data-sitekey attribute
            recaptcha_divs = self.driver.find_elements(
                By.XPATH, "//div[@data-sitekey]"
            )
            
            if recaptcha_divs:
                for div in recaptcha_divs:
                    site_key = div.get_attribute('data-sitekey')
                    if site_key:
                        return site_key
            
            # Method 3: Look for the site key in the page source
            page_source = self.driver.page_source
            match = re.search(r'data-sitekey="([^"]+)"', page_source)
            if match:
                return match.group(1)
            
            # Method 4: Execute JavaScript to find the site key
            site_key = self.driver.execute_script("""
                return document.querySelector('.g-recaptcha').getAttribute('data-sitekey') ||
                       document.querySelector('div[data-sitekey]').getAttribute('data-sitekey') ||
                       document.querySelector('iframe[src*="recaptcha"]').getAttribute('src').match(/k=([^&]+)/)[1];
            """)
            
            if site_key:
                return site_key
            
            logger.warning("Could not extract reCAPTCHA site key using any method")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting reCAPTCHA site key: {e}")
            return None
    
    def _apply_recaptcha_token(self, token: str) -> None:
        """
        Apply the reCAPTCHA solution token to the page.
        
        Args:
            token: The reCAPTCHA solution token from 2Captcha
        """
        try:
            # Execute JavaScript to set the reCAPTCHA response
            self.driver.execute_script(f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                
                // For invisible reCAPTCHA
                if (typeof ___grecaptcha_cfg !== 'undefined') {{
                    // Find the right key
                    Object.keys(___grecaptcha_cfg.clients).forEach(function(key) {{
                        // Set the response token
                        const target = document.getElementsByClassName('g-recaptcha')[0];
                        if (target) {{
                            const widgetId = target.getAttribute('data-widget-id');
                            if (widgetId) {{
                                grecaptcha.enterprise.getResponse = function(w) {{ return '{token}'; }};
                                grecaptcha.getResponse = function(w) {{ return '{token}'; }};
                            }}
                        }}
                    }});
                }}
                
                // Trigger the callback
                if (typeof ___grecaptcha_cfg !== 'undefined') {{
                    setTimeout(function() {{
                        try {{
                            Object.keys(___grecaptcha_cfg.clients).forEach(function(key) {{
                                const client = ___grecaptcha_cfg.clients[key];
                                Object.keys(client).forEach(function(idx) {{
                                    if (typeof client[idx].callback === 'function') {{
                                        client[idx].callback('{token}');
                                    }}
                                }});
                            }});
                        }} catch (e) {{
                            console.error('Error triggering reCAPTCHA callback:', e);
                        }}
                    }}, 500);
                }}
            """)
            
            logger.info("Applied reCAPTCHA solution token to the page")
            
        except Exception as e:
            logger.error(f"Error applying reCAPTCHA token: {e}")
            raise
    
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
        Type text into an element with random delays to simulate human typing.
        
        Args:
            element: The web element to type into
            text: The text to type
        """
        for char in text:
            element.send_keys(char)
            # Random delay between keystrokes (30-100ms)
            
            # Occasionally add a longer pause (1% chance)
       
  
    
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
            
        # Browserbase session is automatically closed when the driver quits,
        # so we don't need to explicitly destroy the session
        self.bb_session = None


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
    parser.add_argument('--captcha-api-key', default='36483071b9fe06d051d4b66f3beca836', 
                        help='API key for 2Captcha service (default: provided key)')
    parser.add_argument('--browserbase-api-key', default=os.getenv('BROWSERBASE_API_KEY'), help='API key for Browserbase')
    parser.add_argument('--browserbase-project-id', default=os.getenv('BROWSERBASE_PROJECT_ID'), help='Project ID for Browserbase')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create form data dictionary
    form_data = {
        'name': args.name,
        'email': args.email,
        'phone': args.phone
    }
    
    if args.info:
        form_data['additional_info'] = args.info
    
    # Initialize the scraper
    scraper = CalendlyScraper(
        headless=args.headless, 
        proxy=args.proxy,
        captcha_api_key=args.captcha_api_key,
        browserbase_api_key=args.browserbase_api_key,
        browserbase_project_id=args.browserbase_project_id
    )
    
    try:
        # Set up the WebDriver
        scraper.setup_driver()
        
        # Navigate to the Calendly URL
        if not scraper.navigate_to_url(args.url):
            logger.error("Failed to navigate to the Calendly URL")
            return 1
        
        # Fill out the form
        if not scraper.fill_form(form_data):
            logger.error("Failed to fill out the form")
            return 1
        
        # Submit the form
        if scraper.submit_form():
            logger.info("Successfully submitted the Calendly booking form")
            # Wait a moment to ensure the confirmation page is fully loaded
            time.sleep(3)  # Add a short delay to view the confirmation
            logger.info("Closing browser after successful submission")
            scraper.close()  # Explicitly close the browser after success
            return 0
        else:
            logger.error("Failed to submit the form")
            return 1
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1
    
    finally:
        # Clean up
        scraper.close()


if __name__ == "__main__":
    sys.exit(main())
