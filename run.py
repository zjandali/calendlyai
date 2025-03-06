#!/usr/bin/env python
"""
Wrapper script to run the Calendly Agent from the project root.
"""
import sys
import asyncio
import argparse
from main import main

def parse_arguments():
    """Parse command-line arguments for the Calendly Agent."""
    parser = argparse.ArgumentParser(description="Calendly Booking Agent")
    
    parser.add_argument("--calendly-url", type=str, 
                        help="The Calendly URL to book (default from settings)")
    
    parser.add_argument("--name", type=str, default="Robert Jandali",
                        help="Name to use for the booking (default: Robert Jandali)")
    
    parser.add_argument("--email", type=str, default="robert@jandali.com",
                        help="Email to use for the booking (default: robert@jandali.com)")
    
    parser.add_argument("--phone", type=str, default="5109198404",
                        help="Phone number to use for the booking (default: 5109198404)")
    
    parser.add_argument("--num-runs", type=int,
                        help="Number of booking attempts to make (default from settings)")
    
    parser.add_argument("--max-retries", type=int,
                        help="Maximum number of retries for browser errors (default from settings)")
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    asyncio.run(main(
        calendly_url=args.calendly_url,
        contact_name=args.name,
        contact_email=args.email,
        contact_phone=args.phone,
        num_runs=2,
        max_retries=args.max_retries
    )) 