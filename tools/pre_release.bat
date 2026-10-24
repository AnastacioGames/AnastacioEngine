@echo off
rem Conferencia local antes de publicar release (Windows).
rem Compila editor+player, instala em build\bin, roda checks de docs/icones,
rem testa o player headless (--server) e roda ctest se configurado.
rem Para no primeiro erro. Uso: tools\pre_release.bat
setlocal
set ROOT=%~dp0..
set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat
set VSLANG=1033

echo == 1/5 Compilando RangeEngine e RangeRuntime
call "%VCVARS%" >nul || goto :falha_vcvars
cd /d "%ROOT%\build" || goto :falha
ninja RangeEngine RangeRuntime || (set ETAPA=ninja& goto :falha)

echo == 2/5 Instalando em build\bin
ninja install || (set ETAPA=ninja install& goto :falha)

echo == 3/5 Checks de docs e icones
cd /d "%ROOT%"
python tools\check_docs.py || (set ETAPA=check_docs& goto :falha)
python tools\check_ui_icons.py || (set ETAPA=check_ui_icons& goto :falha)

echo == 4/5 Smoke test do player headless (10 s)
rem Se o player fechar sozinho com erro antes de 10 s, falha; se seguir rodando, e encerrado.
powershell -NoProfile -Command "$p=Start-Process -FilePath '%ROOT%\build\bin\AnastacioRuntime.exe' -ArgumentList '--server','%ROOT%\tools\debug\cenas\ui_tree_proto.range' -PassThru -WindowStyle Hidden; if($p.WaitForExit(10000)){ if($p.ExitCode -ne 0){ exit 1 } } else { $p.Kill() }; exit 0" || (set ETAPA=smoke test do player& goto :falha)

echo == 5/5 ctest
if exist "%ROOT%\build\CTestTestfile.cmake" (
  cd /d "%ROOT%\build"
  ctest --output-on-failure || (set ETAPA=ctest& goto :falha)
) else (
  echo ctest nao configurado em build\, pulando.
)

echo.
echo PRE-RELEASE OK
exit /b 0

:falha_vcvars
set ETAPA=vcvars64.bat (Visual Studio nao encontrado)
:falha
echo.
echo PRE-RELEASE FALHOU na etapa: %ETAPA%
exit /b 1
