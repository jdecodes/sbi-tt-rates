@echo off
setlocal

echo ==============
set VENV=.testvenv
set PYTHON=%VENV%\Scripts\python.exe

echo ======================================
echo sbi_tt_rates Build
echo ======================================

::del /s /q *.pyc

:: ------------------------------------------------------------
:: Check Python exists
:: ------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not on PATH.
    exit /b 1
)

:: ------------------------------------------------------------
:: Create virtual environment if needed
:: ------------------------------------------------------------
if not exist "%PYTHON%" (
    echo.
    echo Creating virtual environment...
    python -m venv %VENV%

    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)

echo.
echo Using virtual environment: %VENV%

:: ------------------------------------------------------------
:: Upgrade pip
:: ------------------------------------------------------------
:: %PYTHON% -m pip install --upgrade pip

%PYTHON% -c "import sys; print(sys.executable)"
%PYTHON% --version
%PYTHON% -m pip --version
%PYTHON% -m build --version
%PYTHON% -m pytest --version
%PYTHON% -m ruff --version
%PYTHON% -m twine --version
:: ------------------------------------------------------------
:: Install developer dependencies
:: ------------------------------------------------------------
%PYTHON% -m pip install -r requirements-dev.txt
%PYTHON% -m pip install -e .
:: ------------------------------------------------------------
:: Clean
:: ------------------------------------------------------------
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist dist rmdir /S /Q logs

echo Running Ruff to format the code...
%PYTHON% -m ruff format .

echo Running Ruff...
%PYTHON% -m ruff check . --fix

if errorlevel 1 exit /b 1

:: ------------------------------------------------------------
:: Run tests
:: ------------------------------------------------------------
echo.
echo Running tests...

mkdir logs 2>nul

%PYTHON% -m pytest -v

set LOGFILE=logs\pytest.log
%PYTHON% -m pytest -v > "%LOGFILE%" 2>&1

if errorlevel 1 (
    echo.
    echo Tests failed.
    exit /b 1
)

:: ------------------------------------------------------------
:: Build
:: ------------------------------------------------------------
echo.
echo Building package...
%PYTHON% -m build

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

:: ------------------------------------------------------------
:: Validate package
:: ------------------------------------------------------------
echo.
echo Running twine check...
%PYTHON% -m twine check dist/*

if errorlevel 1 (
    echo Twine check failed.
    exit /b 1
)

echo.
echo ======================================
echo Build completed successfully!
echo ======================================

dir dist

endlocal