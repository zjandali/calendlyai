import random
from datetime import datetime, timedelta


def generate_mock_calendar():
    """
    Generate a formatted mock calendar with free time slots during normal business hours.
    
    Returns:
        dict: Formatted calendar data with realistic free time slots
    """
    # Calculate start (tomorrow) and end (7 days from tomorrow) dates
    tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    formatted_data = {
        "week_of": tomorrow.strftime("%B %d, %Y"),
        "timezone": "UTC",  # Changed from America/Los_Angeles to UTC
        "available_slots": []
    }
    
    # Business hours - 9:00 to 17:00 (5 PM)
    business_start = 9
    business_end = 17
    
    # Process each day
    for i in range(7):
        current_date = tomorrow + timedelta(days=i)
        if current_date.weekday() < 5:  # Skip weekends
            # Create a schedule for the day with 30-minute blocks
            day_schedule = {}
            for hour in range(business_start, business_end):
                for minute in [0, 30]:
                    day_schedule[f"{hour}:{minute:02d}"] = "free"
            
            # Common meeting times
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
            selected_times = random.sample(common_meeting_starts, min(num_meetings, len(common_meeting_starts)))
            
            # If we need more meetings than common times, add some random ones
            while len(selected_times) < num_meetings:
                hour = random.randint(business_start, business_end - 1)
                minute = random.choice([0, 30])
                if (hour, minute) not in selected_times:
                    selected_times.append((hour, minute))
            
            # Block time for meetings
            for hour, minute in selected_times:                
                # 30 or 60 minute meetings
                duration = random.choice([30, 60])
                
                # Mark meeting blocks as occupied
                for block in range(duration // 30):
                    block_hour = (hour + (minute + block * 30) // 60) % 24
                    block_minute = (minute + block * 30) % 60
                    block_key = f"{block_hour}:{block_minute:02d}"
                    if block_key in day_schedule:
                        day_schedule[block_key] = "busy"
            
            # Convert schedule to available slots
            free_slots = []
            current_start = None
            
            for hour in range(business_start, business_end):
                for minute in [0, 30]:
                    time_key = f"{hour}:{minute:02d}"
                    
                    if day_schedule.get(time_key) == "free":
                        if current_start is None:
                            current_start = current_date.replace(hour=hour, minute=minute)
                    else:  # busy or end of time slot
                        if current_start is not None:
                            end_time = current_date.replace(hour=hour, minute=minute)
                            # Only add if slot is at least 30 minutes
                            free_slots.append({
                                "start": current_start.strftime("%I:%M %p"),
                                "end": end_time.strftime("%I:%M %p")
                            })
                            current_start = None
            
            # Handle case where the last slot(s) of the day are free
            if current_start is not None:
                end_time = current_date.replace(hour=business_end, minute=0)
                free_slots.append({
                    "start": current_start.strftime("%I:%M %p"),
                    "end": end_time.strftime("%I:%M %p")
                })
            
            if free_slots:
                formatted_data["available_slots"].append({
                    "date": current_date.strftime("%A, %B %d, %Y"),
                    "free_slots": free_slots
                })
    
    return formatted_data


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