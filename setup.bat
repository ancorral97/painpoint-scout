@echo off
echo ============================================
echo  PainPoint Scout - Setup
echo ============================================

python -m venv venv
call venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
echo.
echo .env file created. Edit it with your API keys before running!
echo.
echo ============================================
echo  Done! Next steps:
echo  1. Edit .env with your API keys
echo  2. Run: start.bat
echo ============================================
pause
