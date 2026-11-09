$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    py -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python virtual environment." }
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Could not install pip in the virtual environment." }
}
& $python -m pip install -r (Join-Path $projectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install project dependencies." }
& $python -m waifu_gallery
