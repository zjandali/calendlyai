from langchain.prompts import ChatPromptTemplate

def scheduling_prompt():
    return ChatPromptTemplate.from_template("""
    You are a scheduling assistant. Please analyze the following available meeting times and suggest the best option.

    Available Times:
    {overlapping_availability}

    Find the best meeting time from these  time slots at the earliest reasonable business hour. DO NOT PICK A TIME THAT IS NOT IN THE  AVAILABILITY.
    {format_instructions}

    Note: The suggested_time MUST be converted to this exact format:
    "2025-03-05T09:30:00-07:00?month=2025-03&date=2025-03-05"
    - Include query parameters for month and date
    """)

