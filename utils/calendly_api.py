"""
Utility functions for interacting with the Calendly API
"""

import os
import traceback
import logging
import requests
from datetime import datetime, timedelta
from langchain_openai.chat_models import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from prompts.scheduling_prompts import scheduling_prompt

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
        return uuid
        
    except Exception as e:
        logger.error(f"Error setting up Calendly API: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

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
