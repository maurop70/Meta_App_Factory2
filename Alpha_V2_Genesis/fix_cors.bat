@echo off
cd /d "%~dp0"
echo FIXING CORS DEPENDENCY...
python -m pip install flask-cors
echo.
echo Dependency Installed.
pause
