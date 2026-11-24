@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if errorlevel 1 (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    echo Python 3.10 or newer was not found. Install Python, then try again.
    pause
    exit /b 1
)

%PYTHON_CMD% -c "import pandas, mlxtend, matplotlib, networkx, PIL, tkinter" >nul 2>nul
if errorlevel 1 (
    echo Installing the packages needed by the desktop app...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)

echo Opening Basket Insights...
%PYTHON_CMD% app.py
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo Setup failed. Check the message above. If Windows Security displayed an alert,
echo note the exact alert and the file it names so the cause can be identified.
pause
exit /b 1
