[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist/package",
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create .venv and install project dependencies first."
}

Push-Location $repoRoot
try {
    Write-Host "[1/6] Building frontend..." -ForegroundColor Cyan
    npm --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }

    Write-Host "[2/6] Running tests and checks..." -ForegroundColor Cyan
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    & $python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed" }
    & $python -m mypy
    if ($LASTEXITCODE -ne 0) { throw "mypy failed" }

    Write-Host "[3/6] Installing PyInstaller..." -ForegroundColor Cyan
    & $python -m pip install "pyinstaller>=6.15,<7"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed" }

    $target = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
    $distRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot "dist"))
    $distPrefix = $distRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $target.StartsWith($distPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "OutputDirectory must be located under $distRoot"
    }
    $work = Join-Path $repoRoot "build/pyinstaller"
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    New-Item -ItemType Directory -Path $work -Force | Out-Null

    $runtimeHook = "tools/runtime_hook.py"

    Write-Host "[4/6] Building PyInstaller packages..." -ForegroundColor Cyan

    Write-Host "  -> CAEReportServer (onedir)..." -ForegroundColor Yellow
    & $python -m PyInstaller --noconfirm --clean --onedir --name CAEReportServer `
        --distpath $target --workpath (Join-Path $work "server") `
        --paths "server/src;shared/python" `
        --add-data "frontend/dist;frontend/dist" `
        --runtime-hook $runtimeHook `
        "tools/entrypoints/server_main.py"
    if ($LASTEXITCODE -ne 0) { throw "Server package failed" }

    Write-Host "  -> CAEReportWorker (onedir)..." -ForegroundColor Yellow
    & $python -m PyInstaller --noconfirm --clean --onedir --name CAEReportWorker `
        --distpath $target --workpath (Join-Path $work "worker") `
        --paths "worker/src;shared/python" `
        --add-data "hyperview;hyperview" `
        --runtime-hook $runtimeHook `
        "tools/entrypoints/worker_main.py"
    if ($LASTEXITCODE -ne 0) { throw "Worker package failed" }

    Write-Host "  -> CAEReportDesktop (onefile)..." -ForegroundColor Yellow
    & $python -m PyInstaller --noconfirm --clean --windowed --onefile --name CAEReportDesktop `
        --distpath $target --workpath (Join-Path $work "desktop") `
        --icon "resources/app-icon.ico" `
        --add-data "resources/app-icon.png;resources" `
        --paths "desktop/src;server/src;shared/python" `
        --runtime-hook $runtimeHook `
        "tools/entrypoints/desktop_main.py"
    if ($LASTEXITCODE -ne 0) { throw "Desktop package failed" }

    Write-Host "[5/6] Extracting internal zip archives..." -ForegroundColor Cyan
    $internalZips = Get-ChildItem -LiteralPath $target -Recurse -Filter "*.zip" -File
    foreach ($zipFile in $internalZips) {
        $extractDir = Join-Path $zipFile.DirectoryName "$($zipFile.BaseName)_extracted"
        Write-Host "  Extracting: $($zipFile.Name) -> $extractDir" -ForegroundColor Yellow
        if (Test-Path -LiteralPath $extractDir) {
            Remove-Item -LiteralPath $extractDir -Recurse -Force
        }
        try {
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile.FullName, $extractDir)
        }
        catch {
            Write-Host "  WARNING: Cannot extract $($zipFile.Name), creating empty placeholder" -ForegroundColor Red
            New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
        }
    }

    Copy-Item -LiteralPath "README.md" -Destination $target -Force
    Copy-Item -LiteralPath "docs" -Destination $target -Recurse -Force
    $versionFile = Join-Path $target "version.txt"
    Set-Content -LiteralPath $versionFile -Value $Version -Encoding ASCII

    Write-Host "[6/6] Building installer EXE..." -ForegroundColor Cyan
    $payloadDir = Join-Path $repoRoot "build/installer_payload"
    if (Test-Path -LiteralPath $payloadDir) {
        Remove-Item -LiteralPath $payloadDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $payloadDir -Force | Out-Null
    Get-ChildItem -LiteralPath $target | ForEach-Object {
        if ($_.PSIsContainer) {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $payloadDir $_.Name) -Recurse -Force
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $payloadDir $_.Name) -Force
        }
    }

    $installerName = "CAEReportWorkbench_Setup_$Version.exe"
    $installerOutput = Join-Path $repoRoot "dist" $installerName

    & $python -m PyInstaller --noconfirm --clean --windowed --onefile `
        --name "CAEReportWorkbench_Setup" `
        --distpath (Join-Path $repoRoot "dist") `
        --workpath (Join-Path $work "installer") `
        --icon "resources/app-icon.ico" `
        --add-data "$payloadDir;payload" `
        --hidden-import tkinter `
        --hidden-import tkinter.filedialog `
        --hidden-import tkinter.ttk `
        --hidden-import tkinter.messagebox `
        "tools/installer.py"
    if ($LASTEXITCODE -ne 0) { throw "Installer package failed" }

    $builtInstaller = Join-Path $repoRoot "dist/CAEReportWorkbench_Setup.exe"
    if (Test-Path -LiteralPath $builtInstaller) {
        Write-Host "`n========================================" -ForegroundColor Green
        Write-Host "  Installer built successfully!" -ForegroundColor Green
        Write-Host "  $builtInstaller" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
    } else {
        throw "Installer EXE not found after build"
    }

    Remove-Item -LiteralPath $payloadDir -Recurse -Force -ErrorAction SilentlyContinue
} finally {
    Pop-Location
}
