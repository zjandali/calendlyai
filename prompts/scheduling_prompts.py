from langchain.prompts import ChatPromptTemplate

SCHEDULING_PROMPT = ChatPromptTemplate.from_template("""
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

