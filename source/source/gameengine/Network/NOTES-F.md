# Frente F: predição, lag compensation e relógio

Criado em 2026-10-04. Branch `net/prediction`. Arquivos: `NET_Prediction.h/.cpp`,
`NET_LagCompensation.h/.cpp`, `NET_Clock.h/.cpp`, `tests/NET_Prediction_test.cpp`.

## Interpretações

- **Tick de input = tick do servidor.** O cliente prevê à frente (`NetClock::predictionTick`: tempo do
  servidor + RTT/2 + jitter + 1 tick) e o servidor aplica o input do tick T quando simula T. O estado do
  tick T que volta ao cliente já inclui o input de T. O contrato (seção 7) não diz isso explicitamente.
- **Blocos contíguos:** `Input` leva os blocos `newestTick, newestTick-1, ...`. Um buraco ou volta no tick do
  cliente limpa o histórico de predição (manda menos de 8 blocos até completar de novo).
- **Atrasado x repetido:** bloco de um tick que o servidor já simulou com o input real conta como
  `duplicates`; se o tick foi simulado sem ele (repetição ou falta), conta uma vez como `late`. Bloco de tick
  já passado e fora da janela de 64 ticks conta como `late` a cada vez. Blocos além de `maxAheadTicks`
  (padrão 64) são descartados (`tooFar`).
- **Falta de input:** repete o último por `maxRepeatTicks` (padrão 4); depois `consume` devolve false e o jogo
  decide (normalmente input neutro).
- **Correção suavizada:** só posição. O erro vira um offset visual que decai exponencialmente
  (`smoothingMs`, padrão 100 ms). Erro acumulado acima de `teleportDistance` (2 m) zera o offset (teleporte).
  Rotação não é suavizada na v1.
- **Igualdade:** servidor e predição iguais se posição < 2 mm e velocidade < 0,01 m/s (a quantização de 1 mm
  e de 16 bits da velocidade não dispara correção).
- **Lag compensation:** o cliente informa o tempo que estava renderizando (tick + alpha de
  `NetClock::renderTime`), por exemplo no `tick` do RPC de tiro. O servidor limita o rebobinar a
  `maxRewindMs` (padrão 400 ms) e ao histórico (`historyMs`, 1 s). Hitboxes são casadas entre ticks por
  `(NetId, part)`; a que some no tick seguinte fica parada.
- **Relógio:** offset por EMA α = 0,1 sobre `serverTick*tickMs + RTT/2 - agora`; erro acima de 250 ms
  ressincroniza de uma vez. Jitter no estilo RFC 3550 (ganho 1/16) sobre o tempo de trânsito dos
  snapshots e sobre o RTT (metade). `interp_delay = 2 intervalos de snapshot + 3 × jitter`, entre 0 e
  500 ms; sobe na hora e desce no máximo 20 ms por segundo.

## Mudança fora dos arquivos novos

- `ClientSession::lastPong()` (aditivo): última amostra de Pong (contador, RTT, `serverTick`, hora), para
  alimentar o `NetClock`. A sessão já consumia o Pong sem expor a amostra.

## Dúvidas para o contrato

1. `Input` inválido (decode falhou) só é contado em `InputQueueStats::invalid`. A sessão não tem gancho para a
   camada de cima somar uma violação; proposta: `ServerSession::reportViolation(ClientId)`. O mesmo vale para
   `SnapshotAck` inválido da frente E.
2. O `tick` do `Rpc` é o lugar natural para o tempo de render do tiro, mas só cabe o tick inteiro. O alpha
   pode ir como argumento `float` do RPC na v1; proposta para a v2: tick em ponto fixo (24.8).
3. Comparar ticks usa `std::map` ordenado pelo valor; a volta do contador (2^32 ticks, ~2 anos a 60 Hz) não é
   tratada nas filas.

## Resultado dos testes

- Personagem com 150 ms de RTT e 2% de perda (50 Hz, 600 ticks): 571 ticks com input real, 1 atrasado,
  1 repetido; empurrão de 0,3 m no servidor corrigido sem teleporte, maior passo visual 0,144 m (0,1 m de
  movimento + correção); erro final < 1 cm.
- Raycast acerta onde o cliente viu (tick 45,5) e erra sem rebobinar; pedido além do limite é preso em 400 ms.
- `interp_delay` sobe de 100 ms para > 130 ms com 0–60 ms de jitter e volta para < 105 ms com a rede limpa.
