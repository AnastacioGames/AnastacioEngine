@echo off
rem Abre o RolimaRacer no player com o profiler da engine (RANGE_PROFILE) e o log de shaders,
rem texturas e imagens (RANGE_SHADER_LOG). Ver docs/engine-profiling.md.
rem Jogue normalmente (menu, corrida, ragdoll) e feche o jogo; os logs ficam em
rem debug-logs\perfil-rolima-<data-hora>\ na raiz do repositorio.
rem Outro .range: arraste o arquivo sobre este .bat ou passe o caminho como argumento.
set ROOT=%~dp0..\..
set GAME=D:\ProjetoRolimaRacer\RolimaRacer.range
if not "%~1"=="" set GAME=%~f1
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT=%ROOT%\debug-logs\perfil-rolima-%STAMP%
mkdir "%OUT%\tmp"
set RANGE_PROFILE=%OUT%\profile.txt
set RANGE_SHADER_LOG=%OUT%\shaders.txt
rem Diagnostico opt-in dos scripts do RolimaRacer; outros jogos ignoram a variavel.
set ROLIMA_RAGDOLL_TRACE=%OUT%\ragdoll.jsonl
rem O player grava range_runtime.log.txt no TEMP: uma pasta por rodada.
set TEMP=%OUT%\tmp
set TMP=%OUT%\tmp
for %%f in ("%GAME%") do cd /d "%%~dpf"
start "" "%ROOT%\build\bin\AnastacioRuntime.exe" "%GAME%"
echo Logs em %OUT%
