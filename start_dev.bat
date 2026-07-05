@echo off
echo Starting JobSwipe Development Environment...

echo Starting Backend...
start "JobSwipe Backend" cmd /k "cd backend && call venv\Scripts\activate && uvicorn app.main:app --reload"

echo Starting Frontend...
start "JobSwipe Frontend" cmd /k "cd frontend && npm run dev"

echo Both servers are starting in separate windows.
