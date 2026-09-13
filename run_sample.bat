@echo off
setlocal
.venv\Scripts\python.exe scripts\generate_synthetic_samples.py
.venv\Scripts\docrecon.exe --input samples\input\sample_input.xlsx --pods samples\pods --output output --dry-run
endlocal
