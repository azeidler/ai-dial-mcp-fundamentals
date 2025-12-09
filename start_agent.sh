#!/bin/bash
# Start the agent

cd "$(dirname "$0")"
source .venv/bin/activate

# Check for required environment variables
if [ -z "$DIAL_API_KEY" ] || [ -z "$DIAL_ENDPOINT" ]; then
    echo "Error: DIAL_API_KEY and DIAL_ENDPOINT must be set"
    echo ""
    echo "Please set them:"
    echo "  export DIAL_API_KEY='your_key'"
    echo "  export DIAL_ENDPOINT='your_endpoint'"
    exit 1
fi

python agent/app.py
