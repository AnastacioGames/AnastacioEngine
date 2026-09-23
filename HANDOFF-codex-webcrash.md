# Handoff para Codex — crash na carga de .range no build Web (Emscripten)

Estado no commit `e220cd8` (master). Contexto completo da investigação está no
histórico do chat anterior (sessão Claude); resumo do essencial abaixo.

## Objetivo
Diagnosticar (NÃO corrigir ainda) a causa exata do segfault ao carregar
`untitled.range` no RangeRuntime compilado para Web/Emscripten
(`build-web/bin/RangeRuntime.js` + `test.html`). Regra do usuário: só avançar
para correção depois que a operação/estrutura exata que falha for localizada
com instrumentação mínima e temporária. Não alterar DNA nem a lógica de
conversão de ponteiros (`bh4_from_bh8`, `cast_pointer`, `reconstruct_elem` em
`dna_genfile.c`) até a causa ser confirmada.

## O que já foi descartado
- `get_bhead()` (readfile.c): leitura de arquivo e conversão de header
  64→32 bits (`bh4_from_bh8`) confirmadas corretas via contagem exata de
  bytes (442 chamadas, soma bate com o tamanho do arquivo de 350624 bytes).
- `read_file_dna()`: completa com sucesso — `DNA_sdna_from_data`,
  `DNA_struct_get_compareflags` e `DNA_elem_offset` retornam valores válidos
  e não-nulos, função retorna `true`. Bloco `code=826363460` é o DNA1
  legítimo (não corrupção) — `read_file_dna()` retorna assim que acha
  DNA1/DNA2, por isso não há mais `get_bhead()` depois disso nessa fase.
- Thumbnail (`TEST` block, `len=65544`): bate exatamente com
  `BLEN_THUMB_MEMSIZE_FILE(128,128)`, ou seja, é um thumbnail 128x128
  legítimo — não é fonte óbvia de overflow.

## Suspeito atual
`read_libblock()` (readfile.c, ~linha 8420) e o loop principal de
`blo_read_file_internal()` — responsáveis pela reconstrução real de cada
ID/struct via SDNA. Foi adicionada instrumentação de entrada em ambos
(prints de `bhead->code/len/SDNAnr/nr`), já compilada com sucesso
(`build-web-log30.txt`, exit 0).

## Instrumentação ativa (temporária, marcada `WITH_TEMP_GETBHEAD_DEBUG`)
- Flag: `source/CMakePresets.json`, preset `web-runtime`,
  `CMAKE_C_FLAGS` termina em `-DWITH_TEMP_GETBHEAD_DEBUG`.
- Código: `source/source/blender/blenloader/intern/readfile.c`, blocos
  `#ifdef WITH_TEMP_GETBHEAD_DEBUG` em `get_bhead()`, `read_file_dna()`,
  `blo_read_file_internal()` (topo do `while(bhead)`) e `read_libblock()`
  (entrada da função).
- **Lembrete explícito do usuário**: remover toda essa instrumentação e a
  flag de build ao concluir o diagnóstico.

## Pendência imediata (onde parei)
A última tentativa de capturar o log completo do Chrome headless
(`chrome-profile-web-test11` → `chrome-dump11.html` /
`chrome-console-log11.txt`) **não deu certo**: `chrome-dump11.html` ficou
com 0 bytes (o `--dump-dom` não chegou a produzir saída — o processo deve
ter estourado o timeout ou travado antes de finalizar, provavelmente pelo
volume bem maior de `printf` por causa da instrumentação no loop principal
disparando para cada bloco/ID). `chrome-console-log11.txt` só tem logs de
inicialização do Chrome, nada do harness.

### Próximo passo sugerido
1. Repetir a captura com `--virtual-time-budget` maior (o valor usado nas
   rodadas anteriores pode não ser suficiente com o volume de log extra) e/ou
   rodar em background desde o início com timeout generoso.
2. Se o volume de print for o problema, considerar reduzir a instrumentação
   do loop principal (por exemplo, só logar quando o código do bloco não for
   um dos "skip" — `DATA/DNA1/DNA2/TEST/REND` — já que esses são a maioria
   dos blocos e não vão para `read_libblock()` mesmo).
3. Depois de capturar o dump completo, extrair as linhas
   `[blo_read_file_internal] main-loop ...` e `[read_libblock] enter ...`
   (mesmo padrão usado para `chrome-dump9.html`/`chrome-dump10.html`) e
   identificar o último bloco processado antes da linha `[ABORT]
   segmentation fault`.
4. Só depois disso, com o bloco/ID identificado, investigar dentro de
   `read_libblock()` (ou na sub-rotina de reconstrução daquele tipo de
   struct) qual operação específica falha — com instrumentação mínima
   adicional, sempre evitando alterar DNA ou a conversão de ponteiros.

## Ambiente de teste (para reproduzir)
- Servir `build-web/bin/` com `python -m http.server 8765`.
- Headless Chrome:
  `"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless
  --disable-gpu --no-sandbox --enable-logging=stderr --v=1
  --virtual-time-budget=<N> --user-data-dir=<dir novo>
  --dump-dom http://localhost:8765/test.html`
  stdout → `chrome-dumpN.html`, stderr → `chrome-console-logN.txt`.
- Rebuild após mudar `CMakePresets.json`: rodar de `source/`:
  `cmake --preset web-runtime` depois
  `cmake --build --preset web-runtime --target <alvo>`.

## Regras que continuam valendo (não mudar sem pedido explícito)
- `USE_RNA_RANGE_CHECK` em `rna_internal.h`: excluído no Emscripten como
  workaround documentado, não mexer/"resolver" isso agora.
- Licença do projeto: fixa, não sugerir/alterar.
- Não editar `docs/web-integration-audit.md` (documento do Codex).
- Não commitar sem pedido explícito do usuário (a instrumentação atual já
  foi commitada a pedido, ver commit `e220cd8`).
- Limpezas pendentes para quando o diagnóstico fechar: remover o preload
  TEMP de `untitled.range` em `blenderplayer/CMakeLists.txt` (linhas
  marcadas `# TEMP`), decidir sobre manter/remover `-sSAFE_HEAP=1
  -sASSERTIONS=2 -g2`, remover toda a instrumentação
  `WITH_TEMP_GETBHEAD_DEBUG`, reverter scaffolding de teste em `test.html`.
