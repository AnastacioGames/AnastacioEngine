@echo off
rem Game Trace com janela: escolhe jogo, executavel e modulos (docs/game-trace.md).
rem   abrir_trace_launcher.bat [jogo.range]
start "" pythonw "%~dp0game_trace_launcher.py" %*
