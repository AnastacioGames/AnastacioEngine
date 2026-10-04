# Contrato do protocolo de rede (v1)

Criado em 2026-10-03. Base de [`multiplayer-plan.md`](multiplayer-plan.md), etapa 0. Este arquivo é a
fonte única do formato na rede e das interfaces do núcleo `Network/`. Toda frente (local ou na nuvem)
implementa contra ele; mudar algo aqui exige atualizar este arquivo no mesmo commit.

Status: rascunho, aguardando liberação para implementar.

## 1. Regras gerais

- C++17, sem exceções no caminho de rede (erros por valor de retorno), sem RTTI obrigatório.
- O núcleo `source/source/gameengine/Network/` **não inclui nada da engine** (nem KX, SCA, DNA, Python,
  `CM_*`). Só a biblioteca padrão e, nos transportes, ENet ou a API do Emscripten. A ponte com a engine é
  `KX_NetworkManager` (fora do núcleo).
- Compila de dois jeitos:
  - dentro da engine: `add_subdirectory` gera a biblioteca `ge_network`;
  - sozinho: `cmake -S source/source/gameengine/Network -B build-net -DNET_STANDALONE=ON` gera
    `ge_network` + `net_tests` (gtest de `source/extern/gtest`). Este é o build usado na nuvem.
- Byte order na rede: **little-endian**. Bits escritos do menos para o mais significativo de cada byte.
- Prefixo de nomes: `NET_` (classes/arquivos), namespace `net`.
- Alvos que precisam dar a mesma saída: Windows x64 (MSVC), Linux x64 (GCC/Clang), wasm32 (Emscripten).
  Nada de `float` com comportamento dependente de plataforma no formato: quantização é feita em inteiros.

## 2. Tick e tempo

- `using Tick = uint32_t;` Começa em 1 quando a sessão abre. 0 = "nenhum tick".
- Um tick = um passo fixo de lógica da engine. A taxa (`tickRate`, Hz) é do servidor e vem no handshake.
- Comparação com wrap: `bool tickNewer(Tick a, Tick b) { return int32_t(a - b) > 0; }`.
- Na rede, ticks de snapshot e de input são enviados completos (32 bits) na v1.
- Relógio: cliente estima `serverTick` com ping-pong (`Ping`/`Pong`, seção 5) e média móvel exponencial
  do RTT (alfa 0,1).

## 3. Identidade

- `using NetId = uint32_t;` 0 = inválido.
  - `0x00000001–0x7FFFFFFF`: objetos de cena, id salvo no `.range` (gerado no editor, aleatório, sem
    colisão dentro do arquivo).
  - `0x80000000–0xFFFFFFFF`: objetos criados em jogo; atribuídos só pelo servidor, sequenciais.
- `using ClientId = uint16_t;` 0 = servidor/host. Clientes de 1 a `maxClients`.
- `sceneHash`: FNV-1a 64 bits sobre a lista **ordenada** de `NetId` de cena + nome da cena. Usado no
  handshake e na troca de cena.

## 4. Canais e pacotes

### 4.1 Canais lógicos

| Canal | Garantia | Uso |
|---|---|---|
| 0 `Control` | confiável, ordenado | handshake, desconexão, troca de cena, spawn/despawn, ownership |
| 1 `Rpc` | confiável, ordenado | RPCs e eventos |
| 2 `Snapshot` | não confiável, sequenciado (descarta antigo) | snapshots de estado |
| 3 `Input` | não confiável, sequenciado | inputs do cliente (com redundância) |

Transportes que não têm canais (WebSocket) multiplexam por um byte de canal no início do pacote; nesse caso
tudo chega confiável e ordenado, e o receptor ainda descarta snapshot/input mais antigo que o último aceito.

### 4.2 Limites

