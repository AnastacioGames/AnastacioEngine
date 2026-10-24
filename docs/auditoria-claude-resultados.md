# Auditoria: resultados do Claude (GL5-GL10, RA4)

Lote de auditoria GL (branches `claude/auditoria-gl` e `claude/auditoria-gl7`). Estados finais em
[auditoria-suspeitos.md](auditoria-suspeitos.md).

## Fechados

- GL5 — `SCA_PropertyActuator` criava parser por ativação: corrigido; literais guardam a árvore. Cena
  `criar_cena_gl.py` (300 empties, 1800 atuadores): 1,82 → 1,26 ms/frame (-31%), resultados idênticos.
  Conversão do ramo runtime property não cacheada (custo pequeno, pouco usado).
- GL6 — `SCA_PropertySensor`: falso positivo; só o `GetText()` duplicado do Changed foi corrigido.
- GL7 — cone Gaze do `KX_RaySensor`: corrigido; cossenos em vez de `acos`. Cena `gl7.range` (2116 cubos,
  40 sensores): 8,89 → 7,86 ms (~12%), mesmos alvos. O laço segue O(objetos) por sensor (recurso raro).
- GL8 — `SynchronizeTransform` de Near/Radar: falso positivo prático neste lote; o estado final (corrigido em
  2026-10-09) está em auditoria-suspeitos.md.
- GL9 — `SCA_TimeEventManager`: falso positivo prático; retorno cedo sem propriedades Timer.
- GL10 — `SCA_KeyboardSensor`/`SCA_MouseManager`: corrigido; lookup de toggle vazio pulado, um laço só, mouse
  lido uma vez.
- RA4 — VBO de instancing reenviado em repouso: corrigido; revisão global `uint64_t` evita ABA. Cena
  `criar_cena_ra4_instancing.py`: 1 upload inicial, 0 em repouso, 1 por mudança. Sem benchmark de FPS.

## Aberto

- **RA4, cena de teste:** o player não fecha após `endGame()` em `criar_cena_ra4_instancing.py`. Não
  investigado.
