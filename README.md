# Calendly Agent

A LangChain-powered agent for automatically booking Calendly appointments based on available time slots.

## Features

- Generates a mock calendar representing your availability
- Retrieves available slots from a Calendly account
- Finds overlapping time slots between your calendar and the Calendly availability
- Uses LLM to select the optimal meeting time
- Automates the booking process using Playwright and Anchor Browser

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:

```bash
python -m playwright install
```

4. Set up required environment variables in a `.env` file:

```
ANCHOR_API_KEY=your_anchor_api_key
OPENAI_API_KEY=your_openai_api_key
DEFAULT_CALENDLY_URL=https://calendly.com/user/meeting
```

## Usage

There are two main ways to use the application:

### Using the CLI

Book a single appointment:

```bash
python -m calendly_agent.cli book --calendly-url https://calendly.com/username/30min
```

Run multiple bookings for evaluation:

```bash
python -m calendly_agent.cli evaluate --num-runs 5 --max-retries 3
```

### Using the Main Script

Run with default parameters:

```bash
python -m calendly_agent.main
```

Override number of runs with command-line arguments:

```bash
python -m calendly_agent.main 10 5
```

This will run 10 booking attempts with a maximum of 5 retries for each.

## Project Structure

```
calendly_agent/
├── agents/         # Agent definitions
├── chains/         # LangChain chains
├── config/         # Configuration settings
├── data/           # Data resources
├── models/         # Data models
├── prompts/        # Prompt templates
├── tools/          # Integration tools
├── utils/          # Utility functions
├── cli.py          # CLI interface
├── main.py         # Main entry point
├── requirements.txt # Dependencies
└── README.md       # Documentation
```

## License

MIT 