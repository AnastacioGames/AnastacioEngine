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

	# This CPython wasm build keeps mpdecimal (decimal module) and expat
	# (xml.parsers.expat / plistlib et al.) as separate static libs instead
	# of folding them into libpython3.11.a (see docs/web-python-poc-plan.md).
	# PYTHON_LIBRARIES is what every consumer of Python already links
	# against, so extend it here rather than patching each call site.
	find_library(PYTHON_MPDEC_LIBRARY NAMES mpdec HINTS ${PYTHON_LIBPATH})
	find_library(PYTHON_EXPAT_LIBRARY NAMES expat HINTS ${PYTHON_LIBPATH})
	list(APPEND PYTHON_LIBRARIES ${PYTHON_MPDEC_LIBRARY} ${PYTHON_EXPAT_LIBRARY})
	mark_as_advanced(PYTHON_MPDEC_LIBRARY PYTHON_EXPAT_LIBRARY)
endif()

# SDL2 do Emscripten: o gate de timestamp do gamepad precisa estar removido (entrada presa em ACTIVE no
# navegador). O cache do emsdk fica fora do repo; tools/web/patch-sdl2-gamepad.py e a fonte versionada
# do patch, idempotente. Aplica no configure e avisa se nao der (ex: porta sdl2 ainda nao baixada).
find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
	set(_sdl2_patch "${CMAKE_SOURCE_DIR}/../tools/web/patch-sdl2-gamepad.py")
	if(NOT EXISTS "${_sdl2_patch}")
		set(_sdl2_patch "${CMAKE_SOURCE_DIR}/tools/web/patch-sdl2-gamepad.py")
	endif()
	if(EXISTS "${_sdl2_patch}")
		execute_process(COMMAND ${Python3_EXECUTABLE} ${_sdl2_patch}
		                RESULT_VARIABLE _sdl2_patch_rc OUTPUT_VARIABLE _sdl2_patch_out)
		string(STRIP "${_sdl2_patch_out}" _sdl2_patch_out)
		if(_sdl2_patch_rc EQUAL 0)
			message(STATUS "${_sdl2_patch_out}")
		else()
			message(WARNING "Patch do SDL2 (gamepad) nao aplicado: ${_sdl2_patch_out}\n"
			                "Rode: python tools/web/patch-sdl2-gamepad.py")
		endif()
	endif()
endif()
