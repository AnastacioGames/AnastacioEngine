---
name: build-anastacio
description: Compila o AnastacioEngine (CMake+Ninja) corretamente via vcvars64.bat, seguindo as regras anti-loop do AGENTS.md. Use sempre que precisar compilar/testar uma mudança de C++ neste repo.
---

# Build do AnastacioEngine

A fonte canônica das regras é [AGENTS.md](../../../AGENTS.md) — leia lá antes de tudo, especialmente a seção "Regra anti-loop" e "Ambiente de build". Este skill só resume o comando pronto para não reinventar toda vez.

## Comando de build

Um shell puro (PowerShell, git-bash, cmd) NÃO compila este repo — falta o ambiente do MSVC. Rode `vcvars64.bat` e `ninja` na MESMA chamada:

```
cmd /c '"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cd /d D:\AnastacioEngine\build && ninja <target> 2>&1'
```

Alvos úteis para checagem rápida: `ge_rasterizer`, `ge_rasterizer_opengl`, `ge_rasterizer_shaders` (rebuild depois de editar `.glsl`).
Executáveis completos: `RangeEngine` (editor), `RangeRuntime` (player, aceita `.range` como argumento). Saída em `build/bin/`.

## Antes de repetir um comando que falhou

Não rode a mesma coisa 3x esperando resultado diferente. Siga o checklist do AGENTS.md:
1. Passou pelo vcvars64.bat?
2. Erro idêntico 2x seguidas? Pare e mude de estratégia.
3. Editou algum header (`.h`, especialmente `DNA_*.h`)? Se depois do fix o erro mudar de cara (crash estranho, `STATUS_HEAP_CORRUPTION`), rode `ninja -t clean` e rebuild completo (~45-50min) em vez de debugar como bug de código.
4. Depois de 2 tentativas falhas no mesmo erro, pare e pergunte ao usuário — não continue tentando variações sozinho.
5. Nunca marque como concluído sem build/execução bem-sucedidos; se o ambiente não permitir compilar, diga isso explicitamente como bloqueio.
