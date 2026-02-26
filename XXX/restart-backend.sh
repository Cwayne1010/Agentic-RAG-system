#!/bin/bash
# Restart the FastAPI backend

# Kill any process on port 8000
PID=$(lsof -ti :8000)
if [ -n "$PID" ]; then
  echo "Killing existing backend (PID $PID)..."
  kill $PID
  sleep 1
fi

# Start backend
cd /Users/wayner/RAG/backend
source venv/bin/activate
uvicorn app.main:app --reload
