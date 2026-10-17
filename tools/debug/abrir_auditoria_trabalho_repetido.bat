@echo off
rem Detector de trabalho repetido por frame num jogo real (docs/auditoria-trabalho-repetido.md).
rem Gera uma copia do jogo com o medidor (o original nao muda), abre no player e mede ate fechar.
rem Jogue ate a cena que interessa, fique ~10 s parado, depois ande ~10 s e feche o jogo.
rem Log em debug-logs\auditoria-<data-hora>\contadores.txt (parado: contadores devem ficar ~0).
rem Outro jogo: arraste o .range/.blend sobre este .bat ou passe o caminho como argumento.
set ROOT=%~dp0..\..
set GAME=D:\ProjetoRolimaRacer\RolimaRacer.range
if not "%~1"=="" set GAME=%~f1
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT=%ROOT%\debug-logs\auditoria-%STAMP%
mkdir "%OUT%"
for %%f in ("%GAME%") do set COPY=%%~dpf_audit_copy%%~xf
"%ROOT%\build\bin\AnastacioEngine.exe" -b "%GAME%" --python "%ROOT%\tools\debug\auditar_trabalho_repetido.py" -- "%COPY%" "%OUT%\contadores.txt"
for %%f in ("%GAME%") do cd /d "%%~dpf"
set AUDIT_SECONDS=0
rem Syncs de transform e raizes atualizadas por objeto, a cada segundo (CM_WorkCounters.h).
set RANGE_AUDIT_TRANSFORMS=%OUT%\objetos.txt
"%ROOT%\build\bin\AnastacioRuntime.exe" "%COPY%"
del "%COPY%" "%COPY%1" 2>nul
echo Log em %OUT%\contadores.txt
