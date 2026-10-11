@echo off
rem Abre o editor com o log de shaders/texturas (RANGE_SHADER_LOG), que tambem mede cada troca de layer
rem (linhas "layer_switch"). O log vai para debug-logs\layer_log.txt e e apagado a cada abertura.
set ROOT=%~dp0..\..
if not exist "%ROOT%\debug-logs" mkdir "%ROOT%\debug-logs"
set RANGE_SHADER_LOG=%ROOT%\debug-logs\layer_log.txt
if exist "%RANGE_SHADER_LOG%" del "%RANGE_SHADER_LOG%"
cd /d "%ROOT%\debug-logs"
start "" "%ROOT%\build\bin\AnastacioEngine.exe" %*
