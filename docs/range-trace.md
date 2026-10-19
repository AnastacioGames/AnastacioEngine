# Range Trace

Log opcional de uma sessão de jogo: o que a engine carregou, quanto custou e o que foi de fato desenhado.
Serve para o pente fino de um jogo: achar o que carrega à toa e as cargas no meio do jogo que podem travar.
Código: `source/source/gameengine/Common/CM_Trace.h/.cpp`. Relatório: `tools/debug/relatorio_trace.py`.

## Como usar

```
tools\debug\abrir_trace.bat [jogo.range] [modulos]
```

Abre o jogo no `AnastacioRuntime.exe` (sem argumento abre o RolimaRacer). Jogue o trecho que quer examinar
e feche o jogo normalmente. O `.bat` gera e abre `debug-logs\trace-<data-hora>\relatorio.html`; ao lado fica
`resumo.md`, curto o bastante para colar numa IA.

Sem o `.bat`: `RANGE_TRACE=<pasta>` liga o trace (grava `<pasta>\trace.jsonl`) e
`RANGE_TRACE_MODULES=load,usage` escolhe os módulos (sem a variável, ou `all`, liga todos).
Depois: `python tools/debug/relatorio_trace.py <pasta> [--resumo]`. Funciona também no editor (Play),
cada partida termina com um evento `end` no mesmo arquivo.

Desligado, cada ponto instrumentado custa um `if`. Num jogo exportado nada muda se a variável não existir.

## Módulos

| Módulo | Grava | Peso |
|---|---|---|
| `load` | Por cena convertida (inicial, AddScene, LibLoad): tempo de conversão, texturas e shaders; cada objeto (tipo, camada ativa, malhas), cada malha (triângulos, materiais), cada material (imagens dos nós e slots), objetos deixados de fora pelo Load Mode; objetos On Demand convertidos no meio do jogo | Só no load |
| `usage` | Primeiro frame em que cada objeto passa no culling da câmera ou de uma sombra; cada imagem enviada para a GPU (tamanho, ms, frame) | Um teste de ponteiro por objeto visível por frame |

Próximos (ver `docs/roadmap.md`): `runtime` (sons, scripts, troca de cena), `spikes` (frames lentos com o
que carregou neles, reaproveita `RANGE_PROFILE`), `sector` (câmera num trilho medindo o custo por trecho da
pista), `shaders` e `work` (formato novo para `RANGE_SHADER_LOG` e `CM_WorkCounters`), e o launcher com janela.

## Formato

Uma linha JSON por evento: `{"t":segundos,"f":frame,"ev":"tipo",...}`. Tipos: `session`, `scene_load`,
`load_shaders`, `object`, `mesh`, `material`, `object_left_out`, `convert_object`, `visible`, `image`, `end`.
Objetos são casados por nome entre cenas, porque réplicas e objetos On Demand entram na cena de destino com
o nome do original (os On Demand aparecem primeiro na cena temporária `..ConvertSceneObject..`).

## Como ler o relatório

- **Carregados e nunca desenhados:** objetos com malha que não apareceram nem na câmera nem em sombra.
  Em camada inativa são modelos de Add Object: só contam se o jogo nunca os adicionou na sessão.
  O resultado vale para o que você jogou: um objeto de um trecho que você não visitou aparece aqui.
- **Só em sombra:** fora da câmera o tempo todo, mas projetando sombra.
- **Malhas, materiais e imagens à toa:** usados só pelos objetos nunca desenhados.
- **Cargas durante o jogo:** On Demand, LibLoad/AddScene e imagens enviadas depois dos primeiros 5 frames,
  por ms. As maiores são candidatas a pré-carregar.
