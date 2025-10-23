#!/bin/bash
###############################################################################
# Development Startup Script
#
# This script starts both the backend and frontend with automatic port syncing.
# No more port mismatch issues!
#
# Usage:
#   ./scripts/start-dev.sh
#   ./scripts/start-dev.sh --backend-only
#   ./scripts/start-dev.sh --frontend-only
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         LLMOps Agent Development Environment             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo

# Parse arguments
BACKEND_ONLY=false
FRONTEND_ONLY=false

for arg in "$@"; do
  case $arg in
    --backend-only)
      BACKEND_ONLY=true
      ;;
    --frontend-only)
      FRONTEND_ONLY=true
      ;;
  esac
done

# Function to check if port is in use
check_port() {
  local port=$1
  if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    return 0  # Port is in use
  else
    return 1  # Port is free
  fi
}

# Function to kill process on port
kill_port() {
  local port=$1
  echo -e "${YELLOW}⚠  Port $port is already in use, killing existing process...${NC}"
  lsof -ti:$port | xargs kill -9 2>/dev/null || true
  sleep 1
}

# Start backend
start_backend() {
  echo -e "${GREEN}🚀 Starting Backend API...${NC}"

  # Get port from .env
  BACKEND_PORT=$(grep "^API_PORT=" .env | cut -d '=' -f2)
  BACKEND_PORT=${BACKEND_PORT:-8003}

  echo -e "   Port: ${BLUE}$BACKEND_PORT${NC}"

  # Kill existing process on port
  if check_port $BACKEND_PORT; then
    kill_port $BACKEND_PORT
  fi

  # Check if poetry is available
  if ! command -v poetry &> /dev/null; then
    echo -e "${RED}❌ Poetry not found. Please install Poetry first.${NC}"
    exit 1
  fi

  # Start backend in background
  cd "$PROJECT_ROOT"
  poetry run uvicorn llmops_agent.api.main:app \
    --host 0.0.0.0 \
    --port $BACKEND_PORT \
    --reload \
    --log-level info &

  BACKEND_PID=$!
  echo -e "   PID: ${BLUE}$BACKEND_PID${NC}"
  echo

  # Wait for backend to start
  echo -e "${YELLOW}⏳ Waiting for backend to start...${NC}"
  sleep 3

  if check_port $BACKEND_PORT; then
    echo -e "${GREEN}✅ Backend API is running at http://localhost:$BACKEND_PORT${NC}"
    echo -e "${GREEN}   API Docs: http://localhost:$BACKEND_PORT/docs${NC}"
    echo
  else
    echo -e "${RED}❌ Backend failed to start${NC}"
    exit 1
  fi
}

# Start frontend
start_frontend() {
  echo -e "${GREEN}🎨 Starting Frontend UI...${NC}"

  cd "$PROJECT_ROOT/llmops-agent-ui"

  # Get frontend port from package.json or default to 3000
  FRONTEND_PORT=3000

  echo -e "   Port: ${BLUE}$FRONTEND_PORT${NC}"

  # Kill existing process on port
  if check_port $FRONTEND_PORT; then
    kill_port $FRONTEND_PORT
  fi

  # Sync config from backend (critical!)
  echo -e "${YELLOW}🔄 Syncing config from backend .env...${NC}"
  npm run sync-config
  echo

  # Start frontend
  npm run dev &
  FRONTEND_PID=$!
  echo -e "   PID: ${BLUE}$FRONTEND_PID${NC}"
  echo

  # Wait for frontend to start
  echo -e "${YELLOW}⏳ Waiting for frontend to start...${NC}"
  sleep 5

  if check_port $FRONTEND_PORT; then
    echo -e "${GREEN}✅ Frontend UI is running at http://localhost:$FRONTEND_PORT${NC}"
    echo
  else
    echo -e "${RED}❌ Frontend failed to start${NC}"
    exit 1
  fi
}

# Main execution
if [ "$FRONTEND_ONLY" = true ]; then
  start_frontend
elif [ "$BACKEND_ONLY" = true ]; then
  start_backend
else
  start_backend
  start_frontend
fi

# Print summary
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    🎉 All Systems Go!                     ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo

if [ "$FRONTEND_ONLY" != true ]; then
  echo -e "${GREEN}Backend API:${NC}  http://localhost:${BACKEND_PORT}"
  echo -e "${GREEN}API Docs:${NC}     http://localhost:${BACKEND_PORT}/docs"
fi

if [ "$BACKEND_ONLY" != true ]; then
  echo -e "${GREEN}Frontend UI:${NC}  http://localhost:${FRONTEND_PORT}"
fi

echo
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo

# Wait for processes
wait
