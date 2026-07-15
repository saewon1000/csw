@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM /auto 또는 /y 이면 완료 후 일시정지 생략 (런처에서 자동 호출용)
set "AUTO="
if /I "%~1"=="/auto" set "AUTO=1"
if /I "%~1"=="/y" set "AUTO=1"

REM 임베디드 런타임 파이썬 우선, 없으면 시스템 python 사용
set "PYEXE=%~dp0..\runtime\python\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo.
echo ========================================
echo   가계부 웹앱 필수 패키지 설치
echo ========================================
echo.
echo 사용 파이썬: %PYEXE%
"%PYEXE%" --version
echo.
echo 필수 패키지 설치 중... (이 과정은 몇 분 소요됩니다)
echo.
"%PYEXE%" -m pip install --no-warn-script-location -r "%~dp0requirements.txt"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
    echo ========================================
    echo   설치 완료!
    echo ========================================
) else (
    echo ========================================
    echo   설치 중 오류가 발생했습니다!
    echo ========================================
    echo 인터넷 연결 상태를 확인하세요.
    echo 시스템 파이썬을 사용하는 경우 Python 3.9 이상이 PATH에 등록되어 있어야 합니다.
)
echo.
if not defined AUTO pause
exit /b %RC%