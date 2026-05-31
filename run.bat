@echo off
REM ============================================================
REM  BMW Deal Scanner - Dauerlauf (scannt alle X Minuten)
REM ============================================================
cd /d "%~dp0"
python scanner.py --loop
pause