| Limite | Valor v1 |
|---|---|
| Pacote não confiável (payload) | ≤ 1200 bytes |
| Mensagem confiável | ≤ 65 536 bytes |
| Mensagens por pacote | ≤ 64 |
| RPCs recebidos por cliente | ≤ 120 por segundo |
| Bytes recebidos por cliente | ≤ 64 KB/s (média em 1 s) |
| Conexões pendentes (handshake) | ≤ 16, timeout 5 s |
| Timeout de conexão sem pacotes | 10 s |
| Clientes por servidor (`maxClients`) | ≤ 64 |

Excedeu: a mensagem é descartada e conta como violação; 10 violações em 10 s = desconexão com motivo
`ProtocolViolation`.

### 4.3 Cabeçalho de mensagem

Cada mensagem dentro de um pacote:

```
u8   type        (MessageType)
varu len         tamanho do corpo em bytes (varint LEB128, até 3 bytes)
...  body
```

Mensagem com `type` desconhecido: pulada usando `len` (compatibilidade para frente) e contada como violação
só se `len` passar do fim do pacote.

## 5. Mensagens

`MessageType` (u8). Corpos em notação: `u8/u16/u32/u64` inteiros little-endian; `varu` LEB128;
`str` = `varu` comprimento + UTF-8 (≤ 255 bytes); `bits(n)` campo de n bits no bitstream.

| Id | Nome | Canal | Direção | Corpo |
|---|---|---|---|---|
| 1 | `Hello` | 0 | C→S | `u32 magic='ANET'`, `u16 protocolVersion`, `str gameId`, `u32 gameVersion`, `u64 sceneHash`, `str playerName`, `u64 token` |
| 2 | `Welcome` | 0 | S→C | `u16 clientId`, `u16 tickRate`, `u16 snapshotRate`, `u32 serverTick`, `u16 maxClients`, `str sceneName` |
| 3 | `Reject` | 0 | S→C | `u8 reason` (`RejectReason`), `str detail` |
| 4 | `Disconnect` | 0 | ambos | `u8 reason` (`DisconnectReason`) |
| 5 | `Ping` | 0* | ambos | `u32 seq`, `u32 senderTimeMs` (*enviado no canal 2/3 sem confiabilidade) |
| 6 | `Pong` | 0* | ambos | `u32 seq`, `u32 echoTimeMs`, `u32 serverTick` |
| 7 | `ClientInfo` | 0 | S→C | `u16 clientId`, `str name`, `u8 flags` (conectado/pronto) |
| 8 | `SceneChange` | 0 | S→C | `str sceneName`, `u64 sceneHash` |
| 9 | `SceneLoaded` | 0 | C→S | `u64 sceneHash` |
| 10 | `Spawn` | 0 | S→C | `u32 netId`, `str prototypeName`, `u16 owner`, estado inicial completo (formato da seção 6) |
| 11 | `Despawn` | 0 | S→C | `u32 netId` |
| 12 | `Ownership` | 0 | S→C | `u32 netId`, `u16 newOwner` |
| 13 | `Snapshot` | 2 | S→C | seção 6 |
| 14 | `SnapshotAck` | 3 | C→S | `u32 tick` (último snapshot aplicado) |
| 15 | `Input` | 3 | C→S | `u32 newestTick`, `u8 count` (1–8), `count` × bloco de input (seção 7), do mais novo para o mais velho |
| 16 | `Rpc` | 1 | ambos | `u32 netId` (0 = global), `u16 rpcId`, `u32 tick`, argumentos (seção 8) |
| 17 | `FullStateRequest` | 0 | C→S | vazio (cliente perdeu sincronia) |
| 18 | `Chat` | 1 | ambos | `u16 fromClient`, `str text` (≤ 200 bytes) |
| 200 | `RpcFrom` | 1/2 | S→C | `u16 fromClient` + corpo do `Rpc`; repasse de `All`/`Others` vindo de um cliente (`NOTES-G.md`) |
| 201 | `InputTiming` | 2 | S→C | `u32 tick` (tick do servidor na medição), `i16 slack` em 1/16 de tick: tick mais novo de cada `Input` − próximo tick a simular na chegada, suavizado (EMA 0,1); negativo = inputs atrasados. Provisória, ~4 Hz (`NOTES-engine.md`) |

