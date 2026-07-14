<#
setup_runtime.ps1
-----------------
Python이 설치되지 않은 Windows PC에서도 이 가계부 툴을 실행할 수 있도록,
이 폴더(account_book) 하위에 'runtime\python' 임베디드 파이썬 런타임을 구성한다.

git 저장소에는 용량이 큰 파이썬 런타임을 포함하지 않으므로(.gitignore),
clone 후 '가계부_실행.bat' 을 처음 실행할 때 이 스크립트가 자동으로 호출되어
런타임을 내려받고 필요한 패키지를 설치한다. (최초 1회, 인터넷 필요)

수동 실행:
  powershell -ExecutionPolicy Bypass -File .\setup_runtime.ps1
#>
[CmdletBinding()]
param(
    [string]$PyVersion = "3.11.9",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path   # ...\account_book
$runtime = Join-Path $root "runtime"
$pyDir   = Join-Path $runtime "python"
$tmpDir  = Join-Path $runtime "_tmp"
$marker  = Join-Path $runtime ".ready"
$req     = Join-Path $root "budget_tool\requirements.txt"

if ((Test-Path $marker) -and -not $Force) {
    Write-Host "런타임이 이미 준비되어 있습니다." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $req)) { throw "requirements.txt 를 찾지 못했습니다: $req" }

Write-Host "== 파이썬 런타임 구성 시작 (최초 1회) ==" -ForegroundColor Cyan
Write-Host "대상 폴더: $runtime"

# 0) 초기화 (미완성 런타임이 남아 있으면 정리)
if (Test-Path $runtime) { Remove-Item $runtime -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pyDir, $tmpDir | Out-Null

# 1) 임베디드 Python 다운로드 + 추출
$embedZip = Join-Path $tmpDir "python-embed.zip"
$embedUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
Write-Host "[1/3] 임베디드 Python $PyVersion 다운로드..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -UseBasicParsing
Expand-Archive -Path $embedZip -DestinationPath $pyDir -Force

# ._pth 에서 'import site' 활성화 (pip / site-packages 사용 가능하게)
$pthFile = Get-ChildItem $pyDir -Filter "python*._pth" | Select-Object -First 1
if ($null -eq $pthFile) { throw "._pth 파일을 찾지 못했습니다." }
$pth = Get-Content $pthFile.FullName
$pth = $pth -replace '^\s*#\s*import site', 'import site'
if ($pth -notmatch 'import site')        { $pth += "import site" }
if ($pth -notmatch 'Lib\\site-packages') { $pth += "Lib\site-packages" }
Set-Content -Path $pthFile.FullName -Value $pth -Encoding ascii

$pyExe = Join-Path $pyDir "python.exe"

# 2) pip 부트스트랩
Write-Host "[2/3] pip 부트스트랩..." -ForegroundColor Yellow
$getPip = Join-Path $tmpDir "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
& $pyExe $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "pip 설치 실패" }

# 3) requirements 설치
Write-Host "[3/3] 필요한 패키지 설치 (수 분 소요)..." -ForegroundColor Yellow
& $pyExe -m pip install --no-warn-script-location -r $req
if ($LASTEXITCODE -ne 0) { throw "패키지 설치 실패" }

# 정리 + 완료 표시
Remove-Item $tmpDir -Recurse -Force
New-Item -ItemType File -Path $marker -Force | Out-Null

Write-Host ""
Write-Host "== 런타임 준비 완료 ==" -ForegroundColor Green
