@echo off
rem Range Trace com janela: escolhe jogo, executavel e modulos (docs/range-trace.md).
rem   abrir_trace_launcher.bat [jogo.range]
start "" pythonw "%~dp0range_trace_launcher.py" %*
