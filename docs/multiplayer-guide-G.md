# Guia de RPC (frente G)

Criado em 2026-10-04. Para quem vai ligar os RPCs do núcleo `Network/` na engine (`KX_NetworkManager`,
API Python `@rpc`). Interpretações: `source/source/gameengine/Network/NOTES-G.md`.

## O que a API faz

| Peça | Lado | Papel |
|---|---|---|
| `net::RpcTable` | ambos | Registro por nome. Depois de `finalize()`, `rpcId` = índice na tabela ordenada. Os dois lados registram os mesmos RPCs. |
| `net::RpcServer` | servidor | Decodifica os `Rpc` dos clientes, confere alvo, dono e argumentos, conta violação na sessão, roda o handler e repassa `All`/`Others` para os clientes. Também faz as chamadas do servidor. |
| `net::RpcClient` | cliente | Chama RPCs do servidor (recusa localmente o que o servidor recusaria) e roda os handlers do que chega. |

Alvos: `Server` (roda no servidor), `Owner` (servidor → dono do objeto), `All` (servidor + todos os
clientes), `Others` (servidor + todos menos quem chamou). Opções por RPC: `requireOwner`, `reliable`,
assinatura (`checkArgs` + `argTypes`).

## Exemplo

```cpp
#include "NET_RPC.h"

// Igual nos dois lados (vem do jogo: decoradores @rpc, logic bricks...).
void registerRpcs(net::RpcTable &table)
{
	net::RpcDesc fire;
	fire.name = "fire";
	fire.target = net::RpcTarget::Server;
	fire.requireOwner = true;  // só o dono da arma atira
	fire.checkArgs = true;
	fire.argTypes = {net::RpcArgType::Vec3, net::RpcArgType::Vec3};
	table.add(fire);

	net::RpcDesc emote;
	emote.name = "emote";
	emote.target = net::RpcTarget::Others;
	emote.reliable = false;
	table.add(emote);

	table.finalize();
}

// Servidor
net::RpcTable table;
registerRpcs(table);
table.setHandler("fire", [&](const net::RpcCall &call) {
	const net::RpcArg &origin = (*call.args)[0];
	const net::RpcArg &dir = (*call.args)[1];
	shoot(call.caller, call.netId, origin.v, dir.v, call.tick);
});
net::RpcServer rpc(session, table, [&](net::NetId id, net::ClientId &owner) {
	return replicator.hasObject(id) && (owner = replicator.owner(id), true);
});
// A cada tick:
session.update(nowMs, tick, events);
std::vector<net::SessionEvent> more;
for (const net::SessionEvent &e : events) {
	rpc.handleEvent(e, nowMs, more);  // "more" pode receber ClientLeft por violação
}

// Cliente
net::RpcClient rpcClient(clientSession, table, ownerLookup);
net::RpcArg origin, dir;
origin.type = dir.type = net::RpcArgType::Vec3;
rpcClient.call("fire", weaponId, {origin, dir}, renderTick);
// E para tudo que chega: rpcClient.handleEvent(e);
```

`RpcCall::args` aponta para dados que só valem durante o handler: copie o que precisar guardar.

## Limites

| Item | Valor |
|---|---|
| Argumentos | até 255, até 1024 bytes no total (contrato, seção 8) |
| Taxa | 120 RPC/s por cliente (na sessão; acima disso é violação) |
| Violações | 10 em 10 s desconectam (sessão) |
| Quem chamou | só o servidor sabe; no cliente `caller` é sempre 0 (proposta em NOTES-G) |
| Não confiável | pode perder ou duplicar; pacote ≤ 1200 bytes |
| RPC em objeto despawnado | descartado em silêncio |
