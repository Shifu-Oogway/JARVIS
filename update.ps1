<#
.SYNOPSIS
    JARVIS Update Script (PowerShell) — applies a jarvis-phaseX.zip to the installation dir.
    Native Windows equivalent of update.sh — no bash, WSL, or Git Bash required.

.USAGE
    .\update.ps1 <jarvis-phaseX.zip> [-DryRun] [-SkipBackup]
    .\update.ps1 -Rollback <backup-folder-name>

.NOTES
    First run may need: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
    (Windows blocks running downloaded/unsigned scripts by default.)
#>

param(
    [Parameter(Position = 0)]
    [string]$ZipPath,

    [switch]$DryRun,
    [switch]$SkipBackup,

    [string]$Rollback
)

$ErrorActionPreference = "Stop"

# ── helpers ──────────────────────────────────────────────────────────────────
function Write-Ok   { param($Msg) Write-Host "OK   $Msg" -ForegroundColor Green }
function Write-Info { param($Msg) Write-Host "...  $Msg" -ForegroundColor Cyan }
function Write-Warn { param($Msg) Write-Host "!!!  $Msg" -ForegroundColor Yellow }
function Write-Fail { param($Msg) Write-Host "FAIL $Msg" -ForegroundColor Red }
function Write-Step  { param($Msg) Write-Host "`n$Msg" -ForegroundColor White }

$ScriptDir = $PSScriptRoot
$BackupRoot = Join-Path $ScriptDir ".jarvis-backups"
$SkipDirNames = @(".env", "data", "node_modules", ".next", "__pycache__", ".git", ".jarvis-backups")
$SkipExtensions = @(".pyc", ".pyo", ".log")

function Test-PathExcluded {
    param([string]$RelativePath)
    $parts = $RelativePath -split '[\\/]'
    foreach ($p in $parts) { if ($SkipDirNames -contains $p) { return $true } }
    $ext = [System.IO.Path]::GetExtension($RelativePath)
    return $SkipExtensions -contains $ext
}

function Copy-TreeExcluding {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
    Get-ChildItem -Path $Source -Force | ForEach-Object {
        if ($SkipDirNames -contains $_.Name) { return }
        $target = Join-Path $Destination $_.Name
        if ($_.PSIsContainer) {
            Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
            # prune skip-dirs that may exist nested inside (mirrors bash ignore_patterns)
            Get-ChildItem -Path $target -Recurse -Directory -Force |
                Where-Object { $SkipDirNames -contains $_.Name } |
                ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
        } else {
            Copy-Item -Path $_.FullName -Destination $target -Force
        }
    }
}

# ── rollback ─────────────────────────────────────────────────────────────────
function Invoke-Rollback {
    param([string]$BackupPath)
    Write-Fail "Update failed. Rolling back..."
    if ($BackupPath -and (Test-Path $BackupPath)) {
        Copy-TreeExcluding -Source $BackupPath -Destination $ScriptDir
        Write-Ok "Rolled back to $(Split-Path $BackupPath -Leaf)"
        if ((Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $ScriptDir "docker-compose.yml"))) {
            Push-Location $ScriptDir
            docker compose up -d --build 2>$null
            Pop-Location
        }
    } else {
        Write-Warn "No backup available - rollback skipped."
    }
}

# ── explicit rollback mode ──────────────────────────────────────────────────
if ($Rollback) {
    $target = Join-Path $BackupRoot $Rollback
    if (-not (Test-Path $target)) {
        Write-Fail "Backup not found: $target"
        exit 1
    }
    Invoke-Rollback -BackupPath $target
    exit 0
}

# ── validate args ────────────────────────────────────────────────────────────
Write-Step "[ JARVIS Updater ]"
Write-Host "  Package : $ZipPath"
Write-Host "  Target  : $ScriptDir"
Write-Host "  Dry-run : $DryRun"

if (-not $ZipPath) {
    Write-Fail "Usage: .\update.ps1 <jarvis-phaseX.zip> [-DryRun] [-SkipBackup]"
    exit 1
}
if (-not (Test-Path $ZipPath)) {
    Write-Fail "File not found: $ZipPath"
    exit 1
}
if ([System.IO.Path]::GetExtension($ZipPath) -ne ".zip") {
    Write-Fail "Expected a .zip file"
    exit 1
}