`protocolVersion` = 1. Mudança incompatível no formato incrementa. `RpcFrom` (200) é aditiva: ficou fora
desse contador porque um cliente que não a conhece simplesmente descarta a mensagem (via
`isKnownMessageType`) e só perde os repasses de RPC `All`/`Others` vindos de outro cliente — chamadas do
próprio servidor continuam chegando como `Rpc` normal. Os dois lados de uma mesma sessão devem rodar a
versão que já tem `RpcFrom` (commit que a introduziu); misturar um cliente velho com um servidor novo é
suportado mas degradado, não um erro de protocolo.

`InputTiming` (201) segue a mesma regra: aditiva e descartável. O cliente usa a folga para ajustar o
adiantamento da predição (`NetClock::addInputSlack`, alvo de 3 ticks); um cliente que não a conhece só
fica com a margem fixa do `predictionTick`.

`RejectReason`: 1 `VersionMismatch`, 2 `SceneMismatch`, 3 `ServerFull`, 4 `BadToken`, 5 `Banned`,
6 `GameInProgress` (se o jogo não aceitar entrada tardia).

`DisconnectReason`: 1 `Quit`, 2 `Timeout`, 3 `Kicked`, 4 `ProtocolViolation`, 5 `ServerShutdown`.

### 5.1 Sequência de conexão

```
C → S  Hello
S → C  Welcome | Reject
S → C  ClientInfo (todos)   SceneChange (cena atual)
C → S  SceneLoaded
S → C  Spawn (cada objeto criado em jogo vivo) + Snapshot completo (baseline = 0)
       ... deltas normais ...
```

Entrada com partida em andamento segue a mesma sequência. Reconexão: `Hello` com o mesmo `token` dentro de
30 s recupera o `clientId` e os objetos possuídos; depois disso o servidor faz despawn ou transfere dono.

## 6. Snapshot

```
u32  tick
u32  baselineTick       0 = completo (sem delta)
varu objectCount
objectCount × {
  varu netIdDelta        diferença para o NetId anterior da lista (lista ordenada por NetId)
  bits(1) removed        1 = objeto não relevante mais/sumiu; nada mais segue
  bits(1) changed        0 = idêntico ao baseline; nada mais segue
  campos com 1 bit de presença cada, na ordem: transform, velocity, angularVelocity, props, anim
}
```

O servidor guarda os snapshots enviados por cliente (até 64 ticks) e usa como baseline o último confirmado
por `SnapshotAck`. Se o baseline não existe mais no cliente, ele manda `FullStateRequest`.

### 6.1 Quantização (padrão; configurável por cena/objeto)

| Campo | Formato |
|---|---|
| Posição | 3 × inteiro com sinal, passo de 1 mm, faixa ±(2^(bits-1)) mm; bits por eixo = 22 por padrão (±2,1 km), configurável 16–32 |
| Rotação | "smallest three": 2 bits do índice do maior componente + 3 × 10 bits (padrão), configurável 9–15 bits |
| Velocidade linear | 3 × 16 bits, faixa ±`maxSpeed` (padrão 100 m/s) |
| Velocidade angular | 3 × 12 bits, faixa ±`maxAngSpeed` (padrão 50 rad/s) |
| Propriedade bool | 1 bit |
| Propriedade int | varint com zigzag |
| Propriedade float | inteiro de `bits` sobre `[min,max]` (definidos na UI), ou 32 bits crus se não definido |
| Propriedade string | `str`, só no canal confiável (mudança de string vira RPC interno, não snapshot) |

Quantizar e desquantizar devem ser determinísticos: `quantize(x) = clamp(round_half_away(x/step))` com
inteiros; o teste compara a saída nas três plataformas.

## 7. Input

Bloco de input = conteúdo definido pelo jogo, limitado a 64 bytes por tick (v1: bitstream livre escrito pela
API Python/C++). O cliente manda os 8 últimos ticks em cada pacote (redundância contra perda). O servidor
aplica cada tick uma vez, na ordem, e descarta ticks já aplicados.

