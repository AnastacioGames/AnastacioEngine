# Stub exploratorio: NAO funcional para a maioria das dependencias. Usado
# para levantamento de informacao sobre o que falta para suportar Web
# (Emscripten/WebAssembly) como plataforma de build (ver
# docs/web-export-plan.md). Nao faz find_package de nada por padrao; deixa
# propositalmente todo mundo "nao encontrado" para o CMake apontar, passo a
# passo, cada dependencia que ainda nao usa a porta correspondente do
# Emscripten (SDL2, OpenAL).
#
# Excecao: Python. Etapa 6 do PoC (docs/web-python-poc-plan.md e
# docs/web-python-manifest.md) cross-compilou CPython 3.11 para
# wasm32-emscripten fora do fluxo find_package normal (sem pacotes de
# sistema para procurar); os artefatos ficam num diretorio Unix-like
# reconhecido por FindPythonLibsUnix.cmake, apontado via PYTHON_ROOT_DIR.
if(WITH_PYTHON)
	find_package(PythonLibsUnix REQUIRED)
endif()
