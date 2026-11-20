@echo off
echo ======================================================================
echo           Installing Dependencies for Resume Matcher Pro              
echo ======================================================================
echo.
cd /d "%~dp0"

echo [*] Installing Python packages from requirements.txt...
pip install -r requirements.txt

echo.
echo [*] Checking Ollama installation...
ollama --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [+] Ollama is installed!
    echo.
    echo To pull the recommended Llama model, run:
    echo   ollama pull llama3.1:8b
    echo.
    echo Or for lightweight machines:
    echo   ollama pull llama3.2:3b
) else (
    echo [!] Ollama CLI not detected in PATH.
    echo Download and install Ollama from: https://ollama.com/download
)

echo.
echo ======================================================================
echo Setup completed! You can now launch the app by double-clicking 'run.bat'
echo ======================================================================
pause