## 8. RPC

- Registrados por nome; `rpcId` = índice na tabela de RPCs ordenada por nome. A tabela não vai pela rede
  na v1: cliente e servidor rodam o mesmo jogo, o que `gameVersion` e `sceneHash` garantem no handshake.
- Alvo: `Server`, `Owner`, `All`, `Others`. O servidor recusa RPC de cliente para alvo que ele não pode
  chamar, ou em objeto que não possui (quando o RPC exige dono).
- Argumentos: `u8 count`, depois cada um com `u8 tipo` (`bool, int, float, vec3, quat, str, netId`) e o
  valor. Tamanho total ≤ 1024 bytes (v1).

## 9. Interfaces do núcleo (headers congelados da etapa 0)

### 9.1 `NET_BitStream.h`

```cpp
namespace net {
class BitWriter {
public:
	explicit BitWriter(std::vector<uint8_t> &out);
	void writeBits(uint32_t value, int bits);      // 1..32
	void writeBool(bool v);
	void writeU8(uint8_t), writeU16(uint16_t), writeU32(uint32_t), writeU64(uint64_t);
	void writeVarU(uint64_t v);                     // LEB128
	void writeVarI(int64_t v);                      // zigzag + LEB128
	void writeString(std::string_view s);           // falha (retorna false em ok()) se > 255 bytes
	void writeQuantized(float v, float min, float max, int bits);
	void alignToByte();
	size_t bitsWritten() const;
	bool ok() const;
};

class BitReader {
public:
	BitReader(const uint8_t *data, size_t size);
	uint32_t readBits(int bits);                    // fora do fim: retorna 0 e marca erro
	bool readBool();
	uint8_t readU8(); uint16_t readU16(); uint32_t readU32(); uint64_t readU64();
	uint64_t readVarU(); int64_t readVarI();
	bool readString(std::string &out);
	float readQuantized(float min, float max, int bits);
	void alignToByte();
	size_t bitsRemaining() const;
	bool ok() const;                                // false após qualquer leitura inválida
};

// quantização de transform (seção 6.1)
void writePosition(BitWriter &, const float pos[3], const PositionQuant &);
bool readPosition(BitReader &, float pos[3], const PositionQuant &);
void writeRotation(BitWriter &, const float quat[4], int bitsPerComponent);  // x,y,z,w normalizado
bool readRotation(BitReader &, float quat[4], int bitsPerComponent);
}
```

Regra: um `BitReader` com erro nunca lê fora do buffer e devolve zeros a partir do erro.

### 9.2 `NET_ITransport.h`

```cpp
namespace net {
using PeerId = uint32_t;   // id local do transporte, não é ClientId

enum class Channel : uint8_t { Control = 0, Rpc = 1, Snapshot = 2, Input = 3 };

struct TransportEvent {
	enum class Type { Connected, Disconnected, Received } type;
	PeerId peer;
	Channel channel;
	std::vector<uint8_t> data;   // só em Received
};

class ITransport {
public:
	virtual ~ITransport() = default;
	virtual bool listen(uint16_t port, int maxPeers) = 0;           // servidor
	virtual bool connect(const std::string &host, uint16_t port) = 0; // cliente
	virtual void send(PeerId, Channel, const uint8_t *data, size_t size) = 0;
	virtual void disconnect(PeerId) = 0;
	virtual void poll(std::vector<TransportEvent> &events) = 0;     // não bloqueia
	virtual void shutdown() = 0;
	virtual bool reliableAll() const = 0;                            // true em WebSocket
};

std::unique_ptr<ITransport> createLoopbackPair(std::unique_ptr<ITransport> &other);
std::unique_ptr<ITransport> createENetTransport();
std::unique_ptr<ITransport> createSimulatedTransport(std::unique_ptr<ITransport> inner,
                                                     const NetSimSettings &);
}
```

