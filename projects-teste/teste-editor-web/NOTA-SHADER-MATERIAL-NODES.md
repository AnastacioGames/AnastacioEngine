# Falha injetável em material de nós

Não há, nesta versão da engine, uma API Python para fornecer GLSL arbitrário a um material de nós. O grafo é convertido por `gpu_codegen.c` em fontes internas e a API de material aceita nós conhecidos; um grafo inválido é validado/normalizado antes de alcançar `glCompileShader`.

Assim, não é possível construir um `.range` que force de modo determinístico uma falha de compilação no shader **gerado** por um material de nós sem alterar C/C++ ou corromper os fontes gerados, ambos fora do escopo desta frente. `criar_m1c.py` já prova o transporte de erros de shader e `MatQuebradoLink` prova o evento de link; o fixture `tools/tests/web_profile/fixtures/preflight-link.json` fixa o contrato estruturado de link sem estágio, que é o formato emitido quando a falha não pertence a vertex/fragment/geometry.
