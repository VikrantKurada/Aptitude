<#
Aptitude launcher (Windows / PowerShell).

Creates a local virtual environment on first run, installs Aptitude into it,
then runs the CLI. Any arguments you pass are forwarded to `aptitude`.

Examples:
  .\start.ps1                     # show help
  .\start.ps1 providers           # list providers and which have credentials
  .\start.ps1 create -p "Build a GDPR privacy-policy skill" -i law.pdf --provider ollama
#>
$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv   = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Setting up Aptitude (first run)..." -ForegroundColor Cyan
    python -m venv $venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -e $root
}

if ($args.Count -eq 0) {
    & $python -m aptitude --help
} else {
    & $python -m aptitude @args
}
