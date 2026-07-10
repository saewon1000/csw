<#
build_portable.ps1
------------------
Python이 설치되지 않은 Windows PC에서도 실행할 수 있는 "포터블" 배포본을 만든다.

동작:
  1) Windows 임베디드 Python 을 내려받아 배포 폴더에 넣는다.
  2) pip 를 활성화하고 requirements.txt 패키지를 설치한다.
  3) 앱 코드(budget_tool)와 지출내역 폴더를 복사한다.
  4) 비개발자가 더블클릭할 수 있는 '가계부_실행.bat' 런처를 만든다.

배포:
  생성된 폴더(기본: ..\portable_build\가계부_포터블)를 zip으로 압축해 전달.
  대상 PC에서 압축을 풀고 '가계부_실행.bat' 를 더블클릭하면 끝. (Python 설치 불필요)

사용법 (개발 PC에서):
  cd D:\git\csw\account_book\budget_tool
  powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
#>
[CmdletBinding()]
param(
    [string]$PyVersion = "3.11.9",
    [string]$OutDir    = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$toolDir    = Split-Path -Parent $MyInvocation.MyCommand.Path   # ...\budget_tool
$accountDir = Split-Path -Parent $toolDir                       # ...\account_book
if (-not $OutDir) { $OutDir = Join-Path $accountDir "portable_build" }

$distName = "가계부_포터블"
$distDir  = Join-Path $OutDir $distName
$pyDir    = Join-Path $distDir "python"
$appDir   = Join-Path $distDir "budget_tool"
$tmpDir   = Join-Path $OutDir "_tmp"

Write-Host "== 포터블 배포 빌드 시작 ==" -ForegroundColor Cyan
Write-Host "출력 폴더: $distDir"

# 0) 초기화
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $distDir, $pyDir, $tmpDir | Out-Null

# 1) 임베디드 Python 다운로드 + 추출
$embedZip = Join-Path $tmpDir "python-embed.zip"
$embedUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
Write-Host "[1/5] 임베디드 Python $PyVersion 다운로드..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -UseBasicParsing
Expand-Archive -Path $embedZip -DestinationPath $pyDir -Force

# ._pth 에서 'import site' 활성화 (pip / site-packages 사용 가능하게)
$pthFile = Get-ChildItem $pyDir -Filter "python*._pth" | Select-Object -First 1
if ($null -eq $pthFile) { throw "._pth 파일을 찾지 못했습니다." }
$pth = Get-Content $pthFile.FullName
$pth = $pth -replace '^\s*#\s*import site', 'import site'
if ($pth -notmatch 'import site') { $pth += "import site" }
if ($pth -notmatch 'Lib\\site-packages') { $pth += "Lib\site-packages" }
Set-Content -Path $pthFile.FullName -Value $pth -Encoding ascii

$pyExe = Join-Path $pyDir "python.exe"

# 2) pip 설치
Write-Host "[2/5] pip 부트스트랩..." -ForegroundColor Yellow
$getPip = Join-Path $tmpDir "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
& $pyExe $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "pip 설치 실패" }

# 3) 패키지 설치
Write-Host "[3/5] requirements 설치 (수 분 소요)..." -ForegroundColor Yellow
$req = Join-Path $toolDir "requirements.txt"
& $pyExe -m pip install --no-warn-script-location -r $req
if ($LASTEXITCODE -ne 0) { throw "requirements 설치 실패" }

# 4) 앱 코드 + 지출내역 복사
Write-Host "[4/5] 앱 코드 / 지출내역 복사..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$appFiles = @("__init__.py","aggregate.py","app.py","banksalad.py",
              "config.py","config.json","ingest.py","storage.py","README.md")
