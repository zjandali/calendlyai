import json
import requests
import traceback
from datetime import datetime, timedelta
from playwright.async_api import async_playwright


async def book_calendly_meeting(calendly_url, anchor_api_key, openai_api_key, max_retries=3, contact_details=None):
    """
    Run the entire Calendly booking workflow
    
    Args:
        calendly_url (str): Calendly URL to book
        anchor_api_key (str): API key for Anchor Browser
        openai_api_key (str): API key for OpenAI
        max_retries (int): Maximum number of retries for Anchor Browser errors
        contact_details (dict, optional): Contact information for booking
            {
                "name": str,
                "email": str, 
                "phone": str
            }
        
    Returns:
        dict: Result of the workflow
    """
    from utils.calendar_utils import (
        generate_mock_calendar,
        format_calendar_data,
        convert_to_unified_format,
        find_overlapping_times
    )
    from langchain.chat_models import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from langchain.output_parsers import ResponseSchema, StructuredOutputParser
    
    try:
        # Generate mock calendar
        mock_calendar = generate_mock_calendar()
        print("Generated mock calendar")
        
        # Get Calendly user's available slots
        url_parts = calendly_url.split('/')
        profile_slug = url_parts[-2]
        event_type_slug = url_parts[-1].split('?')[0]
        id_url = f"https://calendly.com/api/booking/event_types/lookup?event_type_slug={event_type_slug}&profile_slug={profile_slug}"
        
        # Get UUID
        response = requests.get(id_url)
        response.raise_for_status()
        event_data = response.json()
        uuid = event_data.get("uuid")
        print(f"Retrieved Calendly UUID: {uuid}")
        
        # Get available time ranges
        range_url = f"https://calendly.com/api/booking/event_types/{uuid}/calendar/range"
        start_date = datetime.now()
        end_date = start_date + timedelta(days=35)
        params = {
            "timezone": "America/Los_Angeles",
            "diagnostics": "false",
            "range_start": start_date.strftime("%Y-%m-%d"),
            "range_end": end_date.strftime("%Y-%m-%d")
        }
        
        calendar_response = requests.get(range_url, params=params)
        calendar_response.raise_for_status()
        calendly_data = calendar_response.json()
        print("Retrieved Calendly availability data")
        
        # Format calendar data
        calendly_formatted = format_calendar_data(calendly_data)
        print("Formatted Calendly data")
        
        # Convert both calendars to unified format
        calendly_timezone = calendly_formatted.get("timezone", "America/Los_Angeles")
        unified_mock = convert_to_unified_format(mock_calendar, 'mock', calendly_timezone)
        unified_calendly = convert_to_unified_format(calendly_formatted, 'calendly')
        
        # Find overlapping times
        overlapping_calendar = find_overlapping_times(unified_mock, unified_calendly)
        print("Found overlapping available times")
        
        # Define the output schema for LLM
        response_schema = ResponseSchema(
            name="suggested_time",
            description="The suggested meeting time in ISO 8601 format",
            type="string"
        )
        
        # Create the parser
        parser = StructuredOutputParser.from_response_schemas([response_schema])
        format_instructions = parser.get_format_instructions()
        
        # Create the prompt template
        prompt_template = ChatPromptTemplate.from_template("""
        You are a scheduling assistant. Please analyze the following available meeting times and suggest the best option.

        Overlapping Available Times:
        {overlapping_availability}

        Find the best meeting time from these overlapping time slots at the earliest reasonable business hour.

        {format_instructions}

        Note: The suggested_time MUST be in this exact format:
        "2025-03-05T09:30:00-08:00?month=2025-03&date=2025-03-05"
        - Include ISO 8601 datetime with timezone offset (-08:00 for PST)
        - Include query parameters for month and date
        """)
        
        # Initialize the LLM
        llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0,
            openai_api_key=openai_api_key
        )
        
        # Get suggested time from LLM
        messages = prompt_template.format_messages(
            overlapping_availability=json.dumps(overlapping_calendar, indent=2),
            format_instructions=format_instructions
        )
        
        response = llm.invoke(messages)
        parsed_response = parser.parse(response.content)
        suggested_time = parsed_response['suggested_time']
        print(f"LLM suggested time: {suggested_time}")
        
        # Extract ISO datetime for URL construction
        iso_datetime = suggested_time.split('?')[0] if '?' in suggested_time else suggested_time
        
        # Construct the booking URL
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(iso_datetime)
        pst_zone = ZoneInfo("America/Los_Angeles")
        dt_pst = dt.astimezone(pst_zone)
        formatted_time = dt_pst.strftime("%Y-%m-%dT%H:%M:%S-08:00")
        
        month_param = dt.strftime("%Y-%m")
        date_param = dt.strftime("%Y-%m-%d")
        
        base_path = '/'.join(calendly_url.split('?')[0].split('/')[:-1]) if calendly_url.endswith('/') else '/'.join(calendly_url.split('?')[0].split('/'))
        final_url = f"{base_path}/{formatted_time}?month={month_param}&date={date_param}"
        print(f"Created booking URL: {final_url}")
        
        # Use default contact info if not provided
        name = "Robert Jandali"
        email = "robert@jandali.com"
        phone = "5109198404"
        
        # Override with provided values if any
        if contact_details:
            if contact_details.get("name"):
                name = contact_details["name"]
            if contact_details.get("email"):
                email = contact_details["email"]
            if contact_details.get("phone"):
                phone = contact_details["phone"]
        
        # Book meeting with Playwright
        retry_count = 0
        session_id = None
        
        while retry_count <= max_retries:
            try:
                # Create anchor session
                url = "https://api.anchorbrowser.io/api/sessions"
                payload = {
                    "adblock_config": {
                        "active": False,
                        "popup_blocking_active": False
                    },
                    "captcha_config": {"active": True},
                    "headless": False,
                    "proxy_config": {
                        "type": "anchor_residential",
                        "active": True
                    },
                    "recording": {"active": False},
                    "profile": {
                        "name": "my-profile",
                        "persist": True,
                        "store_cache": True
                    },
                    "viewport": {
                        "width": 1440,
                        "height": 900
                    },
                    "timeout": 10,
                    "idle_timeout": 3
                }
                
                headers = {
                    "anchor-api-key": anchor_api_key,
                    "Content-Type": "application/json"
                }
                
                response = requests.request("POST", url, json=payload, headers=headers)
                session_id = response.json()['id']
                anchor_url = f"wss://connect.anchorbrowser.io?apiKey={anchor_api_key}&sessionId={session_id}"
                print(f"Created Anchor Browser session: {session_id}")
                
                try:
                    async with async_playwright() as p:
                        browser = await p.chromium.connect_over_cdp(anchor_url)
                        context = browser.contexts[0]
                        ai = context.service_workers[0]
                        page = context.pages[0]
                        
                        await page.goto(final_url)
                        
                        task = f"~ Fill out the form with name {name}, email {email}, phone {phone}, and click the Schedule Event button. Wait until the confirmation page is loaded or a success message appears."
                        result = await ai.evaluate(task)
                        print(result)
                        
                        # Broader check to catch more variations of success messages
                        success = (
                            "confirmation page" in result.lower() or 
                            "success message" in result.lower() or 
                            "clicked the schedule event button" in result.lower() or
                            "successfully filled" in result.lower() or
                            "calendar invitation" in result.lower() or
                            "has been sent" in result.lower() or
                            "confirmation page loaded" in result.lower() or
                            "scheduled" in result.lower()
                        )
                        
                        await browser.close()
                        
                        # Convert ISO time to PST for display
                        dt_pst = datetime.fromisoformat(iso_datetime).astimezone(pst_zone)
                        pst_time_str = dt_pst.strftime("%A, %B %d, %Y at %I:%M %p PST")
                        
                        return {
                            "success": success,
                            "result": result,
                            "booking_url": final_url,
                            "suggested_time_iso": suggested_time,
                            "suggested_time_pst": pst_time_str,
                            "timestamp": datetime.now().isoformat(),
                            "session_id": session_id
                        }
                finally:
                    # Clean up Anchor Browser session
                    if session_id:
                        delete_url = f"https://api.anchorbrowser.io/api/sessions/{session_id}"
                        headers = {"anchor-api-key": anchor_api_key}
                        requests.request("DELETE", delete_url, headers=headers)
                        print(f"Deleted Anchor Browser session: {session_id}")
            
            except Exception as e:
                error_str = str(e)
                retry_count += 1
                
                # Check if it's the specific "Unexpected identifier 'out'" error
                if "Unexpected identifier 'out'" in error_str and retry_count <= max_retries:
                    print(f"Encountered 'Unexpected identifier out' error. Retrying ({retry_count}/{max_retries})...")
                    # Clean up the session if it exists before retrying
                    if session_id:
                        delete_url = f"https://api.anchorbrowser.io/api/sessions/{session_id}"
                        headers = {"anchor-api-key": anchor_api_key}
                        requests.request("DELETE", delete_url, headers=headers)
                        print(f"Deleted Anchor Browser session: {session_id}")
                    # Wait a bit before retrying
                    import asyncio
                    await asyncio.sleep(2)
                else:
                    # If it's not the specific error or we've exceeded retries, re-raise
                    raise
        
        # If we've exhausted all retries
        raise Exception(f"Failed after {max_retries} retries")
    
    except Exception as e:
        print(f"Error in workflow: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        } 