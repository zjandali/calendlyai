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
    logger.info(f"Setting up Calendly API for URL: {calendly_url}")
    
    try:
        url_parts = calendly_url.split('/')
        profile_slug = url_parts[-2]
        event_type_slug = url_parts[-1].split('?')[0]
        
        id_url = f"https://calendly.com/api/booking/event_types/lookup?event_type_slug={event_type_slug}&profile_slug={profile_slug}"
        
        logger.debug(f"Making request to: {id_url}")
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

def get_calendly_availability(uuid: str, timezone: str = "America/Los_Angeles") -> dict:
    """
    Get availability data from Calendly
    """
    logger.info("Fetching Calendly availability")
    
    try:
        range_url = f"https://calendly.com/api/booking/event_types/{uuid}/calendar/range"
        start_date = datetime.now()
        end_date = start_date + timedelta(days=35)
        
        params = {
            "timezone": timezone,
            "diagnostics": "false",
            "range_start": start_date.strftime("%Y-%m-%d"),
            "range_end": end_date.strftime("%Y-%m-%d")
        }
        
        logger.debug(f"Making request to: {range_url} with params: {params}")
        calendar_response = requests.get(range_url, params=params)
        calendar_response.raise_for_status()
        
        calendly_data = calendar_response.json()
        calendly_formatted = format_calendar_data(calendly_data)
        
        logger.info("Successfully retrieved and formatted Calendly availability")
        logger.debug(f"Formatted Calendly data: {pformat(calendly_formatted)}")
        
        return calendly_formatted
        
    except Exception as e:
        logger.error(f"Error getting Calendly availability: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def get_suggested_time(overlapping_calendar: dict) -> str:
    """
    Get suggested meeting time from LLM
    """
    logger.info("Getting suggested meeting time from LLM")
    
    try:
        response_schema = ResponseSchema(
            name="suggested_time",
            description="The suggested meeting time in ISO 8601 format",
            type="string"
        )
        
        parser = StructuredOutputParser.from_response_schemas([response_schema])
        format_instructions = parser.get_format_instructions()
        
        prompt_template = scheduling_prompt()
        messages = prompt_template.format_messages(
            overlapping_availability=json.dumps(overlapping_calendar, indent=2),
            format_instructions=format_instructions
        )
        
        llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        logger.debug("Sending prompt to LLM")
        response = llm.invoke(messages)
        parsed_response = parser.parse(response.content)
        suggested_time = parsed_response['suggested_time']
        
        logger.info(f"LLM suggested time: {suggested_time}")
        return suggested_time
        
    except Exception as e:
        logger.error(f"Error getting suggested time from LLM: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        logger.info(f"Mock calendar data: {pformat(mock_calendar)}")
        logger.debug(f"Mock calendar data: {pformat(mock_calendar)}")
        
        # Set up Calendly API and get availability
        uuid, profile_slug, event_type_slug = setup_calendly_api(calendly_url)
        calendly_formatted = get_calendly_availability(uuid)
        
        # Convert calendars to unified format
        logger.info("Converting calendars to unified format")
        calendly_timezone = calendly_formatted.get("timezone", "America/Los_Angeles")
        unified_mock = convert_to_unified_format(mock_calendar, 'mock', calendly_timezone)
        logger.info(f"Unified mock calendar: {pformat(unified_mock)}")
        unified_calendly = convert_to_unified_format(calendly_formatted, 'calendly')
        
        # Find overlapping times
        logger.info("Finding overlapping availability")
        overlapping_calendar = find_overlapping_times(unified_mock, unified_calendly)
        logger.debug(f"Overlapping calendar: {pformat(overlapping_calendar)}")
        
        # Get suggested time from LLM
        suggested_time = get_suggested_time(overlapping_calendar)
        
        # Create final booking URL
        final_url = create_booking_url(calendly_url, suggested_time)
        
        # Book the appointment using the imported function from scrape.py
        logger.info(f"Booking Calendly appointment at URL: {final_url}")
        booking_success = book_calendly_appointment(
            url=final_url,
            name=name,
            email=email,
            phone=phone,
            additional_info=additional_info,
            debug=True  # Enable debug logging
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