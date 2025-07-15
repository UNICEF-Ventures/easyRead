#!/bin/bash

# Frontend Restart Script
# This script restarts the frontend with the correct environment variables

# Default values
FRONTEND_PORT=${VITE_PORT:-5173}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            FRONTEND_PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --port PORT    Set frontend port (default: 5173)"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}⚡ Restarting Frontend on port $FRONTEND_PORT${NC}"

# Check if frontend dependencies are installed
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
    npm install
fi

# Show current environment variables
echo -e "${YELLOW}🔧 Current environment variables:${NC}"
if [ -f ".env" ]; then
    echo "   .env file exists"
    cat .env
else
    echo -e "${RED}   No .env file found${NC}"
fi

echo ""
echo -e "${GREEN}🚀 Starting frontend development server...${NC}"
echo -e "${YELLOW}   Check browser console for API Base URL logs${NC}"
echo -e "${YELLOW}   If API calls fail, make sure backend is running on the correct port${NC}"
echo ""

# Start frontend
npm run dev -- --port $FRONTEND_PORT