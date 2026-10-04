# Guia de predição, lag compensation e relógio (frente F)

Criado em 2026-10-04. Para quem vai ligar a predição do núcleo `Network/` na engine
(`KX_NetworkManager`, `KX_CharacterController`). Interpretações e números:
`source/source/gameengine/Network/NOTES-F.md`.

## O que a API faz

| Peça | Lado | Papel |
|---|---|---|
| `net::NetClock` (`NET_Clock.h`) | cliente | Estima o tempo do servidor a partir dos Pongs, mede o jitter dos snapshots e dá o `interp_delay` adaptativo, o tick de render (tick + alpha) e o tick que o jogador deve prever. |
| `net::PredictionClient` (`NET_Prediction.h`) | cliente | Guarda input e estado previsto por tick, monta o `Input` com os 8 últimos blocos, reconcilia com o estado do servidor (rebobina e reaplica pelos callbacks do jogo) e suaviza a correção. |
| `net::InputQueue` / `net::PredictionServer` | servidor | Fila de input por cliente: aplica cada tick uma vez e em ordem, descarta repetidos, repete o último input por até N ticks e conta atrasados. |
| `net::LagCompensation` (`NET_LagCompensation.h`) | servidor | Histórico de ~1 s de hitboxes (esfera, cápsula, caixa orientada) e raycast no tempo que o cliente via, com limite de rebobinar. |

## Exemplo: cliente

```cpp
#include "NET_Clock.h"
#include "NET_Prediction.h"

net::ClockConfig clockConfig;
clockConfig.tickRate = session.tickRate();
clockConfig.snapshotRate = session.snapshotRate();
net::NetClock clock(clockConfig);

net::PredictionCallbacks cb;
cb.setState = [&](const net::ObjectState &s) { player.setPosition(s.position); player.setVelocity(s.velocity); };
cb.replay = [&](net::Tick, const net::InputBlock &in) { player.applyInput(in); player.step(1.0f / tickRate); };
cb.getState = [&](net::ObjectState &s) { s = player.state(); return true; };
net::PredictionClient prediction(cb);

uint32_t pongs = 0;
net::Tick tick = net::kNoTick;

// A cada passo fixo:
session.update(nowMs, events);
if (session.lastPong().count != pongs) {
	pongs = session.lastPong().count;
	clock.addPong(session.lastPong().rttMs, session.lastPong().serverTick, nowMs);
}
// Para cada snapshot novo aceito: clock.addSnapshot(snap.tick, nowMs);
// e, com o estado do próprio jogador: prediction.reconcile(snap.tick, *snap.find(playerId));

tick = (tick == net::kNoTick) ? clock.predictionTick(nowMs) : tick + 1;
net::InputBlock in = readLocalInput();  // até 64 bytes
net::InputMsg msg;
prediction.recordInput(tick, in, msg);
session.send(net::Channel::Input, net::makePacket(msg));
player.applyInput(in);
player.step(1.0f / tickRate);
prediction.recordState(tick, player.state());
prediction.update(frameMs);

float offset[3];
prediction.visualOffset(offset);  // somar à posição só na renderização

// Objetos remotos:
net::Tick renderTick;
float alpha;
clock.renderTime(nowMs, renderTick, alpha);
snapshotBuffer.sample(renderTick, alpha, states);
```

## Exemplo: servidor

```cpp
#include "NET_LagCompensation.h"
#include "NET_Prediction.h"

net::PredictionServer inputs;
net::LagCompensation lag({tickRate, 1000, 400});

// A cada tick:
server.update(nowMs, tick, events);
for (const net::SessionEvent &e : events) {
	inputs.handleEvent(e, tick);
}
for (net::ClientId id : server.clients()) {
	net::InputBlock in;
	if (!inputs.consume(id, tick, in)) {
		in = neutralInput();
	}
	applyInput(id, in);
}
stepPhysics();
lag.record(tick, collectHitboxes());

// Tiro que o cliente disparou vendo o tick `shotTick` + `shotAlpha`:
net::RayHit hit;
if (lag.raycast(origin, dir, 100.0f, shotTick, shotAlpha, tick, hit, shooterId)) {
	applyDamage(hit.id, hit.part);
}
```

## Regras para a integração

- A simulação do jogador tem de ser determinística o bastante: o mesmo input sobre o mesmo estado dá o
  mesmo resultado no cliente e no servidor. Personagem (`KX_CharacterController`) serve; física de corpo
  rígido não (plano, seção 5.2).
- `replay` aplica o input e avança um tick do objeto do jogador sem efeitos colaterais (sons, partículas).
- Na replicação, use `ReplicaClientConfig::skipOwned = true` para o snapshot não sobrescrever o jogador
  previsto; o estado do servidor vai para `reconcile`.
- O tempo de render do tiro (tick + alpha de `NetClock::renderTime`) vai junto do RPC de tiro.

## Limites

| Item | Valor |
|---|---|
| Input por tick | 64 bytes; 8 ticks por pacote |
| Input à frente do servidor | 64 ticks (o resto é descartado) |
| Repetição de input faltando | 4 ticks (configurável) |
| Correção | só posição; decai em 100 ms; acima de 2 m teleporta |
| Histórico de hitboxes | 1 s; rebobinar até 400 ms (configurável) |
| `interp_delay` | 2 snapshots + 3 × jitter, até 500 ms; desce 20 ms/s |
| Input inválido | contado em `InputQueueStats::invalid`, ainda não vira violação na sessão |
