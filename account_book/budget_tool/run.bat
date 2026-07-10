@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 가계부 웹 앱을 시작합니다...
python -m streamlit run app.py
pause
