@echo off
rem Sobe a ponte (engine sem janela) e abre o editor Web numa janela de app maximizada.
rem Uso: abrir_editor_web.bat [arquivo.range]
set RAIZ=%~dp0..\..
"%RAIZ%\build\bin\AnastacioEngine.exe" -b %1 --factory-startup --python "%~dp0ponte.py" -- --modelo D:\AnastacioEditorWeb\prototipo\modelo.html --porta 8765 --abrir
