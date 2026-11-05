# Plano: Game Trace diz como corrigir (Trace Doctor)

Hoje o relatório do [Game Trace](game-trace.md) aponta o culpado provável de cada frame lento. Este plano
acrescenta **como corrigir**, primeiro só no relatório e depois como sugestões que o
[Scene Doctor](../source/release/scripts/startup/bl_operators/anastacio_scene_doctor.py) aplica e desfaz no editor.

Regra geral: uma sugestão só aparece quando o trace tem os dados para ela. Se falta um dado, a regra fica
calada e o relatório diz qual dado falta. Nenhum número é estimado sem medição.

## Etapa 1: sugestões no relatório (feita e aprovada em 2026-11-05)

Em `tools/debug/relatorio_trace.py`, uma tabela de regras `sintoma -> sugestão`. Cada regra lê eventos que o
trace já grava e produz itens `(regra, alvo, sugestão, vezes, ms medidos)`. Itens iguais (mesma regra e mesmo
alvo) são somados. O relatório mostra:

- uma seção **Como corrigir** no `relatorio.html` e no `resumo.md`, agrupada por objeto, imagem, script ou
  shader, com quantas vezes cada sugestão apareceu e o ganho estimado;
- uma coluna **como corrigir** na tabela de frames lentos, ligada ao culpado de cada frame.

O **ganho estimado** é o tempo medido do próprio sintoma: a soma dos ms de cada carga (é a travada que some
se a carga sair do jogo) ou a média em ms por frame de um script. Não é uma previsão do frame depois da correção.

| Regra | Sintoma (evento do trace) | Sugestão | Ganho |
|---|---|---|---|
| imagem | `image` depois do frame 5, ≥ 1 ms (módulo `usage`) | pré-carregar; se ≥ 2048×2048, reduzir ou passar para DDS | soma dos ms |
| on_demand | `convert_object` depois do frame 5 (módulo `load`) | Load Mode **With Scene** ou chamar `convertObject` antes do trecho (tela de loading) | soma dos ms |
| cena | `scene_load` de LibLoad/AddScene depois do frame 5 | LibLoad assíncrono ou carregar no loading | soma dos ms |
| script | `scripts`: média ≥ 0,5 ms/frame ou pior frame ≥ 5 ms | nome do script; olhar o laço do `update` (o trace não grava o objeto) | ms/frame |
| shader | `load_shaders` com `compiled` > 0 depois do frame 5, ou `create` no `shaders.txt` depois do frame 5 | aquecer no load (prefetch) / cache de shaders | soma dos ms |
| static_batch | malhas pequenas, visíveis, com o mesmo material, fora do Static Batch | ligar Static Batch | draw calls (não ms) |

**Static Batch não dispara hoje.** O evento `object` grava só a marca manual (`use_static_batch`). Desde
2026-10-30 o Auto Static Batch é padrão por cena e o trace não grava nem essa opção nem o tipo de física do
objeto. Sem isso a regra apontaria objetos que já estão no lote. Ela só dispara se o `scene_load` tiver
`auto_static_batch: false` (um campo novo, de uma linha no `BL_Converter.cpp`, que fica para a etapa 2).

## Etapa 2: sugestões aplicáveis no editor (feita em 2026-11-05)

- O relatório grava `sugestoes.json` na pasta do trace, só com as correções seguras e reversíveis: ligar Static
  Batch e mudar Load Mode. Imagens, scripts e shaders continuam só como texto.
- O Scene Doctor ganha "Abrir sugestões do Game Trace". Cada item vira um `Issue` com `fix`/`revert`, reusando o
  fluxo de aplicar e desfazer que já existe, e confere de novo no `.range` aberto (o objeto existe, ainda não
  está no Static Batch, é estático e sem lógica: `_static_batch_candidate`).
- No C++: gravar `auto_static_batch` no `scene_load` e o tipo de física no `object`, para a regra de Static Batch.

## Validação

- Etapa 1: rodar o relatório em traces reais do RolimaRacer (com e sem `load`, `scripts` e `shaders`) e
  conferir que cada sugestão bate com a tabela de origem. Um trace sem um módulo não pode gerar sugestões
  daquele módulo.
- Etapa 2: aplicar e desfazer pelo Scene Doctor num `.range` de teste e conferir o arquivo salvo.

## Resultado da etapa 2

- C++ (`BL_Converter.cpp`): `object` ganhou `physics`, `parent` e `logic`; `scene_load` ganhou `auto_static_batch`.
- A regra de Static Batch também exige objeto sem lógica nem pai, como o `_static_batch_candidate` do Scene Doctor.
- `sugestoes.json` (versão 1): `{jogo, sugestoes: [{regra, alvo, texto, ganho, lentos, cena, objeto | objetos}]}`.
- Scene Doctor: botão **Game Trace...** (`game.scene_doctor_trace`) e regra `rule_game_trace`, que relê o arquivo a
  cada verificação. Itens `trace_on_demand` e `trace_static_batch`, com Fix e Revert.
- Teste em background (`tools/debug/cenas/criar_cena_trace_doctor.py`): o trace aponta o On Demand (130 ms) e os
  12 cubos; Fix muda o Load Mode e marca o Static Batch, o arquivo salvo guarda a mudança, Revert volta e os
  itens reaparecem. Aceito com janela pelo usuário em 2026-11-05: plano concluído.
