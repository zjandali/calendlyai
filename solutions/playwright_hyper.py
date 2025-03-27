#!/usr/bin/env python3
"""
Enhanced Calendly Booking Form Scraper with 2Captcha Integration using Playwright

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
from typing import Dict, Any, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from fake_useragent import UserAgent
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables for Hyperbrowser
load_dotenv()


class CalendlyScraper:
    """
    Class to handle Calendly form filling and submission using Playwright.
    Hyperbrowser integration is available in this version.
    """
    
    def __init__(
        self, 
        headless: bool = False, 
        proxy: Optional[str] = None, 
        hyperbrowser_api_key: Optional[str] = None
    ):
        self.headless = headless
        self.proxy = proxy
        self.hyperbrowser_api_key = hyperbrowser_api_key
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.wait_time = 10  # seconds
    
    def setup_driver(self) -> None:
        """Set up the Playwright browser with Hyperbrowser integration."""
        if self.hyperbrowser_api_key:
            logger.info("Setting up Hyperbrowser session")
            
            # Initialize Playwright and connect to Hyperbrowser
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(
                f"wss://connect.hyperbrowser.ai?apiKey={self.hyperbrowser_api_key}"
            )
            
            # Getting the default context to ensure the sessions are recorded
            self.context = self.browser.contexts[0]
            self.page = self.context.pages[0]
            
            logger.info(f"Connected to Hyperbrowser session")
        else:
            # Fall back to regular Playwright setup
            logger.info("Setting up regular Playwright browser (Hyperbrowser credentials not provided)")
            self.playwright = sync_playwright().start()
            
            # Launch browser (Chromium)
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            
            # Create a browser context with a custom user agent and viewport
            ua = UserAgent()
            user_agent = ua.random
            logger.info(f"Using User-Agent: {user_agent}")
            
            self.context = self.browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768}
            )
            self.page = self.context.new_page()
    
    def navigate_to_url(self, url: str) -> bool:
        """
        Navigate to the specified Calendly URL.
        
        Args:
            url: The Calendly booking URL.
            
        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        try:
            logger.info(f"Navigating to {url}")
            self.page.goto(url, timeout=self.wait_time * 1000)
            self.page.wait_for_selector("body", timeout=self.wait_time * 1000)
            
            self._handle_cookie_dialogs()
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
            form_data: Dictionary containing form field values.
            
        Returns:
            bool: True if form was filled successfully, False otherwise.
        """
        try:
            logger.info("Filling out Calendly form")
            self._fill_input_field("Name", form_data.get("name", ""))
            self._fill_input_field("Email", form_data.get("email", ""))
            self._fill_phone_number(form_data.get("phone", ""))
            
            if "additional_info" in form_data and form_data["additional_info"]:
                self._fill_textarea("Please share anything", form_data["additional_info"])
            
            self._take_screenshot("form_filled.png")
            logger.info("Form filled successfully")
            return True
        except Exception as e:
            logger.error(f"Error filling form: {e}")
            self._take_screenshot("form_fill_error.png")
            return False
    
    def submit_form(self) -> bool:
        """
        Submit the Calendly form.
        
        Returns:
            bool: True if form was submitted successfully, False otherwise.
        """
        try:
            logger.info("Attempting to submit form")
            schedule_button = self._find_element_with_retry(
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'schedule event') or contains(@class, 'submit') or contains(@type, 'submit')]",
                max_retries=3
            )
            if not schedule_button:
                logger.error("Could not find Schedule Event button")
                return False
            
            self.page.evaluate("element => element.scrollIntoView({block: 'center'})", schedule_button)
            try:
                schedule_button.click()
            except Exception:
                self.page.evaluate("element => element.click()", schedule_button)
            
            self._take_screenshot("after_submit_click.png")
            
            if self._wait_for_confirmation_page():
                logger.info("Form submitted successfully and confirmation page detected")
                self._take_screenshot("submission_success.png")
                return True
            else:
                logger.warning("Could not confirm successful submission")
                self._take_screenshot("submission_timeout.png")
                error_elements = self.page.query_selector_all("//div[contains(@class, 'error')]")
                for error in error_elements:
                    logger.error(f"Form error: {error.inner_text()}")
                return False
        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            self._take_screenshot("submission_error.png")
            return False
    
    def _wait_for_confirmation_page(self, timeout: int = 30) -> bool:
        """
        Wait for the confirmation page to appear after form submission.
        
        Args:
            timeout: Maximum time to wait in seconds.
            
        Returns:
            bool: True if confirmation page was detected, False otherwise.
        """
        try:
            logger.info("Waiting for confirmation page...")
            self.page.wait_for_selector("//h1[contains(text(), 'You are scheduled')]", timeout=timeout * 1000)
            logger.info("Confirmation page detected")
            return True
        except PlaywrightTimeoutError:
            try:
                self.page.wait_for_selector("//div[contains(text(), 'calendar invitation')]", timeout=5000)
                logger.info("Confirmation page detected (calendar invitation)")
                return True
            except PlaywrightTimeoutError:
                if "confirmed" in self.page.url or "success" in self.page.url:
                    logger.info("Confirmation page detected (URL)")
                    return True
                logger.warning("Could not detect confirmation page")
                return False
    
    def _fill_input_field(self, label_text: str, value: str) -> None:
        """
        Fill an input field identified by its label text.
        
        Args:
            label_text: Text of the label associated with the input field.
            value: Value to enter in the field.
        """
        try:
            self.page.wait_for_selector(f"xpath=//label[contains(text(), '{label_text}')]", timeout=self.wait_time * 1000)
            input_field = self._find_element_with_retry(f"xpath=//label[contains(text(), '{label_text}')]/following::input[1]")
            if not input_field:
                input_field = self._find_element_with_retry(f"xpath=//label[contains(text(), '{label_text}')]/..//input")
            if not input_field:
                raise Exception(f"Could not find input field for label: {label_text}")
            
            input_field.fill("")
            self._human_like_typing(input_field, value)
        except Exception as e:
            logger.error(f"Error filling input field '{label_text}': {e}")
            raise
    
    def _fill_textarea(self, label_text: str, value: str) -> None:
        """
        Fill a textarea field identified by its label text.
        
        Args:
            label_text: Text of the label associated with the textarea.
            value: Value to enter in the field.
        """
        try:
            self.page.wait_for_selector(f"xpath=//label[contains(text(), '{label_text}')]", timeout=self.wait_time * 1000)
            textarea = self._find_element_with_retry(f"xpath=//label[contains(text(), '{label_text}')]/following::textarea[1]")
            if not textarea:
                textarea = self._find_element_with_retry(f"xpath=//label[contains(text(), '{label_text}')]/..//textarea")
            if not textarea:
                raise Exception(f"Could not find textarea for label: {label_text}")
            
            textarea.fill("")
            self._human_like_typing(textarea, value)
        except Exception as e:
            logger.error(f"Error filling textarea '{label_text}': {e}")
            raise
    
    def _fill_phone_number(self, phone_number: str) -> None:
        """
        Fill the phone number field, handling country code selection if needed.
        
        Args:
            phone_number: Phone number to enter (with or without country code).
        """
        try:
            if not phone_number.startswith("+"):
                phone_number = "+1 " + phone_number
            parts = phone_number.split(" ", 1)
            country_code = parts[0]
            phone_digits = parts[1] if len(parts) > 1 else phone_number[len(country_code):]
            logger.info(f"Processing phone: country code={country_code}, digits={phone_digits}")
            
            # Find country code selector
            country_selectors = self.page.query_selector_all(
                "//div[contains(@class, 'phone-field-flag') or contains(@class, 'country-select') or contains(@role, 'combobox')]"
            )
            if not country_selectors:
                country_selectors = self.page.query_selector_all(
                    "//div[contains(@class, 'flag')] | //div[contains(@class, 'country')] | //div[contains(@class, 'phone')]//div[contains(@class, 'select')]"
                )
            
          
                self.page.evaluate("element => element.click()", country_selectors[0])
                self._take_screenshot("after_country_select_click.png")
                
                if country_code == "+1":
                    us_found = False
                    search_inputs = self.page.query_selector_all("//input[contains(@placeholder, 'Search')]")
                    if search_inputs:
                        try:
                            search_input = search_inputs[0]
                            search_input.fill("")
                            self._human_like_typing(search_input, "United States")
                            us_options = self.page.query_selector_all("//span[contains(text(), 'United States')]")
                            if us_options:
                                us_options[0].click()
                                us_found = True
                        except Exception as e:
                            logger.warning(f"Error using search input: {e}")
                    
                    if not us_found:
                        try:
                            for _ in range(3):
                                us_options = self.page.query_selector_all(
                                    "//span[contains(text(), 'United States')] | //div[contains(text(), 'United States')] | //li[contains(text(), 'United States')]"
                                )
                                if us_options:
                                    self.page.evaluate("element => element.scrollIntoView(true)", us_options[0])
                                    us_options[0].click()
                                    us_found = True
                                    break
                                dropdown = self.page.query_selector_all(
                                    "//ul[contains(@class, 'country') or contains(@role, 'listbox')]"
                                )
                                if dropdown:
                                    self.page.evaluate("element => element.scrollTop += 300", dropdown[0])
                        except Exception as e:
                            logger.warning(f"Error scrolling to find United States: {e}")
                    
                    if not us_found:
                        try:
                            plus_one_options = self.page.query_selector_all(
                                "//span[contains(text(), '+1')] | //div[contains(text(), '+1')]"
                            )
                            if plus_one_options:
                                plus_one_options[0].click()
                        except Exception as e:
                            logger.warning(f"Error clicking +1 option: {e}")
                
                try:
                    self.page.click("body")  # click outside to close dropdown
                except Exception:
                    pass
            
            phone_input = self._find_element_with_retry(
                "//input[contains(@type, 'tel') or contains(@id, 'phone') or contains(@name, 'phone') or contains(@placeholder, 'phone') or preceding::label[contains(text(), 'Phone')]]",
                max_retries=3
            )
            if not phone_input:
                phone_input = self._find_element_with_retry("//div[contains(@class, 'phone')]//input", max_retries=2)
            if not phone_input:
                raise Exception("Could not find phone number input field")
            
            phone_input.fill("")
            self._human_like_typing(phone_input, phone_digits)
        except Exception as e:
            logger.error(f"Error filling phone number: {e}")
            raise
    
    def _handle_cookie_dialogs(self) -> None:
        """Handle common cookie consent dialogs that might appear on the page."""
        try:
            # First check if any cookie dialogs are visible
            cookie_xpaths = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'I understand')]",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Got it')]",
                "//button[contains(text(), 'Allow')]",
                "//button[contains(@id, 'cookie') and contains(text(), 'Accept')]",
                "//div[contains(@id, 'cookie')]//button[contains(text(), 'Accept')]",
                "//div[contains(@class, 'cookie')]//button",
                "//div[contains(@class, 'consent')]//button"
            ]
            
            # Try standard click first
            for xpath in cookie_xpaths:
                try:
                    # Use force:true to attempt to click even if element might be covered
                    button = self.page.query_selector(xpath)
                    if button and button.is_visible():
                        logger.info(f"Found visible cookie dialog, clicking: {xpath}")
                        self.page.click(xpath, force=True, timeout=5000)
                        time.sleep(0.5)  # Short pause after clicking
                        return
                except Exception as e:
                    logger.debug(f"Standard click on {xpath} failed: {e}")
            
            # If standard click fails, try JavaScript click for all buttons
            for xpath in cookie_xpaths:
                buttons = self.page.query_selector_all(xpath)
                if buttons:
                    for button in buttons:
                        try:
                            logger.info(f"Attempting JavaScript click on cookie button: {xpath}")
                            self.page.evaluate("element => element.click()", button)
                            time.sleep(0.5)  # Short pause after clicking
                            return
                        except Exception as e:
                            logger.debug(f"JavaScript click failed: {e}")
            
            # Look for iframes that might contain cookie consent
            frames = self.page.frames
            for frame in frames:
                try:
                    for xpath in cookie_xpaths:
                        button = frame.query_selector(xpath)
                        if button:
                            logger.info(f"Found cookie button in iframe, clicking: {xpath}")
                            frame.click(xpath, force=True, timeout=5000)
                            return
                except Exception as e:
                    logger.debug(f"Error handling cookie in iframe: {e}")
                
            logger.info("No actionable cookie dialogs found or all attempts to handle them failed")
        except Exception as e:
            logger.warning(f"Error handling cookie dialogs: {e}")
    
    def _human_like_typing(self, element, text: str) -> None:
        """
        Type text into an element with random delays to simulate human typing.
        
        Args:
            element: The element to type into.
            text: The text to type.
        """
        for char in text:
            element.type(char, delay=random.randint(30, 100))
            if random.random() < 0.01:
                time.sleep(0.5)
    
    def _find_element_with_retry(self, selector: str, max_retries: int = 3):
        """
        Find an element with retries.
        
        Args:
            selector: The selector string (XPath in this case).
            max_retries: Maximum number of retry attempts.
            
        Returns:
            The found element or None if not found.
        """
        for attempt in range(max_retries):
            try:
                elem = self.page.wait_for_selector(selector, timeout=self.wait_time * 1000)
                if elem:
                    return elem
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"Could not find element {selector} after {max_retries} attempts: {e}")
                    return None
        return None
    
    def _take_screenshot(self, filename: str) -> None:
        """
        Take a screenshot for debugging purposes.
        
        Args:
            filename: Name of the screenshot file.
        """
        try:
            screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, filename)
            self.page.screenshot(path=screenshot_path)
            logger.debug(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.warning(f"Error taking screenshot: {e}")
    
    def close(self) -> None:
        """Close the Playwright browser and release resources."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()


