import random
from datetime import datetime, timedelta


def generate_mock_calendar():
    """
    Generate a mock calendar in Calendly API format with free time slots during business hours.
    
    Returns:
        dict: Formatted calendar data matching Calendly API structure
    """
    # Calculate today and format it properly
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime("%Y-%m-%d")
    
    calendly_data = {
        "invitee_publisher_error": False,
        "today": today_str,
        "availability_timezone": "America/Los_Angeles",
        "days": []
    }
    
    # Business hours - 9:00 to 17:00 (5 PM) in 30-minute increments
    business_start = 9
    business_end = 17
    
    # Process each day (today + 7 days)
    for i in range(7):
        current_date = today + timedelta(days=i)
        current_date_str = current_date.strftime("%Y-%m-%d")
        
        # Weekend days are unavailable
        if current_date.weekday() >= 5:  # Saturday or Sunday
            day_data = {
                "date": current_date_str,
                "status": "unavailable",
                "spots": [],
                "enabled": False
            }
            calendly_data["days"].append(day_data)
            continue
        
        # Create available spots for weekdays
        spots = []
        
        # Generate all possible time slots
        for hour in range(business_start, business_end):
            for minute in [0, 30]:
                # Create datetime with timezone info
                slot_time = current_date.replace(hour=hour, minute=minute)
                # Format with timezone offset (-07:00 for PDT)
                slot_time_str = slot_time.strftime("%Y-%m-%dT%H:%M:00-07:00")
                
                # Add available spot
                spots.append({
                    "status": "available",
                    "start_time": slot_time_str,
                    "invitees_remaining": 1
                })
        
        # Add day data
        day_data = {
            "date": current_date_str,
            "status": "available" if spots else "unavailable",
            "spots": spots,
            "enabled": True
        }
        
        calendly_data["days"].append(day_data)
    
    return calendly_data


def format_calendar_data(data):
    """
    Format Calendly calendar data into a consistent structure with only ISO times.
    
    Args:
        data (dict): Raw Calendly calendar data
        
    Returns:
        dict: Formatted calendar data with only ISO times for available slots
    """
    formatted_data = {
        "timezone": data.get("availability_timezone"),
        "available_dates": []
    }
    
    for day in data.get("days", []):
        date = day.get("date")
        status = day.get("status")
        
        if status == "available":
            iso_times = []
            for spot in day.get("spots", []):
                # Only include spots that are explicitly available and not booked
                if spot.get("status") == "available" and not spot.get("booking"):
                    iso_times.append(spot["start_time"])
            
            if iso_times:
                formatted_data["available_dates"].append({
                    "date": datetime.fromisoformat(date).strftime("%B %d, %Y"),
                    "iso_times": iso_times
                })
    
    return formatted_data


def convert_to_unified_format(calendar_data, source_type, target_timezone=None):
    """
    Convert calendar data from different sources to a unified format.
    
    Args:
        calendar_data (dict): Calendar data from either mock or Calendly source
        source_type (str): Either 'mock' or 'calendly'
        target_timezone (str): Target timezone to convert times to (e.g., 'America/Los_Angeles')
    
    Returns:
        dict: Unified calendar format
    """
    import pytz  # Make sure to import pytz for timezone handling
    
    unified_data = {
        "timezone": target_timezone,
        "available_days": []
    }
    
    # Determine the target timezone
    if target_timezone is None and source_type == 'calendly':
        target_timezone = calendar_data.get("timezone", "America/Los_Angeles")
    elif target_timezone is None:
        target_timezone = "America/Los_Angeles"  # Default if not specified
    
    unified_data["timezone"] = target_timezone
    target_tz = pytz.timezone(target_timezone)
    
    if source_type == 'mock':
        # Get source timezone
        source_tz = pytz.timezone(calendar_data.get("timezone", "UTC"))
        
        for day_data in calendar_data.get("available_slots", []):
            date_str = day_data.get("date")
            date_obj = datetime.strptime(date_str, "%A, %B %d, %Y")
            
            # Convert time ranges to individual time slots (30 min intervals)
            available_times = []
            for slot in day_data.get("free_slots", []):
                # Parse times in source timezone
                start_time = datetime.strptime(slot["start"], "%I:%M %p").time()
                end_time = datetime.strptime(slot["end"], "%I:%M %p").time()
                
                # Create base datetime objects for calculation
                base_date = date_obj.date()
                current = datetime.combine(base_date, start_time)
                current = source_tz.localize(current)  # Add timezone info
                
                end = datetime.combine(base_date, end_time)
                end = source_tz.localize(end)  # Add timezone info
                
                # Add time slots in 30-minute increments
                while current < end:
                    # Convert to target timezone
                    current_in_target_tz = current.astimezone(target_tz)
                    available_times.append(current_in_target_tz.strftime("%I:%M %p"))
                    current += timedelta(minutes=30)
            
            if available_times:
                # Convert date to target timezone
                date_in_target_tz = source_tz.localize(date_obj).astimezone(target_tz)
                unified_data["available_days"].append({
                    "date": date_in_target_tz.strftime("%B %d, %Y"),
                    "day_of_week": date_in_target_tz.strftime("%A"),
                    "available_times": available_times
                })
    
    elif source_type == 'calendly':
        # Calendly data is already in the desired timezone
        for day_data in calendar_data.get("available_dates", []):
            date_str = day_data.get("date")
            date_obj = datetime.strptime(date_str, "%B %d, %Y")
            
            if day_data.get("iso_times"):
                # Convert ISO times to formatted times for unified format
                available_times = []
                for iso_time in day_data.get("iso_times", []):
                    time_obj = datetime.fromisoformat(iso_time)
                    formatted_time = time_obj.strftime("%I:%M %p")
                    available_times.append(formatted_time)
                
                unified_data["available_days"].append({
                    "date": date_str,
                    "day_of_week": date_obj.strftime("%A"),
                    "available_times": available_times
                })
    
    # Sort available days by date
    unified_data["available_days"].sort(key=lambda x: datetime.strptime(x["date"], "%B %d, %Y"))
    
    return unified_data


