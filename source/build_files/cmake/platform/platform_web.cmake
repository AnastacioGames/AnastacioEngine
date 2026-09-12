# Stub exploratorio: NAO funcional. Usado apenas para levantamento de
# informacao sobre o que falta para suportar Web (Emscripten/WebAssembly)
# como plataforma de build (ver docs/web-export-plan.md). Nao faz
# find_package de nada; deixa propositalmente todo mundo "nao encontrado"
# para o CMake apontar, passo a passo, cada dependencia que ainda nao usa
# a porta correspondente do Emscripten (SDL2, OpenAL) ou precisa de ajuste
# (ex.: Python -> alvo oficial wasm32-emscripten via Pyodide).
