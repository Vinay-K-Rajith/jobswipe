@echo off
echo ========================================
echo JobSwipe Backend Setup (Windows)
echo ========================================

cd /d "%~dp0backend"
echo Current directory: %cd%

echo.
echo Step 1: Creating virtual environment...
if exist venv (
    echo Removing stale virtual environment...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create venv
    exit /b 1
)

echo.
echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Step 3: Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    exit /b 1
)

echo.
echo Step 4: Downloading spacy model...
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('spacy') else 1)"
if errorlevel 1 (
    echo Skipping spacy model download because spaCy is not installed.
) else (
    python -m spacy download en_core_web_sm
    if errorlevel 1 (
        echo WARNING: Failed to download spacy model, continuing without it.
    )
)

echo.
echo Step 5: Running database seed...
python scripts\seed_db.py
if errorlevel 1 (
    echo ERROR: Failed to seed database
    exit /b 1
)

echo.
echo Step 6: Starting backend server...
echo Backend will run on http://localhost:8000
echo.
echo API Documentation will be at:
echo   - http://localhost:8000/docs (Interactive Swagger UI)
echo   - http://localhost:8000/redoc (ReDoc)
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
