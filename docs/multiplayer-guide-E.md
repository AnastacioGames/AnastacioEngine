# Guia da replicação (frente E)

Criado em 2026-10-04. Para quem vai ligar a replicação do núcleo `Network/` na engine
(`KX_NetworkManager`). Contrato do formato: [`multiplayer-protocol.md`](multiplayer-protocol.md).
Interpretações e números do benchmark: `source/source/gameengine/Network/NOTES-E.md`.

## O que a API faz

| Peça | Lado | Papel |
|---|---|---|
| `net::IWorld` (`NET_IWorld.h`) | ambos | Interface que a engine implementa sobre `KX_GameObject`: ler/escrever transform, velocidade e propriedades, "está dormindo", spawn/despawn/dono. |
| `net::Replicator` (`NET_Replicator.h`) | servidor | Registra objetos replicados, lê o estado do `IWorld` a cada tick e manda para cada cliente: `Spawn`/`Despawn`/`Ownership` (confiável) e snapshot delta contra o último snapshot confirmado. Faz relevância por grid, orçamento de banda e prioridade. |
| `net::ReplicaClient` (`NET_ReplicaClient.h`) | cliente | Aplica `Spawn`/`Despawn`/`Ownership` no `IWorld`, decodifica snapshots, manda `SnapshotAck`, descarta snapshot antigo, pede `FullStateRequest` quando perde o baseline e guarda os snapshots num `SnapshotBuffer` para interpolar. |

As duas classes ficam por cima das sessões da frente B (`ServerSession`/`ClientSession`): o jogo repassa
os `SessionEvent` para elas e chama `update` uma vez por tick.

## Exemplo: servidor

```cpp
#include "NET_Replicator.h"

class EngineWorld : public net::IWorld { /* implementado com KX_GameObject */ };

EngineWorld world;
std::unique_ptr<net::ITransport> transport = net::createENetTransport();
net::ServerSession session(*transport, serverConfig);
session.start(7777);

net::ReplicatorConfig rc;
rc.snapshotIntervalTicks = serverConfig.tickRate / serverConfig.snapshotRate;  // ex.: 60 / 20 = 3
net::Replicator replicator(session, world, rc);

// Objeto de cena marcado "Replicate" (NetId salvo no .range).
net::ReplicatedObjectDesc door;
door.props = {{net::PropKind::Bool}};  // mesmo esquema nos dois lados
replicator.addSceneObject(sceneNetId, door);

// Objeto criado em jogo (Add Object): o servidor escolhe o NetId.
net::ReplicatedObjectDesc player;
player.prototype = "Player";         // nome do objeto que o cliente cria no Spawn
player.owner = clientId;
player.syncVelocity = true;
net::NetId id = replicator.spawn(player);
// a engine cria o objeto e passa a responder a world.getTransform(id, ...)

// A cada passo fixo de lógica:
std::vector<net::SessionEvent> events;
session.update(nowMs, tick, events);
for (const net::SessionEvent &e : events) {
	if (!replicator.handleEvent(e)) {
		/* outros eventos: entrada/saída de jogador, RPC, chat... */
	}
}
replicator.setClientView(clientId, cameraPosition, 150.0f);  // opcional: relevância por distância
replicator.update(tick, nowMs);
```

## Exemplo: cliente

```cpp
#include "NET_ReplicaClient.h"

net::ReplicaClientConfig cc;
cc.schema = [](net::NetId id, const std::string &prototype) -> const std::vector<net::PropertyDesc> * {
	return lookupSchema(id, prototype);  // prototype vazio = objeto de cena
};
net::ReplicaClient replica(clientSession, world, cc);

std::vector<net::SessionEvent> events;
clientSession.update(nowMs, events);
for (const net::SessionEvent &e : events) {
	replica.handleEvent(e, nowMs);
	if (e.type == net::SessionEvent::Type::SceneChange) {
		/* carregar a cena */ clientSession.sceneLoaded(e.sceneHash);
	}
}
// Na renderização, ~2 snapshots atrás do mais novo:
replica.applyInterpolated(renderTick, alpha);  // ou applyLatest() sem interpolação
```

## Regras para a integração

- O esquema de propriedades (`PropertyDesc`) tem de ser **igual** no servidor e no cliente, na mesma
  ordem. Ele vem da UI (checkbox "Rep" nas propriedades). Strings não entram no snapshot.
- A `SnapshotConfig` de quantização (bits de posição, rotação, `maxSpeed`) também tem de ser igual nos dois
  lados.
- `IWorld::getProperties` deve devolver os valores na ordem e no tipo do esquema. Se não bater, o objeto
  fica com o último estado válido.
- `isSleeping` = Bullet "sleeping": o servidor não relê o objeto, e ele não gasta bytes.
- Objeto de cena fora da relevância não some do cliente: só para de receber atualizações.
- `ReplicaClientConfig::skipOwned = true` deixa os objetos do próprio jogador para a predição (frente F).

## Limites

| Item | Valor |
|---|---|
| Snapshot | 1 pacote ≤ 1200 bytes por cliente e por envio; o que não couber vai nos próximos, por prioridade |
| Banda | `bytesPerSecond` por cliente (padrão 64 KB/s), contando spawns |
| Remoções por snapshot | 128 (o resto sai nos seguintes) |
| Histórico por cliente | 64 snapshots (baseline mais velho que isso = snapshot completo) |
| `FullStateRequest` | no máximo 1 por segundo por cliente |
| Animação | ainda não replicada |
| CPU (16 clientes, 300 objetos se movendo, 30 Hz, Release) | ~1,0 ms por tick com tudo relevante; ~0,64 ms com raio de 60 m |
| Banda medida no mesmo cenário | ~32 KB/s por cliente (meta < 40 KB/s) |

A detecção de mudança usa hash de 64 bits dos campos quantizados (chance de colisão desprezível). As
violações por `SnapshotAck` inválido ainda não são contadas (falta um gancho em `ServerSession`).
