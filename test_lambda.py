#!/usr/bin/env python3

import os
import json
import sys
from lambda_handler import lambda_handler

# Load environment variables from both local and parent .env files
import sys
sys.path.append('..')
from dotenv import load_dotenv

# Load from local .env first (higher priority)
load_dotenv('.env')
# Load from parent .env as fallback
load_dotenv('../.env')

print(f"🔑 Environment Check:")
print(f"   - JINA_READER_API_KEY: {'✅ Available' if os.getenv('JINA_READER_API_KEY') else '❌ Missing'}")
print(f"   - RAPIDAPI_KEY: {'✅ Available' if os.getenv('RAPIDAPI_KEY') else '❌ Missing'}")
print(f"   - BASE_API_URL: {'✅ ' + os.getenv('BASE_API_URL', 'Not Set') if os.getenv('BASE_API_URL') else '❌ Missing'}")
print(f"   - INSIGHTS_API_KEY: {'✅ Available' if os.getenv('INSIGHTS_API_KEY') else '❌ Missing'}")
print("-" * 50)

# Mock AWS Lambda context
class MockContext:
    def __init__(self):
        self.function_name = "new_company_processor_test"
        self.function_version = "$LATEST"
        self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:new_company_processor_test"
        self.memory_limit_in_mb = 512
        self.remaining_time_in_millis = lambda: 300000

def test_lambda():
    """Test the Lambda function with the provided webpageId"""

    # Load test event
    with open('test_event.json', 'r') as f:
        event = json.load(f)

    print(f"🚀 Testing Lambda with event: {event}")
    print("-" * 50)

    # Create mock context
    context = MockContext()

    try:
        # Call the Lambda handler
        result = lambda_handler(event, context)

        print(f"✅ Lambda execution completed!")
        print(f"Status Code: {result['statusCode']}")

        # Parse and display the response
        response_body = json.loads(result['body'])

        if result['statusCode'] == 200 and response_body.get('success'):
            print(f"🎉 SUCCESS!")
            print(f"📊 Company Processing Complete:")
            print(f"   - Webpage ID: {response_body.get('webpageId')}")
            print(f"   - Nodes Updated: {response_body.get('nodesUpdated', 0)}")
            print(f"   - Processing Via: {response_body.get('via', 'Unknown')}")
            print(f"   - Status: {response_body.get('message', 'Processed successfully')}")
            print(f"   - ✅ Company data has been processed and stored")
            print()
            print("📝 Note: Company data is now processed via event-based system")

        else:
            print(f"❌ FAILED!")
            print(f"Error: {response_body.get('error', 'Unknown error')}")
            if response_body.get('jinaError'):
                print(f"Jina Error: {response_body['jinaError']}")
            if response_body.get('rapidapiError'):
                print(f"RapidAPI Error: {response_body['rapidapiError']}")

    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_lambda()