# Probe Volume GI (luz indireta por grade de sondas)

Uma caixa de sondas difusas que captura a luz rebatida da cena enquanto o jogo roda. Dentro da caixa,
a luz ambiente dos materiais passa a vir da grade, e não do World ou das sondas manuais. O reflexo
continua vindo das sondas manuais e do World. Fica desligado até existir um Empty com `probe_volume`.

## Como ligar

No editor o recurso se chama **Light Probe Volume**. O jeito rápido: **Add > Light Probe Volume** cria o
Empty pronto, e o painel **Light Probe Volume** (aba Empty)
mostra qualidade, espaçamento, quantas sondas a caixa vai ter, rebatida e as opções avançadas. Em
malhas, a aba Object tem **Skip in Light Probe Volume**. O painel só edita as propriedades abaixo.

1. Adicione um Empty com Display **Cube** e escale-o para cobrir a área (sala, rua, galpão). O tamanho
   da caixa é o Display Size vezes a escala. A grade segue sempre os eixos do mundo: a rotação do
   Empty é ignorada (o console e o Scene Doctor avisam). Sala inclinada pede várias caixas.
2. Em Game Properties, crie `probe_volume` (Float): o espaçamento entre sondas em metros. 0 = 4 m.
3. Rode o jogo. No começo a grade captura rápido até a luz assentar (alguns segundos). Depois
   para de capturar e só volta quando algo muda: um objeto se move, aparece ou some, ou o sol e o
   World mudam. Lâmpadas comuns que mudam não acordam a grade.

O volume pode ocupar a sala inteira, encostando no chão, no teto e nas paredes. A engine empurra para
fora as sondas que ficam em cima de uma superfície e desliga as que ficam dentro de paredes ou caixas.
Isso usa a colisão: parede e chão sem colisão não são vistos (o Scene Doctor avisa). Caixas com colisão
Box ou Convex Hull também contam. As camadas de `probe_volume_ignore_layers` ficam fora desse teste.

## Propriedades opcionais (no mesmo Empty)

| Propriedade | Tipo | Padrão | O que faz |
|---|---|---|---|
| `probe_volume_quality` | String ou Int | do preset | `Low`, `Medium` ou `High` (0, 1, 2): faces por quadro e limite de sondas (64, 128, 256). |
| `probe_volume_bounce` | Float | 0,3 | Ganho de cada rebatida da luz da grade. 0 = só a luz direta rebatida uma vez. Máximo 0,95. |
| `probe_volume_ssgi` | Float | 0,5 | Força do SSGI com a câmera dentro do volume, para não somar a luz duas vezes. |
| `probe_volume_clip_end` | Float | 30 | Distância que cada sonda enxerga. |
| `probe_volume_ignore_layers` | Int | 0 | Camadas (bits) que a grade não captura. |
| `probe_volume_freeze` | Bool | não | Captura uma volta e para (luz fixa, custo zero depois; o console mostra "frozen"). |
| `probe_volume_skip` | Bool, em outro objeto | - | O objeto fica fora da captura. |

Ficam fora da captura sozinhos: física dinâmica, rigid body, veículo e malha deformada (armature ou
GPU Skinning). Porta, elevador ou objeto movido por script entram. Quando um deles anda mais de
0,25 m, as sondas perto dele são capturadas primeiro.

## Preset de qualidade (Scene > Quality)

O preset global limita a grade. Very Low desliga, Low, Medium e High dão o nível igual e Ultra dá
High. Auto dá Medium numa placa dedicada e Low na iGPU, na Web e no Android. Sem
`probe_volume_quality` no Empty, a grade segue o preset. Com ela, a grade usa o menor dos dois. No
preset Custom vale o que o último preset gravou.

Se a caixa precisar de mais sondas do que a qualidade deixa, o espaçamento cresce até caber. Aparece
um aviso no console, e o Scene Doctor oferece gravar o espaçamento novo.

## Custo (desktop, RX 6800M, sala de teste com 72 sondas)

| Qualidade | CPU/quadro | GPU/quadro | Volta completa |
|---|---|---|---|
| Low | 0,50 ms | 0,24 ms | 2,3 s |
| Medium | 0,94 ms | 0,48 ms | 1,7 s |
| High | 1,70 ms | 1,03 ms | 0,9 s |

Na iGPU o custo de GPU é cerca de 16 vezes maior, por isso o Auto usa Low lá. O Performance Report
mostra a etapa como "Probes and reflections (Probe Volume GI)".

## Onde vale e onde não vale

- **Desktop:** a luz da grade é lida por pixel (as 8 sondas em volta do ponto), num shader que só é
  compilado em arquivos com volume (e não no preset Very Low). Material com textura demais para sobrar
  a unidade do atlas usa a luz no centro do objeto.
- O volume de cada objeto é escolhido pela caixa da malha: o que contém a maior parte dela. Uma malha
  só usa um volume: um chão único que atravessa duas salas com volumes separados recebe a luz de uma
  delas. Divida a malha por sala.
- **Web:** a luz é lida no centro de cada objeto, porque lá falta unidade de textura. Sem render em
  half float no navegador, o volume não liga.
- Material com luz ou AO pintados na textura soma com a grade e pode ficar claro demais.
- Sala fechada, toda clara e com rebatida alta perde contraste. Baixe `probe_volume_bounce`.
- A grade não vê objeto menor que o espaçamento: a sombra de contato embaixo dele some. Ligue o SSAO
  (Scene > Effects) para devolver essa sombra.

## Volumes ao longo de uma pista (Track Tool)

Numa pista, em vez de uma caixa gigante (o espaçamento cresce e a luz fica borrada), use o subpainel
**Track > Light Probe Volumes** com o traçado selecionado ([plano](plano-track-probes.md)):

- **Preview** mostra as caixas no overlay e a conta "N boxes, M probes (limit L)", sem criar nada.
  Em laranja, as caixas em que o jogo aumentaria o espaçamento.
- **Generate** cria uma cadeia de Empties `PV_<pista>_000…` no grupo `<pista>_ProbeVolumes`, alinhados
  ao mundo e cobrindo só a faixa da pista (até a borda, mais margem), com as sondas de caixas vizinhas
  nos mesmos pontos. Regerar troca só esses; volumes feitos à mão ficam. **Clear** apaga os gerados.
- Padrão: Medium, 6 m, 4 m acima da pista, limite total 15.000. Uma pista de 1,9 km dá ~120 caixas e
  ~14 mil sondas. Acima do limite, o Generate recusa e sugere o espaçamento que cabe.

## Depuração

`RANGE_PROBE_VOLUME_LOG=1` imprime no console, a cada segundo, o seguinte:
- faces e sondas capturadas;
- ms de CPU e de leitura;
- esperas de leitor;
- tempo de volta;
- luz média das sondas (`light`), que tem de se estabilizar e não crescer sem parar.

A cena de teste se gera com `tools/debug/cenas/criar_cena_probe_volume.py`.

Plano e histórico técnico: [plano-probe-volume-gi.md](plano-probe-volume-gi.md).
