#requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true)]
param([switch]$CheckOnly)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath;$env:Path"
}

function Find-Python {
    foreach ($candidate in @('py', 'python')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }
        $prefix = @()
        if ($candidate -eq 'py') { $prefix = @('-3') }
        & $command.Source @prefix -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { return @{ Exe = $command.Source; Prefix = $prefix } }
    }
    return $null
}

function Invoke-Checked([string]$Executable, [string[]]$ArgumentList) {
    & $Executable @ArgumentList
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code ${LASTEXITCODE}: $Executable" }
}

function Install-WinGetPackage([string]$Id) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($null -eq $winget) { throw 'WinGet unavailable. Install Microsoft App Installer, then rerun setup.ps1.' }
    # Current-user installation; never silently fall back to machine-wide installation.
    Invoke-Checked $winget.Source @('install', '--id', $Id, '--exact', '--source', 'winget',
        '--scope', 'user', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
    Refresh-ProcessPath
}

if ($WhatIfPreference) {
    Write-Output 'Plan: detect Python 3.11+; install Python.Python.3.13 with WinGet if missing.'
    Write-Output 'Plan: create repo .venv and install requirements.txt.'
    Write-Output 'Plan: detect XeLaTeX; install MiKTeX.MiKTeX for the current user if missing.'
    Write-Output 'Plan: install required MiKTeX packages; run Chinese/math/TikZ smoke compilation and doctor.'
    Write-Output 'Plan: preserve Codex global settings; use the shared repo .codex/config.toml.'
    return
}

$python = Find-Python
if ($CheckOnly) {
    $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        Invoke-Checked $venvPython @((Join-Path $repoRoot 'scripts\doctor.py'), '--strict')
    } elseif ($null -ne $python) {
        $checkArgs = @($python.Prefix) + @((Join-Path $repoRoot 'scripts\doctor.py'), '--strict')
        Invoke-Checked $python.Exe $checkArgs
    } else { throw 'Python 3.11+ missing. Run setup.ps1 without -CheckOnly.' }
    return
}

if ($null -eq $python) {
    Install-WinGetPackage 'Python.Python.3.13'
    $python = Find-Python
    if ($null -eq $python) { throw 'Python install finished but Python is not discoverable. Restart the terminal and rerun.' }
}
$venvPath = Join-Path $repoRoot '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Invoke-Checked $python.Exe (@($python.Prefix) + @('-m', 'venv', $venvPath))
}
Invoke-Checked $venvPython @('-m', 'pip', 'install', '--requirement', (Join-Path $repoRoot 'requirements.txt'))

$engineArgs = @((Join-Path $repoRoot 'scripts\doctor.py'), '--find-xelatex')
$engine = (& $venvPython @engineArgs | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($engine)) {
    Install-WinGetPackage 'MiKTeX.MiKTeX'
    $engine = (& $venvPython @engineArgs | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($engine)) {
        throw 'MiKTeX install finished but XeLaTeX is unavailable. Restart the terminal, initialize MiKTeX Console, then rerun.'
    }
}

$texBin = Split-Path -Parent $engine
$miktex = Join-Path $texBin 'miktex.exe'
if (Test-Path -LiteralPath $miktex) {
    Invoke-Checked $miktex @('packages', 'update-package-database')
    $packages = @('fontspec', 'xecjk', 'geometry', 'amsmath', 'amsfonts', 'graphics', 'xcolor',
        'tools', 'booktabs', 'enumitem', 'tcolorbox', 'pgf', 'fancyhdr', 'hyperref', 'tex-gyre')
    Invoke-Checked $miktex (@('packages', 'install') + $packages)
}

Invoke-Checked $venvPython @((Join-Path $repoRoot 'scripts\smoke_test.py'), '--xelatex', $engine)
Invoke-Checked $venvPython @((Join-Path $repoRoot 'scripts\doctor.py'), '--strict')
Write-Output 'Setup completed. Open this repo as a Codex project and use prompts/start-book.md.'
