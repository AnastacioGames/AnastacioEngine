# Auditoria da emulação OpenGL para o port Web

Data: 2026-09-13. Destinatário: Claude / responsável pela integração Web.

## Conclusão

A camada que pode poupar adaptações é a do próprio Emscripten, mas
`LEGACY_GL_EMULATION=1` **já está habilitada**. Acrescentar `FULL_ES3=1` ao
build atual é uma recomendação incorreta: o SDK 6.0.9 instalado rejeita a
combinação. A análise encontrou uma incompatibilidade reproduzível entre
a sequência de unbind da engine e o VAO emulado, mais útil para investigar
o bloqueio atual do que trocar flags.

Não foram alterados renderer, presets, SDK ou artefatos gerados. Não houve
build nem nova execução da engine. Houve execução bem-sucedida de um probe
JavaScript com wrappers extraídos do artefato existente e contexto GL simulado.
Isso confirma o mecanismo abaixo, não a resolução completa do jogo no navegador.

## Evidências de configuração

- `source/CMakePresets.json:144–146`, `build-web/CMakeCache.txt:70` e
  `build-web/build.ninja`: WebGL mínimo/máximo 2, `LEGACY_GL_EMULATION=1`,
  `GL_UNSAFE_OPTS=0`, `ASSERTIONS=2`; sem `FULL_ES2`/`FULL_ES3` explícitos.
- O objeto `RAS_StorageVao.cpp.o` está configurado com `WITH_GL_PROFILE_CORE`.
- `D:/emsdk/upstream/emscripten/emscripten-version.txt`: `6.0.9`.
- `D:/emsdk/upstream/emscripten/src/lib/libglemu.js:7–9` contém as verificações
  `assert(!FULL_ES2, 'cannot emulate both ES2 and legacy GL')` e
  `assert(!FULL_ES3, 'cannot emulate both ES3 and legacy GL')`.
- `tools/link.py:1491–1492` nesse SDK faz `FULL_ES3` habilitar `FULL_ES2`.
  O cache usa um caminho virtual `/upstream/emscripten`; não se presume que
  ele identifique fisicamente o SDK Windows. A lógica relevante também foi
  conferida no JavaScript efetivamente gerado.

## VAO emulado: mecanismo reproduzido

Em `RAS_StorageVao.cpp`, o construtor cria/binda o VAO, vincula VBO e IBO,
configura `glVertexAttribPointer` com **offsets no VBO**, e ao final chama
`UnbindVertexBuffer()` **antes** de `GPU_unbind_vertex_array()`.

No JavaScript existente:

1. O wrapper de `glBindBuffer` (`RangeRuntime.js:9641`) grava todo bind de
   ARRAY_BUFFER em `GLEmulation.currentVao.arrayBuffer`, inclusive o bind 0.
2. Portanto, o unbind ainda dentro do VAO apaga a referência ao VBO emulado.
3. `emulGlBindVertexArray` (`:13284`) restaura `info.arrayBuffer` e reaplica
   os ponteiros. Nesse caso reaplica offsets com ARRAY_BUFFER 0.
4. O mesmo artefato define `emscripten_glBindVertexArray` chamando
   `emulGlBindVertexArray`. O prefixo `emscripten_gl` **não contorna a
   emulação legacy de VAO** nesta configuração. Conferir
   `source/source/blender/gpu/intern/gpu_vertex_array.c`.

Há a mesma ordem de unbind no construtor de
`RAS_OpenGLRasterizer::ScreenPlane` (`RAS_OpenGLRasterizer.cpp:158–162`).

Probe reproduzível, a partir da raiz do repositório, em PowerShell:

```powershell
& D:/emsdk/node/24.19.0_64bit/node.exe tools/web_gl_emulation_probe.cjs build-web/bin/RangeRuntime.js
```

Resultado observado, exit 0:

```text
existing: recordedVbo=0; vertexAttribPointer: no ARRAY_BUFFER
control:  recordedVbo=7; errors=[]
PASS: wrapper-state issue reproduced; browser validation still required
```