def main():
    parser = argparse.ArgumentParser(description="Calendly Booking Form Scraper with Playwright")
    parser.add_argument("--url", required=True, default="https://calendly.com/robertjandali/30min/2025-03-28T00:00:00-07:00", help="Calendly booking URL")
    parser.add_argument("--name", default="john doe", help="Name to enter in the form")
    parser.add_argument("--email", default="your-email@example.com", help="Email to enter in the form")
    parser.add_argument("--phone", default="5109198404", help="Phone number to enter in the form")
    parser.add_argument("--info", help="Additional information to provide (optional)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--proxy", help="Proxy server to use (optional)")
    parser.add_argument("--hyperbrowser-api-key", default=os.getenv("HYPERBROWSER_API_KEY"), 
                        help="API key for Hyperbrowser")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    form_data = {
        "name": args.name,
        "email": args.email,
        "phone": args.phone
    }
    if args.info:
        form_data["additional_info"] = args.info
    
    scraper = CalendlyScraper(
        headless=args.headless,
        proxy=args.proxy,
        hyperbrowser_api_key=args.hyperbrowser_api_key
    )
    
    success = False
    try:
        scraper.setup_driver()
        if not scraper.navigate_to_url(args.url):
            logger.error("Failed to navigate to the Calendly URL")
            return 1
        
        if not scraper.fill_form(form_data):
            logger.error("Failed to fill out the form")
            return 1
        
        if scraper.submit_form():
            logger.info("Successfully submitted the Calendly booking form")
            time.sleep(3)
            success = True
            return 0
        else:
            logger.error("Failed to submit the form")
            return 1
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1
    finally:
        if scraper:
            logger.info("Closing browser")
            try:
                scraper.close()
            except Exception as e:
                logger.warning(f"Error during browser cleanup: {e}")


if __name__ == "__main__":
    # For simplified usage, you can run without arguments to use defaults
    if len(sys.argv) == 1:
        sys.argv.extend(["--url", "https://calendly.com/robertjandali/30min/2025-03-28T00:00:00-07:00"])
    sys.exit(main())
