@echo off
rem Range Trace: abre um jogo no player gravando o que carrega e o que e desenhado (docs/range-trace.md).
rem   abrir_trace.bat [jogo.range] [modulos]
rem Modulos: load,usage (padrao: todos). Jogue o trecho que quer examinar e feche o jogo normalmente;
rem o relatorio (relatorio.html + resumo.md) e gerado e aberto ao fechar.
rem Saida: debug-logs\trace-<data-hora>\ na raiz do repositorio.
setlocal
set ROOT=%~dp0..\..
set GAME=D:\ProjetoRolimaRacer\RolimaRacer.range
if not "%~1"=="" set GAME=%~f1
set RANGE_TRACE_MODULES=all
if not "%~2"=="" set RANGE_TRACE_MODULES=%~2
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT=%ROOT%\debug-logs\trace-%STAMP%
mkdir "%OUT%"
set RANGE_TRACE=%OUT%
for %%f in ("%GAME%") do cd /d "%%~dpf"
echo Trace em %OUT% (modulos: %RANGE_TRACE_MODULES%). Feche o jogo para gerar o relatorio.
start "" /wait "%ROOT%\build\bin\AnastacioRuntime.exe" "%GAME%"
python "%ROOT%\tools\debug\relatorio_trace.py" "%OUT%"
if exist "%OUT%\relatorio.html" start "" "%OUT%\relatorio.html"
