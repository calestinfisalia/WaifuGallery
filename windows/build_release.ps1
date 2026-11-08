$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$releaseDir = Join-Path $projectRoot "dist-release"
$assetDir = Join-Path $projectRoot "waifu_gallery\assets"
$appVersionFile = Join-Path $projectRoot "waifu_gallery\__init__.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Run .\run.ps1 once first to create the virtual environment and install dependencies."
}

$versionMatch = [regex]::Match((Get-Content -LiteralPath $appVersionFile -Raw), '__version__\s*=\s*"([^"]+)"')
if (-not $versionMatch.Success) { throw "Could not read the app version from waifu_gallery\__init__.py." }
$appVersion = $versionMatch.Groups[1].Value
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

Write-Host "Building the folder bundle used by Setup..."
& (Join-Path $projectRoot "build_windows.ps1")
if ($LASTEXITCODE -ne 0) { throw "The folder build failed." }

$portableOutput = Join-Path $releaseDir "WaifuGallery-Portable-x64.exe"
Write-Host "Building the single-file portable executable..."
& $python -m PyInstaller `
    --noconfirm --clean --onefile --windowed `
    --icon (Join-Path $assetDir "waifugallery.ico") `
    --name "WaifuGallery-Portable-x64" `
    --paths $projectRoot `
    --add-data "$assetDir;waifu_gallery/assets" `
    --distpath $releaseDir `
    --workpath (Join-Path $projectRoot "build\portable") `
    --specpath $projectRoot `
    (Join-Path $projectRoot "launcher.py")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $portableOutput)) {
    throw "Could not build the portable executable."
}

$innoSetupCompiler = Join-Path ([Environment]::GetFolderPath("ProgramFiles")) "Inno Setup 7\ISCC.exe"
if (-not (Test-Path -LiteralPath $innoSetupCompiler)) {
    $innoSetupCompiler = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Inno Setup 7\ISCC.exe"
}
if (-not (Test-Path -LiteralPath $innoSetupCompiler)) {
    throw "Inno Setup 7 compiler (ISCC.exe) was not found. Install Inno Setup 7, then run this script again."
}

Write-Host "Building the update-aware installer..."
& $innoSetupCompiler `
    "/DAppVersion=$appVersion" `
    "/DWindowsDistDir=$(Join-Path $projectRoot 'dist\Waifu Gallery')" `
    "/DOutputDir=$releaseDir" `
    (Join-Path $projectRoot "setup_windows.iss")
if ($LASTEXITCODE -ne 0) { throw "Could not build the setup executable." }

Write-Host "Release files:"
Get-Item $portableOutput, (Join-Path $releaseDir "WaifuGallery-Setup-x64.exe") |
    Select-Object FullName, Length, LastWriteTime |
    Format-Table -AutoSize