def find_overlapping_times(calendar1, calendar2):
    """
    Find overlapping available times between two calendars in unified format.
    
    Args:
        calendar1 (dict): First calendar in unified format
        calendar2 (dict): Second calendar in unified format
        
    Returns:
        dict: Calendar with only overlapping available times
    """
    overlapping_calendar = {
        "timezone": calendar1["timezone"],  # Assume both calendars use same timezone
        "available_days": []
    }
    
    # Create lookup dictionaries for faster access
    calendar1_lookup = {day["date"]: day["available_times"] for day in calendar1["available_days"]}
    calendar2_lookup = {day["date"]: day["available_times"] for day in calendar2["available_days"]}
    
    # Find common dates
    common_dates = set(calendar1_lookup.keys()) & set(calendar2_lookup.keys())
    
    # For each common date, find overlapping times
    for date in common_dates:
        times1 = set(calendar1_lookup[date])
        times2 = set(calendar2_lookup[date])
        overlapping_times = list(times1 & times2)
        
        # Sort times chronologically from morning to evening
        def time_key(time_str):
            # Convert "01:30 AM" or "01:30 PM" to minutes since midnight for sorting
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            return time_obj.hour * 60 + time_obj.minute
        
        overlapping_times.sort(key=time_key)
        
        if overlapping_times:
            # Find day of week from either calendar
            day_of_week = next(day["day_of_week"] for day in calendar1["available_days"] if day["date"] == date)
            
            overlapping_calendar["available_days"].append({
                "date": date,
                "day_of_week": day_of_week,
                "available_times": overlapping_times
            })
    
    # Sort available days by date
    overlapping_calendar["available_days"].sort(
        key=lambda x: datetime.strptime(x["date"], "%B %d, %Y")
    )
    
    return overlapping_calendar


def generate_mock_calendly_calendar():
    """
    Generate a mock calendar in Calendly API format with free time slots during business hours.
    
    Returns:
        dict: Formatted calendar data matching Calendly API structure
    """
    # Calculate today and the next 7 days
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime("%Y-%m-%d")
    
    calendly_data = {
        "invitee_publisher_error": False,
        "today": today_str,
        "availability_timezone": "America/Los_Angeles",
        "days": []
    }
    
    # Business hours - 7:00 to 17:00 (5 PM) in 30-minute increments
    business_start = 7
    business_end = 17
    
    # Process each day (today + 14 days)
    for i in range(15):
        current_date = today + timedelta(days=i)
        current_date_str = current_date.strftime("%Y-%m-%d")
        
        # Weekend days are unavailable
        if current_date.weekday() >= 5:  # Saturday or Sunday
            calendly_data["days"].append({
                "date": current_date_str,
                "status": "unavailable",
                "spots": [],
                "invitee_events": []
            })
            continue
        
        # Create available spots for weekdays
        spots = []
        
        # Common meeting times to block (similar to generate_mock_calendar)
        common_meeting_starts = [
            (9, 0),   # Morning standup
            (10, 0),  # Mid-morning meeting
            (11, 30), # Pre-lunch meeting
            (13, 0),  # After-lunch meeting
            (14, 30), # Mid-afternoon meeting
            (16, 0)   # End-of-day wrap-up
        ]
        
        # Add 3-5 meetings per day
        num_meetings = random.randint(3, 5)
        
        # Prioritize some common meeting times, but randomize a bit
        blocked_times = random.sample(common_meeting_starts, min(num_meetings, len(common_meeting_starts)))
        
        # If we need more meetings than common times, add some random ones
        while len(blocked_times) < num_meetings:
            hour = random.randint(business_start, business_end - 1)
            minute = random.choice([0, 30])
            if (hour, minute) not in blocked_times:
                blocked_times.append((hour, minute))
        
        # Generate all possible time slots
        for hour in range(business_start, business_end):
            for minute in [0, 30]:
                # Skip blocked meeting times
                if (hour, minute) in blocked_times:
                    continue
                
                # Create datetime in local timezone
                slot_time = current_date.replace(hour=hour, minute=minute)
                
                # Convert to UTC for the API format
                slot_time_utc = slot_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
                
                # Add available spot
                spots.append({
                    "status": "available",
                    "start_time": slot_time_utc,
                    "invitees_remaining": 1
                })
        
        # Add day data
        day_data = {
            "date": current_date_str,
            "status": "available" if spots else "unavailable",
            "spots": spots,
            "invitee_events": []
        }
        
        calendly_data["days"].append(day_data)
    
    return calendly_data 