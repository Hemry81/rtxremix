@echo off
echo ========================================
echo USD Point Instancer Converter Setup
echo ========================================
echo.
echo This script will install all required Python packages for the USD Point Instancer Converter.
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.8+ and ensure it's in your system PATH.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python version:
python --version
echo.

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not installed or not available.
    echo Please ensure pip is installed with your Python installation.
    pause
    exit /b 1
)

echo pip version:
pip --version
echo.

echo ========================================
echo Installing Required Packages
echo ========================================
echo.

echo [1/4] Installing USD Core library...
pip install usd-core>=23.0
if errorlevel 1 (
    echo WARNING: usd-core installation failed. Trying alternative usd-python...
    pip install usd-python>=23.0
    if errorlevel 1 (
        echo ERROR: Failed to install USD library. This is required for the converter.
        echo Please install USD manually or check your internet connection.
        pause
        exit /b 1
    )
)
echo USD library installed successfully.
echo.

echo [2/4] Installing NumPy for numerical operations...
pip install numpy>=1.21.0
if errorlevel 1 (
    echo ERROR: Failed to install NumPy. This is required for texture processing.
    pause
    exit /b 1
)
echo NumPy installed successfully.
echo.

echo [3/4] Installing Pillow for image processing...
pip install Pillow>=8.0.0
if errorlevel 1 (
    echo ERROR: Failed to install Pillow. This is required for texture conversion.
    pause
    exit /b 1
)
echo Pillow installed successfully.
echo.

echo [4/4] Installing optional psutil for process monitoring...
pip install psutil>=5.8.0
if errorlevel 1 (
    echo WARNING: Failed to install psutil. This is optional - converter will work without it.
) else (
    echo psutil installed successfully.
)
echo.

echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo All required packages have been installed.
echo You can now run the converter using:
echo.
echo   For GUI:  python unified_PointInstancer_converter_ui.py
echo   For CLI:  python unified_PointInstancer_converter.py --help
echo.
echo Note: If you encounter tkinter errors, you may need to install GUI support:
echo   - Windows: Usually included with Python
echo   - Linux: sudo apt-get install python3-tk
echo   - macOS: Usually included with Python
echo.
pause