O controle muda somente a ordem simulada: desvincula o VAO antes do VBO.
O probe extrai os wrappers reais; simula o contexto GL e um atributo com
offset não zero. Não executa o C++/Wasm, shaders, draw ou driver.
SHA256 do JS analisado:
`B188915D8AE3AC1FBE6BDA61745215256E5EB4B2C3419ADE18EFE8BAF6B1A168`.

O log já existente `shader-test4.log:325–328` registra
`vertexAttribPointer: no ARRAY_BUFFER is bound and offset is non-zero` e
`drawElements: no buffer is bound to enabled attribute`, coerentes com esse
mecanismo. Ainda falta confirmar a pilha/VAO responsável no jogo.

## Segundo problema a manter separado

`shader-test4.log:231–233` também registra buffers de alvo não-ELEMENT usados
como ELEMENT_ARRAY_BUFFER. O local apontado é `ras_gl_bind_buffer_webgl`.
Em `RAS_OpenGLDebugDraw.cpp:38`, esse helper chama `GLctx.bindBuffer`
diretamente, enquanto VAOs e atributos continuam passando por wrappers.
Ele não atualiza o estado espelhado de bindings do Emscripten/VAO emulado.

Essa mistura exige inspeção dos IDs e targets; **não foi demonstrado que a
troca da ordem de unbind resolve esse segundo erro**. Não generalizar o
helper direto para o renderer inteiro como solução. VAOs nativos e emulados
também não devem compartilhar IDs como se fossem a mesma tabela.

## Onde FULL_ES3 pode poupar uma adaptação real

`RAS_StorageVbo::GetIndexMap` (`RAS_StorageVbo.cpp:128`) usa
`glMapBufferRange` com `GL_MAP_WRITE_BIT | GL_MAP_INVALIDATE_BUFFER_BIT`;
`FlushIndexMap` usa `glUnmapBuffer`. O chamador em `RAS_MeshSlot.cpp:95`
usa isso para `m_zsort` / `SortPolygons`.

O SDK instalado implementa esse padrão de escrita/invalidação em
`src/lib/libwebgl.js:4172`, dentro de `#if FULL_ES3`. Portanto, é um benefício
concreto possível **depois de uma migração deliberada para fora do legacy**.
Não é prova de que o cubo atual precise dele nem correção de VAO.

Além disso, `source/extern/glew-es/include/GL/glew.h:2257,4951` mapeia essas
funções para ponteiros GLEW. Habilitar emulação não garante que a engine
alcance as entradas corretas; conferir resolução/remapeamento no Web.
Uma alternativa localizada é ordenar índices na CPU e atualizar o IBO com
`glBufferSubData`, a ser avaliada pelo responsável, sem mudar flags globais.

## Próxima ação recomendada ao Claude

1. Conferir se os arquivos/artefato ainda correspondem a esta análise.
2. Instrumentar o primeiro bind/replay problemático e identificar VAO/VBO/IBO.
3. Testar isoladamente a ordem VAO-unbind antes de VBO-unbind nos dois
   construtores indicados, mantendo o restante da configuração.
4. Recompilar com o ambiente correto e confirmar logs no navegador. Investigar
   separadamente o erro de target do DebugDraw se persistir.
5. Validar o cubo real com Python e teclado; depois transparência/zsort.
   Ausência de erros no probe não substitui esse aceite.

Não remover `LEGACY_GL_EMULATION` nem adicionar `FULL_ES3` como experimento
cego: há helpers legados ainda usados. `gpu_shader.c:249` já documenta um
contorno para interferência do wrapper legacy em `glShaderSource`.

## Referências externas

- [Emscripten: suporte OpenGL](https://emscripten.org/docs/porting/multimedia_and_graphics/OpenGL-support.html):
  distingue o subconjunto WebGL, emulação ES e suporte parcial ao GL antigo.
- [Emscripten: FULL_ES3](https://emscripten.org/docs/tools_reference/settings_reference.html#full-es3):
  descreve emulação adicional de ES3; não significa suporte integral ao GL desktop.
- [SDK 6.0.9: libglemu.js](https://github.com/emscripten-core/emscripten/blob/6.0.9/src/lib/libglemu.js):
  referência versionada para comparar as guardas e a implementação local.

A recomendação anterior na conversa de simplesmente considerar FULL_ES3
sem verificar sua incompatibilidade com legacy fica corrigida por esta auditoria.
