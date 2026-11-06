$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Run .\run.ps1 once first to create the virtual environment and install dependencies."
}
& $python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }
$iconAssets = Join-Path $projectRoot "waifu_gallery\assets"
& $python -m PyInstaller --noconfirm --clean --windowed --name "Waifu Gallery" --paths $projectRoot --add-data "$iconAssets;waifu_gallery/assets" --distpath (Join-Path $projectRoot "dist") --workpath (Join-Path $projectRoot "build") (Join-Path $projectRoot "launcher.py")
if ($LASTEXITCODE -ne 0) { throw "Could not build the Windows application." }
Write-Host "Built app: $(Join-Path $projectRoot 'dist\Waifu Gallery\Waifu Gallery.exe')"
