# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# One-command local demonstration of LEGION Market Genesis (Windows PowerShell 5.1+).
#
#   .\run_market_genesis_demo.ps1 -NimKeyFile C:\path\to\nvapi.txt [-Arm A2] [-Port 8790] [-SkipWorlds]
#
# Prerequisites: Python 3.11+, git, network access to github.com and integrate.api.nvidia.com,
# an NVIDIA NIM API key in a local file. The script clones (or reuses) the externally licensed LEGION Core
# at the pinned revision (PolyForm Noncommercial 1.0.0) and LEGION-Federation next to this repository.
# Only SIMULATED production/delivery/ledger effects are produced. No PayPal call is made by this script.
param(
    [Parameter(Mandatory = $true)][string]$NimKeyFile,
    [ValidateSet("A1", "A2")][string]$Arm = "A2",
    [int]$Port = 8790,
    [switch]$SkipWorlds,
    [switch]$NoBrowser
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here
$Core = Join-Path $Root "LEGION-Core-pinned"
$Fed = Join-Path $Root "LEGION-Federation"
$CorePin = "d083c44af2526e38068e0220891cd0bb5fce52af"

if (-not (Test-Path $NimKeyFile)) { throw "NIM key file not found: $NimKeyFile" }
if (-not (Test-Path $Core)) { git clone -q https://github.com/veraxis-protocol/LEGION.git $Core }
git -C $Core checkout -q $CorePin
if ((git -C $Core rev-parse HEAD) -ne $CorePin) { throw "LEGION Core is not at the pinned revision" }
if (-not (Test-Path $Fed)) { git clone -q https://github.com/veraxis-protocol/LEGION-Federation.git $Fed }

$Venv = Join-Path $Root ".venv-genesis"
if (-not (Test-Path $Venv)) { python -m venv $Venv }
$Py = Join-Path $Venv "Scripts\python.exe"
& $Py -m pip install -q -r (Join-Path $Here "requirements.lock")

$Stamp = Get-Date -Format "yyyyMMddTHHmmss"
$Out = Join-Path $Root "runs\demo-$Stamp"
New-Item -ItemType Directory -Force $Out | Out-Null
$env:PYTHONPATH = "$Fed;$Here"
$env:LMF_NIM_KEY_FILE = (Resolve-Path $NimKeyFile).Path

Write-Host "1/4 unit tests (Federation schemas)"
Push-Location $Fed; & $Py -m unittest tests.test_schemas; Pop-Location

if (-not $SkipWorlds) {
    Write-Host "2/4 13 worlds x 4 federated cases (independent Judge per world)"
    Push-Location $Fed
    & $Py tools\run_world_cases.py --cases (Join-Path $Here "fixtures\FED_WORLD_CASES.json") --core $Core --out (Join-Path $Out "worlds")
    Pop-Location
}

Write-Host "3/4 seven-owner first attempt ($Arm) - dashboard on http://127.0.0.1:$Port/ (LIVE while running)"
$Run = Join-Path $Out "e2e-$Arm"
New-Item -ItemType Directory -Force $Run | Out-Null
$dash = Start-Process -PassThru -NoNewWindow $Py -ArgumentList @("-m", "legion_marketplace.dashboard", "--run", $Run, "--port", $Port,
    "--worlds", (Join-Path $Out "worlds")) -WorkingDirectory $Here
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port/" }
Push-Location $Here
& $Py -m legion_marketplace.e2e --core $Core --out $Run --arm $Arm
Pop-Location

Write-Host "4/4 adversarial negative suites against live owner processes"
Push-Location $Here
& $Py -m legion_marketplace.negatives --core $Core --out (Join-Path $Out "negatives")
Pop-Location
Write-Host "Done. Evidence: $Out . Judge: $Run\JUDGE_RESULT.json . Dashboard keeps running (pid $($dash.Id)) in REPLAY mode."
