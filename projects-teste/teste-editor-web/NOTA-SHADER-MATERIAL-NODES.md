# Falha injetável em material de nós

**Correção (2026-10-04):** a versão anterior desta nota dizia que não havia como fornecer GLSL a um material de nós
sem alterar C/C++. Há: o material tem `script_frag` e `script_vert` (painel Shading > Shader Sources), dois Texts
com GLSL de usuário. `gpu_material_construct_end` (`gpu_material.c`) passa esses Texts a `GPU_generate_pass`, também
quando o material vem de `ntreeGPUMaterialNodes`, e `code_generate_fragment`/`code_generate_vertex` (`gpu_codegen.c`)
os acrescentam ao fragment e ao vertex gerados a partir do grafo. Um erro de sintaxe ali faz o shader do material de
nós falhar no `glCompileShader`, com a origem `MA<nome do material>` em `Module.onDiagnostic`.

- Cena: `criar_m1c_nos.py` (`RangeEngine.exe -b --python criar_m1c_nos.py -- fragment|vertex|link`) grava
  `m1c-nos-<modo>.range`, sem controller Python; a falha ocorre ao converter o material no carregamento.
- Execução no navegador: roteiro D em `ROTEIRO-M1.md` (usa `claude_m1c_diag.cjs`).
- Teste unitário: `tools/tests/web_profile/test_preflight_node_material.py` fixa o formato do relatório e guarda o
  caminho de injeção acima (falha se o codegen deixar de acrescentar o GLSL de usuário).
- Limite: em material de nós o `fragment()` do usuário é declarado e anexado, mas não é chamado (só o caminho BI liga
  `user_get`). O modo `link` depende de o navegador reprovar varyings de tipos diferentes mesmo sem uso no fragment;
  se não reprovar, isso é resultado a registrar, não falha do coletor.
