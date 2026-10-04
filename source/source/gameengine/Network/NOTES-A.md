# Notas da frente A (`net/core`)

Pontos em que o contrato (`docs/multiplayer-protocol.md`) estava ambíguo ou incompleto, e a interpretação
adotada (a mais conservadora). Se alguma for aceita, vale passar para o contrato; se não, corrigir aqui e
regenerar os vetores dourados (`net_tests --update-golden`).

## Bitstream

- Inteiros `u8/u16/u32/u64` e varints **não** alinham sozinhos ao byte: são `writeBits` em sequência. Em
  posição alinhada isso dá exatamente little-endian. Cada corpo de mensagem termina com `alignToByte()`.
- `'ANET'` como `u32`: bytes `A N E T` na rede (valor `0x54454E41`), não literal multicaractere do C++.
- `PositionQuant` não estava definido: `{ int bits = 22; }`, faixa 16–32. O passo é fixo em 1 mm
  (o contrato diz "passo de 1 mm"; não abri passo configurável). Valor na rede = `q + 2^(bits-1)` sem
  sinal (offset binário), faixa `[-2^(bits-1), 2^(bits-1)-1]` mm. NaN vira 0.
- `writeQuantized(v, min, max, bits)`: `round_half_away((v-min)/(max-min) * (2^bits-1))`, em `double`,
  com clamp. NaN vira `min`. Consequência: com número par de passos o zero não é exato (ex.: velocidade
  0 m/s volta como ~0,0015 m/s em 16 bits). Aceitável para v1; uma variante simétrica mudaria o formato.
- Rotação: em empate do maior componente vence o menor índice (garante `q` e `-q` iguais). Componentes
  menores quantizados em `[-1/√2, 1/√2]`. Bits por componente só em 9–15 (fora disso, erro).
- Adicionados além da 9.1 (funções livres, sem mexer na interface da classe): `writeFloat32/readFloat32`
  (float cru), `quantizeRange/dequantizeRange`, `quantizePositionAxis`, `quantizeRotation`,
  `BitWriter::fail()`, `BitReader::fail()` e `BitReader::bitPosition()`.

## Mensagens

- Decode é estrito: depois do corpo só pode sobrar padding de alinhamento; byte sobrando = corpo inválido.
- `Hello` com `magic` errado = corpo inválido. `protocolVersion` diferente decodifica normalmente
  (o servidor precisa ler para mandar `Reject VersionMismatch`).
- `Reject`/`Disconnect` com motivo desconhecido = corpo inválido.
- `PacketReader` devolve também tipos desconhecidos (o chamador pula); `len` além do fim, varint de
  tamanho com mais de 3 bytes ou mais de 64 mensagens = erro do pacote (violação).
- `Input`: o contrato não diz como delimitar cada bloco; cada bloco vai como `varu len` (≤ 64) + bytes.
- `Rpc`: ids de tipo de argumento `1 bool, 2 int, 3 float, 4 vec3, 5 quat, 6 str, 7 netId` (ordem do
  contrato, começando em 1 como os outros enums). Valores: bool `u8` 0/1, int `varI`, float/vec3/quat
  em float cru de 32 bits (sem quantização), str `str`, netId `u32`. O limite de 1024 bytes conta do
  `u8 count` até o fim dos argumentos.
- `Chat.text` ≤ 200 bytes, verificado no encode e no decode.
- `Spawn`: "estado inicial completo (formato da seção 6)" = os 5 bits de presença + campos de um objeto,
  sem `netIdDelta/removed/changed`.
- `messageChannel()` em `NET_Types.h` devolve o canal como `uint8_t` para não duplicar o `enum Channel`
  que é da frente B (`NET_ITransport.h`).

## Snapshot

- Objeto **omitido** do snapshot delta = igual ao baseline (é o que dá "objeto parado = 0 bytes"). Sumiço
  precisa de `removed = 1`. O encoder nunca emite `changed = 0`, mas o decoder aceita (mantém o baseline).
- Cada campo é escrito logo após seu bit de presença (bits intercalados, não os 5 bits juntos).
- "Mudou" é decidido sobre os valores **quantizados**, não sobre o float.
- Campos: transform = posição + rotação; velocidade 3 × 16 bits; angular 3 × 12 bits;
  anim = `varu action`, `frame` e `speed` em float cru (o contrato não define animação; provisório).
- Propriedades: o contrato não diz como o receptor conhece os tipos. Adotado um esquema por objeto
  (`SnapshotConfig::schema(NetId)` → `PropertyDesc[]`, vindo da UI nos dois lados). Formato:
  `varu count` (= tamanho do esquema), depois por propriedade `bit changed` + valor. Se o `count` mudar em
  relação ao baseline, todas vão com `changed = 1`. Strings ficam fora do snapshot (contrato).
- O conjunto de campos de um objeto é fixo: um campo que some no estado atual não tem como ser sinalizado
  e o cliente mantém o valor do baseline.
- `decodeSnapshot` falha se o `baselineTick` ≠ 0 e o baseline passado não for desse tick; o chamador lê
  `readSnapshotHeader()` antes para achar o baseline (e manda `FullStateRequest` se não tiver).
- `SnapshotBuffer::sample(renderTick, alpha)`: posição e velocidades em lerp, rotação em slerp;
  propriedades e animação do snapshot mais antigo; objeto que só existe no mais antigo fica como está;
  depois do mais novo devolve o mais novo (sem extrapolar); antes do mais antigo retorna `false`.

## Build e testes

- O `CMakeLists.txt` de `source/extern/gtest` usa `blender_add_lib`/`remove_cc_flag`; no modo
  `NET_STANDALONE` o nosso CMake define versões mínimas dessas macros antes do `add_subdirectory`
  (não editei nada fora de `Network/`). O `main` dos testes é próprio (`tests/net_test_main.cpp`).
- Vetores dourados: `tests/golden/*.bin`, gerados uma vez com `net_tests --update-golden` (ou
  `NET_UPDATE_GOLDEN=1`). Conferidos iguais com GCC 13 e Clang no Linux; falta conferir no MSVC e no
  Emscripten.
- Fuzz: 100 000 entradas com semente fixa (pacotes aleatórios e pacotes válidos com bits trocados) no
  decode de mensagens, mais 100 000 no decode de snapshot delta. Também rodado com ASan/UBSan, limpo.