`NetSimSettings`: `latencyMs`, `jitterMs`, `lossPercent`, `duplicatePercent`, semente do gerador (testes
repetíveis).

### 9.3 Outros

- `NET_Types.h`: `Tick`, `NetId`, `ClientId`, `tickNewer`, enums da seção 5.
- `NET_Messages.h/.cpp`: estruturas e `encode/decode` de cada mensagem da seção 5 (decode retorna `false`
  para corpo inválido, nunca lê fora).
- `NET_SnapshotBuffer.h`: buffer circular de snapshots por tick e interpolação (`sample(renderTick, alpha)`).

## 10. Testes obrigatórios do núcleo

- Ida e volta de cada tipo do bitstream, inclusive limites (0, máximo, negativo mínimo).
- Leitura truncada em cada posição de um pacote válido: nunca crasha, `ok()` vira false.
- Valores fora da faixa na quantização: ficam presos na faixa (clamp), sem overflow.
- Rotação: erro angular máximo < 0,25° com 10 bits; `q` e `-q` dão o mesmo resultado.
- Vetores de teste dourados (`tests/golden/*.bin`) comparados byte a byte: mesma saída em todas as
  plataformas.
- Encode/decode de cada mensagem; mensagem com `len` mentiroso; tipo desconhecido pulado.
- Transporte loopback e simulado: entrega, perda e ordem conforme as configurações, com semente fixa.
- Fuzz curto (libFuzzer quando disponível, ou 100 000 entradas aleatórias com semente fixa) no decode.

## 11. Interpretações aceitas das frentes A–D (2026-10-03)

Valem como parte do contrato. Detalhes em `Network/NOTES-A.md`, `NOTES-B.md`, `NOTES-C.md` e
`tools/net_menu/NOTES-D.md`.

- **Bitstream:** inteiros e varints não alinham sozinhos; cada corpo termina com `alignToByte()`.
  `PositionQuant { int bits = 22; }` (16–32), passo fixo de 1 mm, offset binário. Quantização de faixa em
  `double` com arredondamento simétrico: o zero não é exato (velocidade 0 volta ~0,0015 m/s em 16 bits).
  Rotação: empate vai para o menor índice; 9–15 bits por componente.
- **Mensagens:** decode estrito (byte sobrando = inválido); `Hello` com magic errado = inválido;
  `Input` = `varu len` (≤ 64) + bytes por bloco; tipos de argumento de RPC 1–7 na ordem da seção 8;
  `Chat.text` ≤ 200 bytes; `Spawn` = bits de presença + campos de um objeto.
- **Snapshot:** propriedades por esquema de cada objeto; animação é provisória (pode mudar na frente E).
- **Transporte:** `ITransport::localPort()` (0 se não houver); `createLoopbackHub()`; simulado perde/duplica
  só nos canais não confiáveis. ENet: Control/Rpc `RELIABLE`, Snapshot/Input `UNSEQUENCED`.
- **Sessão:** ordem das checagens do `Hello`: versão/gameId/gameVersion → banido → cena → token já
  conectado → reconexão → cheio → partida em andamento. Ping a cada 1 s, RTT por EMA α = 0,1. Servidor
  escuta com `maxClients + 16` peers para conseguir mandar `Reject ServerFull`.
- **WebSocket:** um frame binário por mensagem, primeiro byte = canal; limite 65 537 bytes (close 1009);
  erros de protocolo 1002, texto 1003; sem checagem de `Origin`; só IPv4; TLS no proxy reverso.
- **Multi-transporte:** `reliableAll() = false` (limite de 1200 bytes nos canais não confiáveis vale para
  todos); `maxPeers` por transporte, o total de jogadores é limitado pela sessão; `localPort()` é a do
  primeiro transporte.
- **Descarte de snapshot/input antigo** no WebSocket é da camada de replicação, não do transporte.
- **Menu:** fica em `tools/net_menu/` até o template da etapa 5; API Python esperada descrita em NOTES-D.
