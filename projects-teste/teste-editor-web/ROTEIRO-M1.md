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

## C. Falha de vertex/link de shader (não testado)
Só o fragment do Filter2D foi exercitado. Para cobrir vertex/link é preciso um material GLSL que falhe:
1. Cena com **Game Engine > Shading: GLSL** e um material cujo shader seja inválido (por exemplo, nó de script
   ou GLSL customizado com sintaxe quebrada), usado em um objeto visível.
2. Exporte e rode `verify-package.cjs` com `PREFLIGHT_OUT=pf.json`.
3. Esperado no JSON: `shader_errors` com `stage` `vertex` ou `link` e o nome do material; importado no editor
   vira `WEB-GFX-002` com o log em "fix".
4. Se não houver como montar esse material pela UI, registre "não testado" no changelog e siga para o M2.
