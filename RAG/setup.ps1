# setup.ps1 - Automated Python Environment Setup for Windows
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Version-Aware RAG - Automated Environment Setup" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Function to test if a given python binary is valid and not a dead WindowsApps redirector
function Test-PythonBinary {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -Path $Path -PathType Leaf)) { return $false }

    try {
        $output = & $Path --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $output -match "Python \d+\.\d+") {
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

$discoveredPython = $null

# 1. Search common Windows installation directories and environments
$candidateLocations = @(
    "C:\ANACONDA\python.exe",
    "C:\ProgramData\Anaconda3\python.exe",
    "C:\ProgramData\miniconda3\python.exe",
    "$env:USERPROFILE\anaconda3\python.exe",
    "$env:USERPROFILE\miniconda3\python.exe",
    "C:\Python312\python.exe",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python311\python.exe",
    "C:\Program Files\Python310\python.exe"
)

Write-Host "[1/4] Searching common Windows directories..." -ForegroundColor Yellow
foreach ($candidate in $candidateLocations) {
    if (Test-PythonBinary -Path $candidate) {
        $discoveredPython = $candidate
        break
    }
}

# 2. Check Windows Registry (HKCU / HKLM) if not found yet
if (-not $discoveredPython) {
    Write-Host "[1/4] Inspecting Windows Registry for registered Python installations..." -ForegroundColor Yellow
    $regPaths = @(
        "HKCU:\Software\Python\PythonCore\*\InstallPath",
        "HKLM:\Software\Python\PythonCore\*\InstallPath"
    )
    foreach ($regPath in $regPaths) {
        $installs = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
        foreach ($item in $installs) {
            $folder = $item.'(default)'
            if ($folder) {
                $pyPath = Join-Path $folder "python.exe"
                if (Test-PythonBinary -Path $pyPath) {
                    $discoveredPython = $pyPath
                    break
                }
            }
        }
        if ($discoveredPython) { break }
    }
}

# 3. Check environment PATH
if (-not $discoveredPython) {
    Write-Host "[1/4] Checking system PATH..." -ForegroundColor Yellow
    $pathCommands = Get-Command python, py -ErrorAction SilentlyContinue | Where-Object { 
        $_.Source -notlike "*WindowsApps*" 
    }
    foreach ($cmd in $pathCommands) {
        if (Test-PythonBinary -Path $cmd.Source) {
            $discoveredPython = $cmd.Source
            break
        }
    }
}

# Handle missing Python scenario
if (-not $discoveredPython) {
    Write-Host ""
    Write-Host "[ERROR] No valid Python installation was found on your system." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.11 with PATH registration via winget by running:" -ForegroundColor Yellow
    Write-Host "  winget install Python.Python.3.11 --scope machine" -ForegroundColor Green
    Write-Host ""
    Write-Host "After installation finishes, close and reopen PowerShell and re-run: .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

$pyVersion = (& $discoveredPython --version 2>&1)
Write-Host "[OK] Detected Python executable: $discoveredPython ($pyVersion)" -ForegroundColor Green

# 4. Create virtual environment (venv)
$venvDir = Join-Path $PSScriptRoot "venv"
Write-Host "[2/4] Setting up virtual environment at '$venvDir'..." -ForegroundColor Yellow

if (-not (Test-Path $venvDir)) {
    & $discoveredPython -m venv "$venvDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[OK] Virtual environment created successfully." -ForegroundColor Green
} else {
    Write-Host "[OK] Existing virtual environment found." -ForegroundColor Green
}

# 5. Locate venv python and pip executables
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"
$venvActivate = Join-Path $venvDir "Scripts\Activate.ps1"

if (-not (Test-Path $venvPip)) {
    Write-Host "[ERROR] Virtual environment pip executable not found at '$venvPip'." -ForegroundColor Red
    exit 1
}

# 6. Upgrade pip and install requirements
Write-Host "[3/4] Upgrading pip inside virtual environment..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet

$requirementsFile = Join-Path $PSScriptRoot "requirements.txt"
if (Test-Path $requirementsFile) {
    Write-Host "[4/4] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $venvPip install -r "$requirementsFile"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to install dependencies from requirements.txt." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[OK] All dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "[WARNING] requirements.txt not found in current folder." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Setup complete! Virtual environment is ready." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To activate the environment in this terminal session, run:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To start the FastAPI service, run:" -ForegroundColor Cyan
Write-Host "  uvicorn main:app --reload" -ForegroundColor White
Write-Host ""
