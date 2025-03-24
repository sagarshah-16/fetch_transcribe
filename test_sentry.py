import os
import sentry_sdk
from dotenv import load_dotenv
import sys
import traceback

# Load environment variables
load_dotenv()

# Initialize Sentry with direct DSN
sentry_dsn = "https://6dfff80fcb1a2211dc8c000b7b9f7ae4@o1135944.ingest.us.sentry.io/4509030358384640"

# Initialize Sentry SDK with your project's DSN
sentry_sdk.init(
    dsn=sentry_dsn,
    traces_sample_rate=1.0,  # Capture 100% of transactions for testing
    profiles_sample_rate=1.0,  # Capture 100% of profiles for testing
    environment=os.getenv("ENVIRONMENT", "development"),
    release=os.getenv("RELEASE", "0.1.0"),
)

def main():
    try:
        # Set user context
        sentry_sdk.set_user({"id": "test-user-123", "email": "test@example.com"})

        # Add breadcrumb
        sentry_sdk.add_breadcrumb(
            category="test",
            message="About to trigger a test error",
            level="info"
        )

        # Start a transaction for performance monitoring
        with sentry_sdk.start_transaction(op="test", name="Test Sentry Error") as transaction:
            # Add span for more detailed performance tracking
            with sentry_sdk.start_span(op="test.division", description="Division operation"):
                print("Triggering a test error for Sentry...")

                # Deliberately cause an error
                result = 1 / 0  # Will cause a ZeroDivisionError

                print("This line will never execute")

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print("This error has been reported to Sentry.")

        # Capture the exception with additional context
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "test_error")
            scope.set_context("test_info", {
                "purpose": "Testing Sentry integration",
                "test_id": "manual-test-001",
                "environment": os.getenv("ENVIRONMENT", "development")
            })
            sentry_sdk.capture_exception(e)

        # Also manually capture a message
        sentry_sdk.capture_message("This is a test message sent along with the error", level="warning")

        # Print the full traceback for local debugging
        traceback.print_exc()

if __name__ == "__main__":
    main()

    # Wait a moment to ensure Sentry has time to send the event
    print("\nWaiting for Sentry to process the error...")
    import time
    time.sleep(2)
    print("Done. Check your Sentry dashboard to see the error report.")