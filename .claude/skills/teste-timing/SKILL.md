---
name: teste-timing
description: Testa o ritmo de frames (frame pacing) da engine no Windows comparando o método spin/sleep com o sleep simples, com e sem o timer de 1 ms, e dá um veredito em linguagem simples. Use quando o usuário pedir para testar timing, FPS, frame drops, pacing ou o ajuste do Kitsuy.
---

# Teste de timing (A/B)

O usuário não é técnico: rode tudo sozinho e responda só com o veredito e uma tabela curta.

## Passos

1. Compile `RangeRuntime` e `RangeEngine` com o skill `build-anastacio` (respeite as regras anti-loop dele).
2. Se `python -c "import psutil"` falhar, rode `python -m pip install psutil` (só mede CPU; sem ele a coluna fica `?`).
3. Feche jogos/editores abertos e, em notebook, deixe na tomada.
4. Rode da raiz do repo: `python tools/timing_ab.py build\bin` (~5 min: 8 execuções de 15 s).
5. Rode uma segunda vez para confirmar. Diferença menor que ~10% entre `mix` e `sleep` é ruído.

## Como ler

Colunas: `fps` (deve ficar ~60), `jitter` (variação do tempo do frame, menor é melhor),
`worst` (pior frame), `late` (frames 50% mais lentos que o normal = engasgos visíveis), `cpu`.

- `timer 15ms` simula Windows antigo / Wine (o caso do Kitsuy). É onde a diferença deve aparecer.
- `mix` (spin/sleep, padrão atual) ganha se tiver menos `late` e `jitter` sem fps menor.
- Custo do `mix`: `cpu` maior. Acima de ~60% em notebook pode esquentar; avise.

## Veredito

- `mix` melhor ou igual em `late`/`jitter` → manter (padrão atual).
- `mix` igual e `cpu` muito maior → sugerir voltar ao `sleep` (trocar o padrão em `KX_KetsjiEngine::WaitUntil`).
- Sem frames no trace → o runtime não abriu ou fechou cedo; rode `build\bin\RangeRuntime` manualmente na cena de `tools/create_fixed_timestep_test.py` para ver o erro.

Variáveis usadas: `RANGE_PACING=sleep` (método antigo), `RANGE_NO_TIMER_RES=1` (desliga `timeBeginPeriod(1)`).
