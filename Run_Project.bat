@echo off
setlocal
cd /d "%~dp0"
title DS-A38 Association Rule Mining

echo ================================================
echo   DS-A38 - Food Product Association Mining
echo ================================================
echo.

where python >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if errorlevel 1 (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    echo Python launcher was not found. Install Python 3.10 or newer, then try again.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing or checking required packages...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Running Apriori and FP-Growth. Charts and tables will be saved in output\.
echo.
%PYTHON_CMD% -u main.py --data data/groceries.csv --support 0.05 --confidence 0.30 --lift 1.0
if errorlevel 1 goto :failed

echo.
echo Finished. Open the output folder to view the results.
pause
exit /b 0

:failed
echo.
echo The project did not finish. Read the error above. If Windows Security showed an alert,
echo note the exact alert text and the file or action it names before changing any settings.
pause
exit /b 1
