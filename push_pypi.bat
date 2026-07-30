@echo off

call build.bat
if errorlevel 1 exit /b 1

echo.
echo =========================================
echo Uploading to PyPI...
echo =========================================

echo ==============
set VENV=.testvenv
set PYTHON=%VENV%\Scripts\python.exe

%PYTHON% -m twine upload dist/*
if errorlevel 1 exit /b 1

echo.
echo PyPI upload completed successfully.