foreach ($f in $appFiles) {
    Copy-Item (Join-Path $toolDir $f) (Join-Path $appDir $f) -Force
}
# 지출내역 (원본 데이터) 미러링 → budget_tool 의 형제 폴더여야 경로가 맞음
$srcExport = Join-Path $accountDir "지출내역"
if (Test-Path $srcExport) {
    Copy-Item $srcExport (Join-Path $distDir "지출내역") -Recurse -Force
} else {
    New-Item -ItemType Directory -Force -Path (Join-Path $distDir "지출내역") | Out-Null
    Write-Host "  (경고) 지출내역 폴더가 없어 빈 폴더를 생성했습니다." -ForegroundColor DarkYellow
}

# 5) 런처 배치파일 생성
Write-Host "[5/5] 런처 생성..." -ForegroundColor Yellow
$bat = @'
@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 연도별 가계부
echo ================================================
echo   연도별 가계부 도구를 시작합니다.
echo   잠시 후 웹 브라우저가 자동으로 열립니다.
echo   ( 이 검은 창을 닫으면 프로그램이 종료됩니다 )
echo ================================================
echo.
set PYTHONIOENCODING=utf-8
set PORT=
for /f "delims=" %%p in ('python\python.exe _freeport.py') do set PORT=%%p
if "%PORT%"=="" set PORT=8501
echo   주소: http://localhost:%PORT%
echo.
python\python.exe -m streamlit run budget_tool\app.py --server.port %PORT% --server.address 127.0.0.1 --server.headless=false --browser.gatherUsageStats=false
echo.
echo 프로그램이 종료되었습니다. 아무 키나 누르면 창이 닫힙니다.
pause >nul
'@
Set-Content -Path (Join-Path $distDir "가계부_실행.bat") -Value $bat -Encoding oem
# .bat 을 chcp 65001 과 맞게 UTF-8(BOM 없음)로 재저장 (콘솔 한글 깨짐 방지)
$batPath = Join-Path $distDir "가계부_실행.bat"
[System.IO.File]::WriteAllText($batPath, ($bat -replace "`r?`n","`r`n"),
    (New-Object System.Text.UTF8Encoding($false)))

# 빈 포트 자동 탐색 헬퍼 (8501 등이 사용 중이어도 충돌 없이 실행)
$freeport = @'
"""사용 가능한(비어 있는) TCP 포트 번호 하나를 표준출력으로 반환한다."""
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
'@
[System.IO.File]::WriteAllText((Join-Path $distDir "_freeport.py"),
    ($freeport -replace "`r?`n","`r`n"),
    (New-Object System.Text.UTF8Encoding($false)))

# 사용 안내 파일
$readme = @'
연도별 가계부 (포터블 버전)
============================

[실행 방법]
  1. 이 폴더의  가계부_실행.bat  파일을 더블클릭하세요.
  2. 검은 콘솔 창이 뜨고, 잠시 후 웹 브라우저가 자동으로 열립니다.
  3. 브라우저에서 가계부를 사용하세요.

[종료 방법]
  - 검은 콘솔 창을 닫으면 종료됩니다.

[내 거래내역으로 바꾸기]
  - '지출내역' 폴더 안에 뱅크샐러드에서 내려받은 엑셀 파일을 넣으세요.
  - 프로그램을 다시 실행하면 자동으로 반영됩니다.

* Python 설치가 필요 없습니다. 폴더째로 복사해서 사용하세요.
* 인터넷 연결 없이 내 PC 안에서만 동작합니다.
'@
Set-Content -Path (Join-Path $distDir "사용설명.txt") -Value $readme -Encoding utf8

# 정리
Remove-Item $tmpDir -Recurse -Force

$sizeMB = [math]::Round((Get-ChildItem $distDir -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host ""
Write-Host "== 완료 ==" -ForegroundColor Green
Write-Host "배포 폴더: $distDir  (약 $sizeMB MB)"
Write-Host "이 폴더를 zip으로 압축해 전달하면, 대상 PC에서 '가계부_실행.bat' 더블클릭으로 실행됩니다."
