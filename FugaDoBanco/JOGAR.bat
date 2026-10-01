@echo off
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -c "import pygame" >nul 2>nul || %PY% -m pip install pygame
%PY% main.py
if errorlevel 1 pause
