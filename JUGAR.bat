@echo off
rem Demo todo-en-uno: doble click = simulador + plataforma + navegador + puntaje.
rem Opciones extra: JUGAR.bat --acelerar 60
cd /d "%~dp0"
python demo.py %*
pause