# ── extract ──────────────────────────────────────────────────────────────────
Write-Step "1 / 6  Inspecting package"
$WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) ("jarvis-update-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null

try {
    Expand-Archive -Path $ZipPath -DestinationPath $WorkDir -Force

    $JarvisRoot = $WorkDir
    if (Test-Path (Join-Path $WorkDir "jarvis")) { $JarvisRoot = Join-Path $WorkDir "jarvis" }

    if (-not (Test-Path (Join-Path $JarvisRoot "backend")) -and -not (Test-Path (Join-Path $JarvisRoot "frontend"))) {
        Write-Fail "The zip does not look like a JARVIS package (no backend/ or frontend/ found)"
        exit 1
    }

    # ── diff (MD5 hash comparison) ──────────────────────────────────────────
    $sourceFiles = Get-ChildItem -Path $JarvisRoot -Recurse -File -Force
    $changed = @()
    foreach ($sf in $sourceFiles) {
        $rel = $sf.FullName.Substring($JarvisRoot.Length).TrimStart('\', '/')
        if (Test-PathExcluded $rel) { continue }
        $df = Join-Path $ScriptDir $rel
        $isChanged = $true
        if (Test-Path $df) {
            $h1 = (Get-FileHash -Path $sf.FullName -Algorithm MD5).Hash
            $h2 = (Get-FileHash -Path $df -Algorithm MD5).Hash
            $isChanged = ($h1 -ne $h2)
        }
        if ($isChanged) { $changed += $rel }
    }

    if ($changed.Count -eq 0) {
        Write-Ok "Nothing to update - package matches what is already installed."
        exit 0
    }

    Write-Info "$($changed.Count) file(s) will be updated:"
    foreach ($f in ($changed | Sort-Object)) { Write-Host "     $f" -ForegroundColor Cyan }

    if ($DryRun) {
        Write-Host ""
        Write-Ok "Dry run complete - nothing written."
        exit 0
    }

    # ── backup ───────────────────────────────────────────────────────────────
    $RollbackBackup = $null
    if (-not $SkipBackup) {
        Write-Step "2 / 6  Creating backup"
        New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
        $RollbackBackup = Join-Path $BackupRoot ("backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        Copy-TreeExcluding -Source $ScriptDir -Destination $RollbackBackup
        Write-Ok "Backup -> $RollbackBackup"

        # prune backups older than 30 days
        Get-ChildItem -Path $BackupRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
            ForEach-Object { Remove-Item $_.FullName -Recurse -Force; Write-Host "Pruned: $($_.Name)" }
    } else {
        Write-Warn "Skipping backup (-SkipBackup)"
    }

    # ── apply ────────────────────────────────────────────────────────────────
    Write-Step "3 / 6  Applying changes"
    try {
        foreach ($rel in $changed) {
            $sf = Join-Path $JarvisRoot $rel
            $df = Join-Path $ScriptDir $rel
            $parent = Split-Path $df -Parent
            if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            Copy-Item -Path $sf -Destination $df -Force
        }
        Write-Ok "$($changed.Count) file(s) applied"
    } catch {
        Invoke-Rollback -BackupPath $RollbackBackup
        exit 1
    }

    # ── Python deps ──────────────────────────────────────────────────────────
    Write-Step "4 / 6  Installing dependencies"
    $Backend = Join-Path $ScriptDir "backend"
    $Frontend = Join-Path $ScriptDir "frontend"

    if (Test-Path (Join-Path $Backend "pyproject.toml")) {
        $py = "python"
        $venvPy = Join-Path $Backend ".venv\Scripts\python.exe"
        if (Test-Path $venvPy) { $py = $venvPy; Write-Info "Using venv" }
        & $py -m pip install -q -e $Backend 2>&1 | Select-Object -Last 20
        Write-Ok "Python dependencies up to date"
    }

    if (Test-Path (Join-Path $Frontend "package.json")) {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Push-Location $Frontend
            npm install --silent 2>&1 | Select-Object -Last 3
            Pop-Location
            Write-Ok "npm packages up to date"
        } else {
            Write-Warn "npm not found - run 'npm install' in frontend\ manually"
        }
    }

    # ── DB migrations (Alembic) ─────────────────────────────────────────────
    if (Test-Path (Join-Path $Backend "alembic.ini")) {
        $py = "python"
        $venvPy = Join-Path $Backend ".venv\Scripts\python.exe"
        if (Test-Path $venvPy) { $py = $venvPy }
        & $py -c "import alembic" 2>$null
        $alembicOk = ($LASTEXITCODE -eq 0)
        if ($alembicOk) {
            Write-Info "Running database migrations..."
            Push-Location $Backend
            & $py -m alembic upgrade head 2>&1 | Select-Object -Last 5
            Pop-Location
        }
    }

    # ── tests ────────────────────────────────────────────────────────────────
    Write-Step "5 / 6  Running tests"
    if (Test-Path (Join-Path $Backend "tests")) {
        $py = "python"
        $venvPy = Join-Path $Backend ".venv\Scripts\python.exe"
        if (Test-Path $venvPy) { $py = $venvPy }

        Push-Location $Backend
        $env:JARVIS_NIM_API_KEY = ""
        & $py -m pytest -q 2>&1 | Select-Object -Last 6
        $testsOk = ($LASTEXITCODE -eq 0)
        Pop-Location

        if ($testsOk) {
            Write-Ok "All tests passed"
        } else {
            Write-Fail "Tests failed - rolling back"
            Invoke-Rollback -BackupPath $RollbackBackup
            exit 1
        }
    } else {
        Write-Warn "No tests\ directory found - skipping"
    }

    # ── restart services ─────────────────────────────────────────────────────
    Write-Step "6 / 6  Restarting services"
    if ((Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $ScriptDir "docker-compose.yml"))) {
        Push-Location $ScriptDir
        $running = docker compose ps --services --status running 2>$null
        if ($running) {
            Write-Info "Rebuilding running Docker services..."
            docker compose up -d --build 2>&1 | Select-Object -Last 6
            Write-Ok "Services restarted"
        } else {
            Write-Warn "No running Docker services found - start with: docker compose up --build"
        }
        Pop-Location
    } else {
        Write-Warn "Docker not found - restart services manually"
    }

    # ── summary ──────────────────────────────────────────────────────────────
    Write-Host ""
    Write-Host "Update complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Package  : $(Split-Path $ZipPath -Leaf)" -ForegroundColor Cyan
    Write-Host "  Files    : $($changed.Count) updated" -ForegroundColor Cyan
    Write-Host "  Backup   : $(if ($RollbackBackup) { $RollbackBackup } else { 'none' })" -ForegroundColor Cyan
    Write-Host ""
    if ($RollbackBackup) {
        Write-Host "  To roll back manually:"
        Write-Host "    .\update.ps1 -Rollback $(Split-Path $RollbackBackup -Leaf)" -ForegroundColor Yellow
    }
}
finally {
    if (Test-Path $WorkDir) { Remove-Item $WorkDir -Recurse -Force -ErrorAction SilentlyContinue }
}