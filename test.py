import logging
import time
from datetime import datetime
from calendly_continuous_workflow import run_calendly_workflow
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_test_suite(num_runs, delay_between_runs=0):
    """
    Run the Calendly workflow multiple times and collect statistics
    
    Args:
        num_runs (int): Number of test runs to perform
        delay_between_runs (int): Delay in seconds between runs to avoid rate limiting
    """
    results = {
        'successful': 0,
        'failed': 0,
        'total_runs': num_runs,
        'start_time': datetime.now(),
        'successful_urls': [],
        'errors': []
    }
    
    logger.info(f"Starting test suite with {num_runs} runs")
    logger.info(f"Delay between runs: {delay_between_runs} seconds")
    
    for run_num in range(1, num_runs + 1):
        try:
            logger.info(f"\nStarting run {run_num}/{num_runs}")
            
            # Test data - you can modify these values as needed
            test_data = {
                "name": f"Test User {run_num}",
                "email": f"test{run_num}@example.com",
                "phone": "5109198404",
                "additional_info": f"Test booking {run_num}",
                "timezone": "America/Los_Angeles",
                "max_retries": 3
            }
            
            # Run the workflow
            start_time = time.time()
            result = run_calendly_workflow(**test_data)
            end_time = time.time()
            
            if result:
                results['successful'] += 1
                results['successful_urls'].append(result)
                logger.info(f"Run {run_num} successful - URL: {result}")
            else:
                results['failed'] += 1
                error_msg = f"Run {run_num} failed - No booking URL returned"
                results['errors'].append(error_msg)
                logger.error(error_msg)
            
            logger.info(f"Run {run_num} completed in {end_time - start_time:.2f} seconds")
            
            # Wait between runs unless it's the last run
            if run_num < num_runs:
                logger.info(f"Waiting {delay_between_runs} seconds before next run...")
                time.sleep(delay_between_runs)
                
        except Exception as e:
            results['failed'] += 1
            error_msg = f"Run {run_num} failed with error: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
    
    # Calculate and log final statistics
    results['end_time'] = datetime.now()
    duration = results['end_time'] - results['start_time']
    success_rate = (results['successful'] / results['total_runs']) * 100
    
    logger.info("\n=== Test Suite Results ===")
    logger.info(f"Total Runs: {results['total_runs']}")
    logger.info(f"Successful: {results['successful']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Success Rate: {success_rate:.2f}%")
    logger.info(f"Total Duration: {duration}")
    logger.info(f"Average Time Per Run: {duration.total_seconds() / results['total_runs']:.2f} seconds")
    
    if results['errors']:
        logger.info("\nErrors encountered:")
        for error in results['errors']:
            logger.info(f"- {error}")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Calendly workflow test suite')
    parser.add_argument('--runs', type=int, default=5, help='Number of test runs to perform')
    parser.add_argument('--delay', type=int, default=0, help='Delay between runs in seconds')
    
    args = parser.parse_args()
    
    run_test_suite(args.runs, args.delay)