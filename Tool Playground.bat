@echo off
cd /d "%~dp0"
uv run python scripts/tool_playground.py
if errorlevel 1 pause
