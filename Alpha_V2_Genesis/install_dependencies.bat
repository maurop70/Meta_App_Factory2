@echo off
cd /d "%~dp0"
echo Installing Alpha V2 Genesis Dependencies...
python -m pip install -r requirements.txt
echo.
echo Also ensuring pyngrok specifically (just in case)...
python -m pip install pyngrok
echo.
echo DEPENDENCIES INSTALLED.
pause
