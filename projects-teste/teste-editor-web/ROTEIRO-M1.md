# Roteiro M1: diagnósticos estruturados (Python e shader)

Pendências que só o clique na UI ou um material GLSL real fecham. Use o `editor-web-teste.range` e o
`LEIA-ME.md` desta pasta como base. Anote o texto exato do que falhar.

## A. Importar relatório com erro Python pelo editor
1. Salve como `pf-python.json`:
   ```json
   {"schema": "range-web-preflight", "schema_version": 2,
    "python_errors": [{"kind": "ValueError", "text": "m1-injected-exception",
                       "context": "controller", "origin": "Cube",
                       "traceback": "Traceback (most recent call last): ..."}]}
   ```
2. Painel **Scene > Web (Range)** > **Importar pré-voo Web** > escolha o arquivo.
   - Esperado: aviso "Preflight: 1 problem(s)." e um resultado `WEB-PY-009` na lista.
3. Repita com `"schema_version": 1`: mesmo resultado.
4. Repita com `"schema_version": 3` (ou apagando o campo): um único `WEB-DEPLOY-002`, "Versão do relatório de pré-voo incompatível".
5. Importe `pf-ok.json` (relatório sem problemas): os resultados do pré-voo anterior somem e aparece
   "Preflight found no problems."
6. **Localizar** não aparece nesses resultados (o `origin` do relatório não é um objeto real); isso é esperado.

## B. Execução sem pré-voo (runtime)
1. Exporte o pacote com **auto_preflight** desligado.
2. Sirva (`python serve.py 8080`) e abra a página **sem** `?preflight=1`.
3. Esperado: o jogo roda igual, sem erro no console causado pelo relatório, e `window.rangePreflight` não é exigido.

## C. Falha de vertex/link de shader (vertex testado em 2026-09-20; ver changelog)
Só o fragment do Filter2D foi exercitado. O `shader_quebrado.py` (nesta pasta) injeta um vertex shader inválido
via `getShader().setSource()`, sem montar material pela UI.
0. Atalho: `criar_m1c.py` (`RangeEngine.exe -b --python criar_m1c.py`) gera o `m1c-shader.range` pronto.
1. Copie `shader_quebrado.py` para a pasta do seu `.range` de teste (mesma pasta do arquivo).
2. No `.range`: um Cubo com **qualquer material** (Game Engine > Shading: GLSL). Logic Editor: Sensor **Always**
   (Pulse desligado) > Controller **Python**, Modo **Module**, `shader_quebrado.quebrar` > sem atuador.
3. Salve, **Export Web** com **Preflight after export** ligado.
4. Sirva, abra com `?preflight=1`, clique em Jogar e espere o log `[shader_quebrado] ...` no console.
5. Rode `verify-package.cjs` com `PREFLIGHT_OUT=pf.json` (ou copie o relatório do console) e importe
   no editor com **Import Web preflight**.
6. Esperado: `shader_errors` com stage `vertex`; no editor `WEB-GFX-002` com o log em "fix".
7. Se o log aparecer no console mas `shader_errors` vier vazio, anote o texto exato: é lacuna do coletor.
8. Se `getShader()` devolver None ou o objeto sem material, registre e siga para o M2.
