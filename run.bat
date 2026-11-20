@echo off
echo ======================================================================
echo           Starting Resume Matcher Pro (AI + ATS Optimizer)            
echo ======================================================================
echo.
cd /d "%~dp0"

echo [1/2] Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10+
    pause
    exit /b 1
)

echo [2/2] Launching Resume Matcher Pro Web App...
echo.
echo Make sure Ollama is running in background (e.g. 'ollama run llama3.1:8b')
echo.
python -m streamlit run app.py
pause
