import random
from datetime import datetime, timedelta

def generate_mock_calendar():
    """
    Generate a mock calendar in Calendly API format with mostly busy time slots during business hours.
    
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
                
                # Make most slots busy (80% chance of being busy)
                if random.random() < 0.8:
                    continue
                
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



def find_matching_times(calendar1, calendar2):
    """
    Find matching available time slots between two calendars with Calendly-like structure.
    """
    # Create sets of available times from both calendars
    times1 = set()
    times2 = set()
    
    # Helper function to extract times from a calendar
    def extract_times(calendar, time_set):
        for day in calendar.get('days', []):
            if day['status'] == 'available' and day.get('enabled', True):
                for spot in day.get('spots', []):
                    if spot['status'] == 'available' and spot.get('invitees_remaining', 0) > 0:
                        # Parse the ISO format time string
                        time = datetime.fromisoformat(spot['start_time'])
                        time_set.add(time)
    
    # Extract times from both calendars
    extract_times(calendar1, times1)
    extract_times(calendar2, times2)
    
    # Find intersection of available times
    matching_times = sorted(times1.intersection(times2))
    
    return matching_times


def format_matches(matching_times):
    """
    Format matching times in a readable way.
    
    Args:
        matching_times (list): List of datetime objects
        
    Returns:
        str: Formatted string of times
    """
    formatted_times = []
    for time in matching_times:
        iso_format = time.strftime("%Y-%m-%dT%H:%M:%S-07:00")
        readable_format = time.strftime("%A, %B %d, %Y at %I:%M %p")
        formatted_times.append(f"{readable_format} ({iso_format})")
    
    # Join the times with line breaks for better readability in the prompt
    return "\n".join(formatted_times)