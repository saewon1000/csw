@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo   가계부 웹앱 필수 패키지 설치
echo ========================================
echo.
echo Python 버전 확인 중...
python --version
echo.
echo 필수 패키지 설치 중... (이 과정은 몇 분 소요됩니다)
echo.
python -m pip install -r requirements.txt
echo.
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   설치 완료!
    echo ========================================
    echo.
    echo 이제 run.bat 을 실행하면 앱을 시작할 수 있습니다.
    echo.
) else (
    echo.
    echo ========================================
    echo   설치 중 오류가 발생했습니다!
    echo ========================================
    echo.
    echo Python이 설치되어 있고 PATH에 등록되어 있는지 확인하세요.
    echo Python 3.9 이상이 필요합니다.
    echo.
)
pause
