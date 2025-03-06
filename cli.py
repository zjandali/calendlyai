import os
import argparse
import asyncio
from datetime import datetime

from config.settings import settings
from workflow import run_multiple_workflows
from tools.calendly_api import book_calendly_meeting


async def run_booking_once(args):
    """Run a single booking workflow"""
    # Get API keys
    anchor_api_key = args.anchor_api_key or settings.anchor_api_key or os.getenv("ANCHOR_API_KEY")
    openai_api_key = args.openai_api_key or settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    
    if not anchor_api_key or not openai_api_key:
        print("Error: Missing required API keys. Please set ANCHOR_API_KEY and OPENAI_API_KEY.")
        return
    
    print(f"Running single booking workflow for URL: {args.calendly_url}")
    result = await book_calendly_meeting(args.calendly_url, anchor_api_key, openai_api_key, args.max_retries)
    
    if result.get("success", False):
        print(f"Successfully booked: {result.get('suggested_time_pst', 'Time not available')}")
    else:
        print(f"Booking failed: {result.get('error', 'Unknown error')}")
    
    # Save result to file
    import json
    os.makedirs("eval", exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(f"eval/booking_result_{timestamp}.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Result saved to eval/booking_result_{timestamp}.json")


async def run_multiple_bookings(args):
    """Run multiple booking workflows"""
    # Get API keys
    anchor_api_key = args.anchor_api_key or settings.anchor_api_key or os.getenv("ANCHOR_API_KEY")
    openai_api_key = args.openai_api_key or settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    
    if not anchor_api_key or not openai_api_key:
        print("Error: Missing required API keys. Please set ANCHOR_API_KEY and OPENAI_API_KEY.")
        return
    
    print(f"Running {args.num_runs} booking workflows for URL: {args.calendly_url}")
    summary = await run_multiple_workflows(
        args.calendly_url, 
        anchor_api_key, 
        openai_api_key, 
        args.num_runs, 
        args.max_retries
    )
    
    print(f"Evaluation complete! Success rate: {summary['this_run']['success_rate']}%")
    print(f"Successful runs: {summary['this_run']['successful_runs']}/{summary['this_run']['total_runs']}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Calendly Booking Agent CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Global arguments
    parser.add_argument(
        "--anchor-api-key", 
        help="Anchor Browser API key (can also be set as ANCHOR_API_KEY env var)"
    )
    parser.add_argument(
        "--openai-api-key", 
        help="OpenAI API key (can also be set as OPENAI_API_KEY env var)"
    )
    
    # Subparsers for different commands
    subparsers = parser.add_subparsers(title="Commands", dest="command")
    
    # Book once command
    book_parser = subparsers.add_parser("book", help="Book a single calendly appointment")
    book_parser.add_argument(
        "--calendly-url", 
        default=settings.default_calendly_url,
        help="Calendly URL to book"
    )
    book_parser.add_argument(
        "--max-retries", 
        type=int, 
        default=settings.default_max_retries,
        help="Maximum number of retries for Anchor Browser errors"
    )
    
    # Evaluate command (multiple bookings)
    eval_parser = subparsers.add_parser("evaluate", help="Run multiple booking evaluations")
    eval_parser.add_argument(
        "--calendly-url", 
        default=settings.default_calendly_url,
        help="Calendly URL to book"
    )
    eval_parser.add_argument(
        "--num-runs", 
        type=int, 
        default=settings.default_num_runs,
        help="Number of times to run the workflow"
    )
    eval_parser.add_argument(
        "--max-retries", 
        type=int, 
        default=settings.default_max_retries,
        help="Maximum number of retries for Anchor Browser errors"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "book":
        asyncio.run(run_booking_once(args))
    elif args.command == "evaluate":
        asyncio.run(run_multiple_bookings(args))


if __name__ == "__main__":
    main() 