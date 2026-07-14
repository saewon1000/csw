@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 연도별 가계부

set "PYEXE=runtime\python\python.exe"
set "MARKER=runtime\.ready"

if not exist "%MARKER%" (
    echo ================================================
    echo   최초 실행 준비 중입니다.
    echo   파이썬 런타임을 내려받아 설치합니다.
    echo   인터넷 연결이 필요하며 수 분 정도 걸립니다.
    echo   ( 이 준비는 처음 한 번만 진행됩니다 )
    echo ================================================
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_runtime.ps1"
    if errorlevel 1 (
        echo.
        echo [오류] 런타임 준비에 실패했습니다.
        echo        인터넷 연결을 확인한 뒤 다시 실행해 주세요.
        pause
        exit /b 1
    )
)

echo.
echo ================================================
echo   연도별 가계부 도구를 시작합니다.
echo   잠시 후 웹 브라우저가 자동으로 열립니다.
echo   ( 이 검은 창을 닫으면 프로그램이 종료됩니다 )
echo ================================================
echo.
set PYTHONIOENCODING=utf-8
set PORT=
for /f "delims=" %%p in ('"%PYEXE%" "%~dp0_freeport.py"') do set PORT=%%p
if "%PORT%"=="" set PORT=8501
echo   주소: http://localhost:%PORT%
echo.
"%PYEXE%" -m streamlit run "%~dp0budget_tool\app.py" --server.port %PORT% --server.address 127.0.0.1 --server.headless=false --browser.gatherUsageStats=false
echo.
echo 프로그램이 종료되었습니다. 아무 키나 누르면 창이 닫힙니다.
pause >nul