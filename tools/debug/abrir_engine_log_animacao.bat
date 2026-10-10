@echo off
rem Abre o editor com o log de tempo das animacoes (RANGE_ANIM_LOG, ver docs/engine-profiling.md).
rem O log vai para debug-logs\anim_log.txt na raiz do repositorio e e apagado a cada abertura.
set ROOT=%~dp0..\..
if not exist "%ROOT%\debug-logs" mkdir "%ROOT%\debug-logs"
set RANGE_ANIM_LOG=%ROOT%\debug-logs\anim_log.txt
if exist "%RANGE_ANIM_LOG%" del "%RANGE_ANIM_LOG%"
cd /d "%ROOT%\debug-logs"
start "" "%ROOT%\build\bin\AnastacioEngine.exe" %*
