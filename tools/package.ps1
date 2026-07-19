[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist/package"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create .venv and install project dependencies first."
}

Push-Location $repoRoot
try {
    npm --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    & $python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed" }
    & $python -m mypy
    if ($LASTEXITCODE -ne 0) { throw "mypy failed" }
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

    & $python -m PyInstaller --noconfirm --clean --onedir --name CAEReportServer `
        --distpath $target --workpath (Join-Path $work "server") `
        --paths "server/src;shared/python" --add-data "frontend/dist;frontend/dist" `
        "tools/entrypoints/server_main.py"
    if ($LASTEXITCODE -ne 0) { throw "Server package failed" }
    & $python -m PyInstaller --noconfirm --clean --onedir --name CAEReportWorker `
        --distpath $target --workpath (Join-Path $work "worker") `
        --paths "worker/src;shared/python" --add-data "hyperview;hyperview" `
        "tools/entrypoints/worker_main.py"
    if ($LASTEXITCODE -ne 0) { throw "Worker package failed" }
    & $python -m PyInstaller --noconfirm --clean --windowed --onefile --name CAEReportDesktop `
        --distpath $target --workpath (Join-Path $work "desktop") `
        --icon "resources/app-icon.ico" --add-data "resources/app-icon.png;resources" `
        --paths "desktop/src;server/src;shared/python" "tools/entrypoints/desktop_main.py"
    if ($LASTEXITCODE -ne 0) { throw "Desktop package failed" }

    Copy-Item -LiteralPath "README.md" -Destination $target -Force
    Copy-Item -LiteralPath "docs" -Destination $target -Recurse -Force
    Compress-Archive -Path (Join-Path $target "*") -DestinationPath (Join-Path $repoRoot "dist/CAEReportWorkbench-0.1.0-win64.zip") -Force
} finally {
    Pop-Location
}
