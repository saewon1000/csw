@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 연도별 가계부

set "PYEXE=%~dp0runtime\python\python.exe"

REM ── 1) 임베디드 파이썬 런타임이 없으면 최초 구성 ──
if not exist "%PYEXE%" call :setup_runtime
if not exist "%PYEXE%" goto :setup_failed

REM ── 2) 필수 모듈 확인 (마커가 아닌 실제 import 로 검증) ──
"%PYEXE%" -c "import streamlit, pandas, plotly, openpyxl" 1>nul 2>nul
if not errorlevel 1 goto :run

REM 모듈 누락 → install.bat 자동 실행
echo.
echo ================================================
echo   실행에 필요한 모듈이 없어 자동으로 설치합니다.
echo   인터넷 연결이 필요하며 수 분 정도 걸립니다.
echo ================================================
echo.
call "%~dp0budget_tool\install.bat" /auto
cd /d "%~dp0"

REM 설치 후 재확인
"%PYEXE%" -c "import streamlit, pandas, plotly, openpyxl" 1>nul 2>nul
if not errorlevel 1 goto :run

REM 그래도 실패 → 런타임 전체 재구성 (최후의 수단)
echo.
echo 설치 후에도 모듈을 찾을 수 없어 런타임을 다시 구성합니다...
call :setup_runtime_force
if not exist "%PYEXE%" goto :setup_failed
"%PYEXE%" -c "import streamlit, pandas, plotly, openpyxl" 1>nul 2>nul
if errorlevel 1 goto :setup_failed

:run
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
exit /b 0

:setup_runtime
echo ================================================
echo   최초 실행 준비 중입니다.
echo   파이썬 런타임을 내려받아 설치합니다.
echo   인터넷 연결이 필요하며 수 분 정도 걸립니다.
echo   ( 이 준비는 처음 한 번만 진행됩니다 )
echo ================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_runtime.ps1"
exit /b %ERRORLEVEL%

:setup_runtime_force
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_runtime.ps1" -Force
exit /b %ERRORLEVEL%

:setup_failed
echo.
echo [오류] 실행 준비에 실패했습니다.
echo        인터넷 연결을 확인한 뒤 다시 실행해 주세요.
echo.
pause
exit /b 1