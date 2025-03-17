from langchain.prompts import ChatPromptTemplate

def scheduling_prompt():
    template = """
    You are a scheduling assistant. Please analyze the following available meeting times and suggest the best option.

    Overlapping Available Times:
    {overlapping_availability}

    Based on the available times, please suggest the best meeting time. Choose a time that is during business hours (09:00:00-07:00 to 17:00:00-07:00 in ISO 8601 format) if possible, and preferably not too early or too late in the day.

    {format_instructions}
    """
    
    return ChatPromptTemplate.from_template(template)

