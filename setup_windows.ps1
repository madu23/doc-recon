$ErrorActionPreference = "Stop"
Write-Host "Creating DocRecon virtual environment..."
py -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
Write-Host ""
Write-Host "Python dependencies installed."
Write-Host "Now verify Tesseract is installed: tesseract --version"
Write-Host "If Windows cannot find it, set ocr.tesseract_cmd in config.json."
