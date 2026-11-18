# Personagem v2 — rosto com Impostor de Caixa e mãos que dobram (plano)

Criado em 2026-11-17. Substitui, para os pilotos novos, o fluxo de um botão só de
[personagem-auto-rig-plan.md](personagem-auto-rig-plan.md) (que continua valendo para o que não muda aqui).

## Por que refazer

| Problema | Causa no gerador atual (`range_character_autorig.py`) |
|---|---|
| Rosto feio de longe | cabeça + peito reduzidos juntos para 6000 tris no nível 0 e para 2500/900 nos LOD (`decimate_to`, `LOD_LEVELS`); o Collapse destrói olhos, boca e nariz |
| Dedos esticam e quebram | resto do corpo (com as mãos) cai para 3000 tris; esqueleto **dois dedos** (só polegar e indicador): médio, anelar e mínimo seguem a mão e atravessam o volante; os pesos dos dedos vêm da `WeightProxy` decimada (~8 mil faces), pobre nos dedos |
| Billboard da cabeça (teste de ontem) fora do ângulo | o Flat Impostor gira para a câmera; a cabeça precisa seguir o osso. O **Impostor de Caixa** usa os eixos do objeto e já foi testado preso a osso (changelog 2026-11-17) |

## Regra de trabalho

- Uma etapa por vez, cada uma com **arquivo de checkpoint** e aceite antes da próxima.
  Pasta de trabalho por personagem: `D:\ProjetoRolimaRacer\personagens\6 - Personagem v2\<Nome>\`
  com `01_importado.range`, `02_esqueleto.range`, ... Refazer uma etapa = abrir o checkpoint anterior.
- Cada etapa vira uma função em `range_character_autorig.py` (ou módulo novo `range_character_v2.py`)
  e um script de linha de comando; o botão único só volta no fim, encadeando as etapas aprovadas.
- Validação em background (render/medida); janela só quando o usuário pedir.

## Etapas

| # | Etapa | Saída | Estado |
|---|---|---|---|
| 0 | Exportar do Fuse (Export in new folder + Remove occluded polygons, sem Pack) | OBJ + PNGs por peça | usuário |
| 1 | Importar e limpar: frente −Y → **+Y**, cm → m, mesma altura para todos, pé no chão, transformações aplicadas; materiais novos por peça | `01_importado.range` | feita no Enzo, falta aceite |
| 2 | Esqueleto: escolher base da biblioteca (proposta: `mixamo_full_fingers`, 52 ossos) e encaixar (`fit_skeleton`, `fit_thumbs` estendido para todos os dedos) | `02_esqueleto.range` | feita no Enzo, falta aceite |
| 3 | Pesos: corpo pela malha base; mãos refeitas pelos ossos encaixados; pescoço/cabeça (`limit_head_weights`) | `03_pesos.range` | feita no Enzo, falta aceite |
| 4 | Separar a cabeça: plano abaixo do queixo/base do crânio; objeto `Cabeca` rígido no osso Head | `04_cabeca.range` | feita no Enzo, falta aceite |
| 5 | Mãos: proteger mãos e dedos da redução (grupo de vértices no Decimate) + pose de pegada (volante/guidão) para teste | `05_maos.range` | feita no Enzo, falta aceite |
| 6 | Atlas do corpo (sem a cabeça) e material opaco | `06_atlas.range` | feita no Enzo, falta aceite |
| 7 | Redução e LOD do corpo (mãos protegidas) | `07_lod.range` | feita no Enzo; falta testar LOD com armature no jogo |
| 8 | Impostor de Caixa da cabeça: `object.bake_box_impostor` com Use as LOD; nível 0 = cabeça cheia do Fuse | `08_impostor.range` | feita no Enzo, falta aceite |
| 9 | Fechar o piloto: ragdoll, `camera_hide_fp`, cartão/foto, grupo, DDS, `Group<Nome>.range` | piloto pronto | **Enzo finalizado e no jogo** (2026-11-17) |
| 10 | Teste no jogo: perto, longe, cabeça virando (head_look), mãos no volante, queda | aceite | Enzo aceito pelo usuário no jogo; falta só ver a queda do ragdoll |

## Passo a passo (vale para todo personagem)

Pasta de trabalho: `D:\ProjetoRolimaRacer\personagens\6 - Personagem v2\<Nome>\`.

### Receita rápida (Enzo finalizado em 2026-11-17)

Tudo em background, uma etapa por vez, conferindo a imagem `NN_*.png` de cada uma (detalhes nas seções abaixo).
`E = build\bin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py --` e `P = "<pasta de trabalho>"`:

| # | Comando | Conferir |
|---|---|---|
| 0 | Fuse: Export in new folder + Remove occluded polygons, sem Pack → OBJ + PNGs | — |
| 1 | `E importar <obj> P` | `01_importado_*.png`: de frente para +Y, 1,672 m, pé no chão, cabelo escuro sem brilho |
| 2 | `E esqueleto P` | `02_maos.png`: **dedão** no lugar, dedos retos no centro |
| 3 | `E pesos P` | `03_maos_*`: mãos abrem e fecham sem rasgar |
| 4 | `E cabeca P` | `04_cabeca_*`: corte 2,2 cm sob o queixo / 1 cm sob o crânio; pescoço em degradê sem quina a ±40° |
| 5 | `E maos P` | `05_maos_*`: dedos fechados no volante e no guidão |
| 6 | `E atlas P` | `06_atlas_*`: atlas + AO; AO some na emenda e o tom do pescoço = o da cabeça |
| 7 | `E lod P` | `07_*`: corpo 4491, LOD 2500/900, sem buraco sentado; anel do corte travado |
| 8 | `E impostor P` | `08_comparacao.png`: impostor no ângulo certo |
| 9 | `E fechar P <Nome>` | `09_card_foto.png`; info: `cabeca_no_corpo.soldados` > 0, `primeira_pessoa_tris` > 0, 28 peças de ragdoll |
| 10 | runtime invisível: `10_teste/rodar_instalado.py`, `rodar_sem_corte.py`, `rodar_fp.py` (trocar o nome) | IK do triciclo, `maos_<Nome>`, ragdoll válido; emenda de perto; impostor antes do LOD1 do corpo; 1ª pessoa só pernas e braços |
| 11 | (não usar, ver Etapa 11) `E corpo P <Nome>` (`--dist 20 --lod2 15 --res 512`) | info: cartão a 20 m, Cabeca invisível a 21 m, `lod_max_ragdoll` corpo 2 / cabeça 1; grava `10_impostor_corpo.range` e o cartão no `09_piloto` |
| 12 | Instalar: backup de `5 - Personagem Link/_novos/Group<Nome>` em `5 - Personagem Link/_backup/`, copiar `09_piloto` inteiro para lá | testar numa corrida |

O piloto final tem: nível 0 do corpo com a cabeça cheia soldada (sem emenda) dividido em `Body<Grupo>` (pernas e
braços) + `Body<Grupo>.001` (cabeça e tronco, `camera_hide_fp`, de longe invisível); LOD1/LOD2 sem cabeça;
`Cabeca<Grupo>` invisível de perto e Impostor de Caixa de longe (troca antes do LOD1); IK do triciclo
(`IK_tri`/`ROT_tri`, `ik_ph`, `ik_pole_*`), `maos_<Nome>`, `MAOS_VOLANTE/GUIDAO.<Grupo>`; ragdoll; cartão/foto; DDS.

### Etapa 1 — importar e limpar (feita e conferida no Enzo, 2026-11-17)

```
build\bin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  importar "<...>\2 - File Exported from Fuse in (.obj)\_novos\<Nome>\<Nome>.obj" ^
  "D:\ProjetoRolimaRacer\personagens\6 - Personagem v2\<Nome>"
```

Sai `01_importado.range` + `01_importado_frente.png` e `_lado.png`. Conferir no log `PERSONAGEM_V2`:
`escala 0.01`, `frente_malha -Y` → `frente_depois +Y` (giro de 180°), `altura` = `altura_base` (1,672 m).

O que a etapa corrige no OBJ do Fuse (`range_character_v2.import_fuse`):

| Vem do Fuse | Fica |
|---|---|
| centímetros (~167 de altura), rotação 90° em X | metros, escala 1, rotação 0 (transformação aplicada), pé no chão, centro em X/Y = 0 |
| frente −Y | frente **+Y** (como os esqueletos da biblioteca) |
| cada personagem com a sua altura | **todos com a altura da base** (1,672 m), medida sem cabelo/chapéu/óculos/máscara |
| material do importador OBJ (`Ka 0`, alpha 0 com transparência, normal como bump sRGB, especular 1,0, gloss ignorado): renderiza **preto** | material **novo** por peça: diffuse; normal map de verdade (Non-Color, tangente); especular pelo mapa (força 0,2); gloss → dureza (0,5); metal 0; opaco |
| cabelo e cílios sem recorte | `Hair` e `Eyelashes` (material próprio) recortam pelo alfa (`CLIP`) |

Peças do Enzo: Body 15 990 tris, Hair 4586, Eyes 1520, Bottoms 878, Tops 684, Shoes 680, Eyelashes 106.

Render de conferência: cena temporária com **cópias** dos objetos, motor Blender Render e camada 1 nas
lâmpadas. Com o próprio objeto ligado em duas cenas, ou com o motor Game herdado, o render sai preto.

### Etapa 2 — esqueleto (feita no Enzo, 2026-11-17)

```
build\bin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  esqueleto "D:\ProjetoRolimaRacer\personagens\6 - Personagem v2\<Nome>" [mixamo_full_fingers]
```

Abre `01_importado.range`, grava `02_esqueleto.range` (armature `Armature`, 52 ossos, malha ainda solta) e
`02_maos.json`. Gráfico das mãos (malha cinza + ossos por dedo, vistas de cima e de frente):
`python tools/personagem_v2_maos.py 02_maos.json 02_maos.png`.

O que faz (`range_character_v2.fit_skeleton_v2`):
1. Traz o esqueleto da biblioteca e estica braços/mãos pela envergadura (`autorig.fit_skeleton`, já existia).
2. `fit_fingers` nos **5 dedos**, cada um uma linha **reta** pelo centro do dedo (dedo torto no repouso dobra torto):
   - Indicador a mínimo: a malha `Body` é cortada (bisect) em fatias de 3 mm ao longo da mão; cada dedo vira um
     anel fechado separado; o centro do anel é ligado ao dedo da base mais próximo; a linha é o eixo principal
     desses centros, até a ponta do dedo na malha. Tentativas que falharam (2026-11-17): centro por junta
     (zigue-zague), 2 cortes perto da linha da base e vértices perto da linha (pegavam o dedo vizinho: no lado
     direito do Enzo a linha da base passa 8 mm fora do centro), separar por vão entre vértices (malha esparsa).
   - Dedão: eixo principal dos vértices a até 1,6 cm da cadeia, refeito 4 vezes.
   - O nó do dedo (dentro da palma) entra projetado na linha; as juntas mantêm as proporções da base.
   - Trava: eixo medido a mais de 25° do dedo da base é descartado (aviso, fica o da base).
3. Conferir no log: `avisos` vazio, `dedos_mm` (deslocamento de cada osso) até ~1 cm. No gráfico: cada cadeia
   dentro do seu dedo, reta, terminando na ponta; **dedão** acompanhando o dedo nas duas vistas.

Enzo: o esqueleto da biblioteca é dele mesmo, então só os dedos mexem (1-10 mm). Nos outros personagens
os braços também mudam: conferir o gráfico com atenção (histórico: dedão fora do lugar nos pilotos antigos).

### Etapa 3 — pesos (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  pesos "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>"
```

Abre `02_esqueleto.range`, grava `03_pesos.range` (peças ligadas na armature) e renders das mãos
`03_maos_<Lado>_<aberta|fechada>_<frente|baixo>.png` (juntar numa grade `03_maos.png`).

O que faz (`range_character_v2.weights_v2`):
1. Corpo: pesos da malha da base (`autorig.transfer_weights`, face mais próxima, 4 ossos por vértice).
2. Mãos: `finger_weights` refaz cada vértice da mão pelos **nossos ossos encaixados**: o dedo mais próximo
   (até 11 mm do eixo; dedão 17 mm) fica só com as falanges dele, misturando ±4 mm nas juntas; na palma
   degradê de `Hand` para a 1ª falange (de 10 mm antes do nó até 6 mm depois). Pulso/antebraço não mudam.
   Os pesos copiados da base decimada esticavam e quebravam o dedo ao dobrar.
3. Pescoço/cabeça: `autorig.limit_head_weights` (como no gerador antigo).
4. Conferir no log: `sem_peso` vazio; `maos_vertices` ~500 por mão. Nos renders: mão fechada (pose de teste
   `pose_grip`, dedos 55/70/50°) com os dedos inteiros, sem esticar nem afinar na junta.

Enzo: 536/534 vértices refeitos, nenhum sem peso; mão fechada sem esticar.
`pose_grip` gira cada falange em volta de um eixo **fixo por dedo** (medido no repouso), como rotação local do osso. Com o eixo recalculado pela direção já dobrada, a ponta (3ª falange) voltava em vez de dobrar (apontado pelo usuário).
Atenção: a câmera do render usa `to_track_quat('-Z', 'Y')` (Y é o cima da câmera); com `'Z'` a imagem saía
de cabeça para baixo e parecia que os dedos fechavam para as costas da mão.

### Etapa 4 — separar a cabeça (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  cabeca "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>"
```

Abre `03_pesos.range`, grava `04_cabeca.range` e renders `04_cabeca_<corte|repouso|virada>_<frente|lado|atras>.png`
(grade `04_cabeca.png`; no `corte` a cabeça sai em vermelho).

O que faz (`range_character_v2.split_head`):
1. **Corte geométrico**: plano inclinado que passa **2,2 cm abaixo do queixo** na frente e **1 cm abaixo da base do
   crânio** (cabeça do osso Head) atrás (altura aprovada pelo usuário; 1 cm mais alto ficava curto). A malha é
   **cortada no plano** (bisect, pesos/UV interpolados) antes de separar: emenda reta. Só separar faces
   inteiras deixava a borda serrilhada, que dobrava ao virar a cabeça. Faces acima do plano vão para a cabeça. Mandíbula, queixo e boca inteiros na cabeça;
   o pescoço fica no corpo e dobra.
   Não usar corte por peso do Head (>= 0,5): passava pela boca, queixo e lábio de baixo ficavam no corpo e
   rasgavam ao virar a cabeça (testado e descartado).
2. Cabelo, olhos, cílios e acessórios de cabeça (chapéu, óculos, máscara, barba) vão inteiros; tudo vira o
   objeto **`Cabeca`**.
3. `Cabeca` é **rígida, presa ao osso Head** (parent BONE, sem pesos nem modificador Armature): é o que o
   Impostor de Caixa precisa (o cartão não tem pesos; deformado pela armature ficaria na pose T).
4. Emenda: o anel de vértices do corpo na borda do corte passa a pesar 100 % Head (não abre ao virar).
5. Conferir: `anel_emenda` dezenas de vértices (Enzo: 36; centenas = corte serrilhado); nos renders, corte
   abaixo do queixo, nada do rosto no corpo; cabeça virada (pescoço 15°, cabeça 15° + 40° de giro) sem fresta.

Enzo: cabeça 15 196 tris (rosto ~9 mil + cabelo 4,6 mil + olhos 1,5 mil), corpo 7080, emenda 38 vértices.

### Etapa 5 — mãos para o jogo (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  maos "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>"
```

Abre `04_cabeca.range`, grava `05_maos.range` e renders `05_maos_<pegada>_<Lado>_<frente|ponta>.png` (grade `05_maos.png`).

1. `protect_hands`: grupo de vértices **`proteger_maos`** (mãos e dedos = 1, degradê no pulso). A redução da
   etapa 7 usa como trava, para não quebrar o formato dos dedos.
2. `make_grip_actions`: duas actions só com os ossos dos dedos (fake user) com o **movimento de fechar a mão**:
   quadro 1 aberta (repouso) → quadro 12 fechada na barra. No jogo, numa camada acima da animação de dirigir:
   ```python
   # pegar o volante (fica fechada no fim)
   arm.playAction("MAOS_VOLANTE", 1, 12, layer=2, play_mode=bge.logic.KX_ACTION_MODE_PLAY)
   # soltar
   arm.playAction("MAOS_VOLANTE", 12, 1, layer=2, play_mode=bge.logic.KX_ACTION_MODE_PLAY)
   ```
   - **`MAOS_VOLANTE`** (barra de 3,2 cm, aro do volante) e **`MAOS_GUIDAO`** (2,4 cm).
   - Cada falange gira (eixo fixo do dedo, rotação local) até a ponta encostar numa barra virtual posta na
     palma, junto da base dos dedos (meia grossura do dedo 6,5 mm). Dedão deitado ao longo do aro (10/15/20°).
3. Conferir: nos renders (vista de frente) os dedos abraçam a barra e as pontas chegam embaixo dela; no guidão
   fecham mais. Enzo: dedos 16-28° / 34-60° / 50-74° por falange.

Falta (etapas 9-10): ligar as actions no jogo (camada só dos dedos sobre `CARRO_*`) e conferir a mão no volante
de verdade. Pegada do dedão por baixo (guidão de moto/bicicleta) fica para depois, se precisar.

### Etapa 6 — atlas do corpo (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  atlas "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>" [<Nome>]
```

Abre `05_maos.range`, grava `06_atlas.range`, `textures/Group<Nome>_diffuse.png` e `_normal.png` (2048) e
render `06_atlas_frente/lado.png`. O nome sai da pasta de trabalho se não for passado.

1. `atlas_body`: tudo menos a `Cabeca` → `autorig.build_atlas` (corpo 1/4, roupas 1/4, resto 1/16) e
   `autorig.join_pieces` → malha **`Body`** com o material **`Group<Nome>Material`** opaco (brilho 0,2, sem metal,
   normal Non-Color), como o `finish_pilot` antigo.
2. **Bake de AO** (sombras de contato), como o modo Combined do addon `automate_atlas_bake` do processo antigo
   (`bake_ao_into_atlas`): Blender Render, AO por raytrace com 16 amostras, distância 0,25 m (o padrão de 10 m
   deixava tudo cinza), assado no UV do atlas e multiplicado na cor com força 0,5 (`1 - (1 - ao) * 0,5`). A Cabeca
   entra como obstáculo (pescoço sob o queixo). Gera `Group<Nome>_ao.png` e guarda `Group<Nome>_diffuse_sem_ao.png`.
   Esquecido na 1ª versão da etapa (apontado pelo usuário).
3. A `Cabeca` fica com os materiais do Fuse (Body, Hair, Eyelashes): a cabeça de perto tem a textura cheia e o
   impostor assa dela.
4. Conferir: no `_ao.png` pele/roupa claras com cantos escuros (axila, gola, cós, entre os dedos); render igual ao da etapa 1 com sombra leve nos cantos; `materiais_cabeca` com Body/Hair/Eyelashes.

Enzo: Body 9322 tris (corpo 7080 + regata 684 + bermuda 878 + chinelo 680).
Limites: o atlas só tem cor e normal (o mapa de especular/gloss do Fuse fica de fora; brilho fixo 0,2). A textura
do corpo do Fuse vai inteira para 1/4 do atlas, inclusive a parte do rosto, que agora só a cabeça usa.

### Etapa 7 — redução e LOD do corpo (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  lod "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>"
```

Abre `06_atlas.range`, grava `07_lod.range` e renders `07_lod_*.png`, `07_Bodylod1/2_frente.png`, `07_maos_*.png`
(grade `07_lod_grade.png`).

1. `reduce_body`, nível 0 em duas passadas (Decimate Collapse, High Quality, grupo com Invert = trava; a razão é
   acertada em algumas tentativas, porque a trava muda ratio → triângulos):
   - 1ª: resto do corpo a **3000** com as mãos inteiras travadas (`proteger_maos`);
   - 2ª: mãos a **~1500** com só as juntas travadas (`joint_weights` → grupo `proteger_juntas`): 1 a até 4 mm de
     cada junta dos dedos e do nó, caindo a 0 em 10 mm (meio das falanges, palma, costas da mão); ponta do dedo
     0,6; pulso/antebraço e todo o resto do corpo 1 (sem trava no antebraço saía um bico no pulso; sem trava no
     resto a 2ª passada comia o corpo em vez das mãos).
2. LOD por cópia do corpo cheio, reduzida por igual (sem trava): `Bodylod1` 2500 tris a 10 m, `Bodylod2` 900 a 25 m.
   Antes de reduzir, `remove_hidden_faces` tira da cópia cheia as **faces que nunca aparecem** (pedido do
   usuário): de cada face saem 64 raios (dos dois lados); se nenhum escapa do personagem (malha + Cabeca) **na
   pose de descanso e na pose sentada do jogo**, a face sai (forro da roupa, pele sob a roupa). Enzo: 828 faces;
   os LOD continuam 2500/900, gastos só no que aparece.
   **Errado (1ª versão):** tirar depois de reduzir, só em repouso. A redução abre frestas finas na roupa que os raios
   não acham; sem a pele de baixo elas viram buraco no ombro com o piloto sentado (visto no jogo na etapa 10).
   Conferir sentado (`lod_sentado`: render do LOD com `bake_seat_pose`), não só em pose T.
   Sobra: marquinhas claras pequenas na borda da cava e na barra da bermuda. O nível 0 não passa por isso.
3. Conferir: `maos_depois` ≈ 1500; render da mão fechada sem quebrar o dedo e sem bico no pulso.

Enzo: 9322 → **4491** (mãos 2584 → 1499), LOD 2500/900. Mão fechada boa; aberta e de perto os dedos ficam mais
facetados (versão só com a 1ª passada: 5583 com mãos 2591).

**LOD com armature no jogo: funciona** (etapa 10, 2026-11-17). O gerador antigo tinha desligado o LOD
(`LOD_LEVELS = ()`) por "LOD de malha com armature via LibLoad aparece em pose T"; no runtime atual o LibLoad do
`GroupEnzo` troca 0 → 1 → 2 (`currentLodLevel`) e o LOD segue a pose sentada.

### Etapa 8 — Impostor de Caixa da cabeça (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  impostor "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>"
```

Abre `07_lod.range`, grava `08_impostor.range`. A `Cabeca` não passa pela redução da etapa 7: o bake sai da cabeça
cheia do Fuse (15 196 tris, texturas originais) em qualquer ordem.

1. `bake_head_impostor`: origem da `Cabeca` no centro da caixa dela (vinha nos pés, do corpo), depois
   `object.bake_box_impostor` da engine: **512 px por vista**, modo Auto (deu **Volume**), normal map, **Use as LOD
   a 10 m** (junto do LOD1 do corpo). Roda em `-b` (Blender Internal), ~41 s. Cartão `Cabeca_box_impostor` na
   camada 20, imagens `Cabeca_imp_color`/`_imp_data` empacotadas.
2. O cartão é a malha do LOD da própria `Cabeca` (presa ao osso Head): não precisa de parent.
3. Conferir no editor invisível (GLSL), mesma câmera, cabeça real × `Cabeca.data = cartão` (a troca do LOD),
   cabeça em 3 poses — roteiro `tools/personagem_v2_compara_impostor.py` (trocar PASTA). **Esconder a
   camada 20**, senão o cartão solto aparece parado na pose de repouso (2ª cabeça).
   Enzo: repouso igual; cabeça inclinada no ângulo certo (o erro do billboard de ontem); de lado/baixo a 75 cm
   faixas na pele e no cabelo (limite do modo Volume; no jogo só entra a 10 m+).
   Para ver o atlas: gravar PNG à mão dos pixels (`save_render` em imagem empacotada derruba o editor).

### Etapa 9 — fechar o piloto (feita no Enzo, 2026-11-17)

```
buildin\AnastacioEngine.exe -b --factory-startup --python tools\personagem_v2.py -- ^
  fechar "D:\ProjetoRolimaRacer\personagens - Personagem v2\<Nome>" [<Nome>] [--projeto D:\ProjetoRolimaRacer] [--sem-ragdoll]
```

Abre `08_impostor.range`, grava **`09_piloto/Group<Nome>.range`** + `textures/` (cópia das texturas usadas, foto e
cartão) + `textures_dds/`. Não mexe no piloto que o jogo usa hoje (a troca é na etapa 10).

`finish_pilot_v2` (como o `finish_pilot` antigo): ragdoll de 14 caixas (`autorig.add_ragdoll`, 28 objetos com os
pivôs); `ArmatureGroup<Nome>` com `pilot.armature`, `active_ragdoll`, componente do ragdoll, skinning na GPU;
`BodyGroup<Nome>` (+ `BodyGroup<Nome>lod1/2`); `Cabeca` com `camera_hide_fp` (só a cabeça some em 1ª pessoa; o
antigo escondia também o alto do peito); Empty `Group<Nome>` com `is_pilot` instanciando o grupo (armature + Body +
Cabeca + ragdoll; LODs e cartão do impostor fora); pose sentada do jogo (`bake_seat_pose`); camada escondida para o
LibLoad; DDS. Imagens do impostor ficam empacotadas (não têm arquivo).

Nomes com o grupo (vários pilotos v2 na mesma corrida não podem repetir nome): a armature vira
`ArmatureGroup<Nome>` **antes** do ragdoll (peças `RagdollPart-ArmatureGroup<Nome>-...`, como os antigos);
`CabecaGroup<Nome>` + `CabecaGroup<Nome>_box_impostor`; materiais da cabeça `<Nome>_Body/_Hair/_Eyelashes`;
actions `MAOS_VOLANTE.Group<Nome>` e `MAOS_GUIDAO.Group<Nome>`.

Triciclo (o que o jogo procura no arquivo do piloto, `animations_manager.ik_triciclo`):
- `add_tricycle_ik`: `IK_tri` em `LeftLeg/RightLeg/LeftForeArm/RightForeArm` (cadeia 2, braços com pole
  `ik_pole_<L/R>.Group<Nome>`) e `ROT_tri` (Copy Rotation) nas mãos, todos **mutados**; alvo `ik_ph.ArmatureGroup<Nome>`
  (no grupo). Os alvos só existem para a engine criar os constraints: o jogo troca pelos `tri_ik_*` do veículo.
- `make_handlebar_action`: **`maos_<Nome>`** = mão fechada do `MAOS_GUIDAO` (quadro 12) num keyframe no quadro 1
  (o jogo toca só o quadro 1, camada 8).
- Ajuste fino das mãos no guidão: `Vehicle_data/ajuste_maos.json` (cena `teste_maos.range` do jogo). Os objetos
  `ajuste_mao_*`/`bancada_*` dos antigos só são o reserva sem esse json: não são gerados.

Foto/cartão (`autorig.render_card`) ajustado para o v2: peça presa a osso segue o osso da cópia na pose da foto;
materiais com recorte por alfa (cabelo, cílios) continuam recortados (opacos saíam brancos).
Conferir: `09_card_foto.png` com cabelo escuro, olhos sem anel branco, cabeça no pescoço.

### Correções 2026-11-18: 1ª pessoa com braços e pescoço sem ponta (no `fechar`)

- **1ª pessoa escondia braços e mãos:** os grupos auxiliares `proteger_maos`/`proteger_juntas` (redução da etapa 7)
  ficavam no corpo com peso 1 e "ganhavam" dos ossos em `split_fp_part`. Agora o `finish_pilot_v2` apaga esses
  grupos do corpo e dos LODs e `split_fp_part` só olha grupos `mixamorig:*`. Parte escondida 17393 → 15860 tris;
  escondida, aparecem braços (desde o ombro), mãos, quadril e pernas (`Enzo/10_teste/fp_final_esc.png`).
- **Pescoço com ponta a 40°:** a alça da regata e o trapézio giravam com a cabeça (borda radial larga do
  `blend_neck` da etapa 4). No nível 0, antes de juntar a cabeça: `blend_neck` com `NECK_EXTRA_UP_CLOSE` 16 cm e
  `limit_neck_radial` (teto do Head fora do cilindro do pescoço, 0 a `NECK_RADIAL_LIMIT` 0,5 raio; excesso vai para
  o Neck). Prints em `Enzo/15_pescoco_fp/` (`folha_teto.png`, `folha_velho_novo.png`). 8/16/24 cm sozinhos não
  mudavam nada; o teto é o que tira a ponta.
- **Peças escondidas no LOD:** `Body<Grupo>.001` de longe agora é `use_invisible_mesh` SEM objeto (antes: triângulo
  minúsculo na origem; e nível invisível COM objeto liga a origem fixa de distância do HLOD na engine). O triângulo de
  perto da `Cabeca` é de área zero com a caixa da cabeça. Motivo: a engine só reavalia o LOD de quem está no quadro.
  Num teste o tronco sumiu de perto uma vez (não reproduzido depois); a mudança é por segurança.

### Etapa 10 — teste no jogo (runtime invisível, Enzo, 2026-11-17)

Cena de teste gerada por script (chão, sol, hemi, câmera, action `CARRO_Main_drive_position` copiada do
`RolimaRacer.range`), runtime invisível pelo `tools/testes_engine/controle.abrir_jogo`, e no jogo:
`LibLoad(09_piloto/GroupEnzo.range, load_actions=True)` + `addObject("GroupEnzo")` + a action de dirigir na
camada 0. Prints de frente, diagonal e lado a 2,5 m, 15 m e 30 m (lente proporcional à distância, o piloto fica do
mesmo tamanho), e das mãos com `MAOS_VOLANTE`/`MAOS_GUIDAO` (quadro 12) na camada 3.

Resultado:
- carrega com 28 peças de ragdoll; LOD do corpo troca 0 → 1 → 2 e segue a pose (sem pose T); cabeça troca para
  o impostor a 10 m, no lugar e no ângulo certos;
- `MAOS_VOLANTE` por cima da action de dirigir fecha os dedos;
- **achado 1:** buraco no ombro dos LOD sentado → remoção de faces escondidas mudou para antes da redução, nas
  duas poses (etapa 7);
- **achado 2:** cabelo grisalho de perto, do lado do sol. Não era a cor (a textura é marrom uniforme), nem DDS, nem
  normal map: era o **especular**, que no runtime clareia o cabelo (no GLSL do editor não). A etapa 1 agora faz
  cabelo e cílios sem brilho (intensidade 0, sem mapa de especular/gloss) e com a cor base = média da textura
  (`clip_base_color`). No Enzo foi corrigido no `06_atlas.range` e refeitas as etapas 7–9.
- sobra: contorno claro fino na ponta das mechas e em volta dos olhos (cílios) de perto; ragdoll caindo não testado
  (o componente precisa do veículo do jogo).

**Pescoço em degradê** (achado do usuário no jogo: ao virar o rosto o pescoço fazia uma ponta quadrada). O
head_look gira só o osso Head (até 40°); a cabeça é rígida no Head e o anel da emenda é 100 % Head, mas logo abaixo o
pescoço do Fuse pesa ~80 % Spine2 / ~20 % Neck: a torção inteira caía na 1ª faixa. `blend_neck` (chamado no fim do
`split_head`, etapa 4, malha cheia) dá peso do Head ao pescoço: 1 no anel → 0 a 8 cm abaixo da base do pescoço
(cabeça do Neck), curva suave, vezes um fator radial (só dentro do cilindro do pescoço, cai de R a 2R; ombro e
peito ficam). Grade de variantes em `Enzo/11_pescoco/grade.png` (2–6 cm ainda dobrava). No Enzo foi aplicado no
`06_atlas.range` (cópia `06_atlas.range.antes_pescoco`) e refeitas as etapas 7–9. Aplicar **antes** da redução: a
etapa 7 junta os vértices do anel (38 → 5 com Head 1).

**Cabeça no corpo de perto** (2026-11-17, após o usuário ver a linha de cor na emenda): o corte separado deixava
a emenda diferente em textura (AO do atlas × textura do Fuse), normal e mapa de normal, e a redução deslocava o
anel. Agora `head_in_body_up_close` (etapa 9): a cabeça cheia volta para dentro do nível 0 do corpo (100 % Head,
materiais do Fuse lendo o UV da cabeça pelo nome), **soldada** no anel (a etapa 7 trava o anel na redução); a
`Cabeca` fica com 1 triângulo invisível e mostra só o impostor, trocando antes do LOD1 do corpo (distância do
LOD1 − distância entre as origens − 0,3 m; Enzo: cabeça 9,07 m, corpo 10 m → no jogo 10 m e 11 m: nunca sem
cabeça, faixa curta com cabeça dupla). Nível 0 do corpo: 19 675 triângulos. Mantidos: `blend_neck` (pescoço em
degradê) e `combine_ao` (AO some na emenda e o tom do corpo vira o da cabeça, ponto a ponto). Não usar os pesos do
Fuse no rosto: o queixo e a boca pesam pouco no Head e a boca entorta ao virar. Conferido no runtime
(`10_teste/rodar_sem_corte.py`). 1ª pessoa: `split_first_person` separa cabeça + alto do tronco (sem os
braços; `autorig.split_fp_part`, mesma altura dos antigos) em `Body<Grupo>.001` com `camera_hide_fp`; os LODs dela
são um triângulo invisível (no antigo as duas partes desenhavam o mesmo LOD). Conferido no runtime
(`10_teste/rodar_fp.py`): escondida, sobram pernas e braços.

**Troca no jogo** (2026-11-17, Enzo): backup do antigo em `personagens/5 - Personagem Link/_backup/GroupEnzo_antes_v2_<data>/`;
a pasta `09_piloto` inteira vira `_novos/Group<Nome>/` (caminhos das texturas relativos). Antes de trocar, comparar
objetos/constraints/actions do antigo × novo (foi assim que faltaram o IK do triciclo e a `maos_<Nome>`).
Conferido no runtime invisível (`10_teste/rodar_instalado.py`): `cons["mixamorig:LeftLeg:IK_tri"]` etc. existem,
`maos_<Nome>` fecha os dedos, ragdoll válido com 14 corpos.

### Etapa 11 — impostor do corpo inteiro como último LOD (no pipeline, 2026-11-18)

**NÃO USAR (medido 2026-11-18, decisão: tirar).** 20 Enzos a 38 m, 3 rodadas alternadas, runtime invisível:
cartão × LOD2 de malha = MainRender 0,14 × 0,21 ms, mas UpdateParents 0,95 × 0,05 ms com o cartão (CPU pior no
total); Animations/Skinning iguais (o esqueleto roda de longe do mesmo jeito). Memória: 2 imagens 1536×1024 sem
compressão ≈ 17 MB por piloto (+ 17 MB da cabeça). Para PC fraco pesa mais a memória (iGPU usa a RAM) do que 899
triângulos. Com `RANGE_WEAK_GPU=16` os números não mudaram (simulador talvez não aja no runtime invisível).
O Enzo instalado voltou a ser o `09_piloto` sem cartão (backup com cartão em `_backup/GroupEnzo_com_cartao_2026-11-18`).
O código (`E corpo`, `lodLevelMax`, travas do ragdoll/abaixar/triciclo) fica: sem `lod_max_ragdoll` nada trava.
Passos do Volume da cabeça: 10 (`HEAD_IMPOSTOR_STEPS`, 2026-11-18; prints 32 × 17 × 10 a 10/15/25 m quase iguais, em
`Enzo/13_passos/comparar_passos_10.png`; Enzo instalado e 09 ajustados). Resolução do impostor da cabeça: **256** (`HEAD_IMPOSTOR_RES`, 2026-11-18): imagens 768×512, ~4 MB/piloto em vez
de ~17 MB; prints 512 × 256 ampliados quase iguais e no tamanho real do jogo (10 m, lente 35) idênticos
(`Enzo/13_passos/comparar_res.png`, `real_10m.png`). `E impostor P --res N` troca. 128 testado (2026-11-18): ampliado serrilha cabelo/rosto, no jogo quase igual; usuário
manteve **256**; 128 só se um dia houver opção "PC muito fraco" (`comparar_res_128.png`). Enzo refeito e instalado
(backups: `Enzo/08_impostor_512.range`, `Enzo/09_piloto_512`, `_backup/GroupEnzo_cabeca512_2026-11-18`).

**Pipeline (`E corpo P <Nome>`, depois do `fechar`):** `v2.bake_body_impostor` abre o `06_atlas.range` (corpo cheio),
pose sentada, corpo + cabeça numa malha no espaço do `Body` e assa o Impostor de Caixa (512, Volume pelo AUTO);
grava só o cartão em `10_impostor_corpo.range`. `v2.add_body_impostor` põe o cartão como último LOD do
`Body<Grupo>` (`BODY_IMPOSTOR_DIST` 20 m, LOD2 puxado para 15 m), níveis invisíveis na `Cabeca<Grupo>` e no
`Body<Grupo>.001` 1 m depois, folga de 0,5 m em todas as trocas e a propriedade de jogo `lod_max_ragdoll` (corpo 2,
cabeça 1). Imagens com o grupo no nome (`Corpo<Grupo>_imp_*`, `Cabeca<Grupo>_imp_*`).
**Ragdoll:** a engine ganhou `KX_GameObject.lodLevelMax` (-1 = sem limite); o componente `Ragdoll` do jogo
(`ragdoll_system/ragdoll.py`, `_cap_lod`) põe o valor de `lod_max_ragdoll` em cada filho ao ligar e -1 ao
desligar. Teste no runtime invisível: caído a 25 e 60 m fica malha deitada + impostor da cabeça (2, 2, 1); desligado
volta ao cartão (3, 3, 2). Varredura 7–25 m ida e volta sem quadro sem cabeça. Enzo reinstalado assim
(backup do teste de ontem em `_backup/GroupEnzo_teste20m_2026-11-18`).
Decisão do usuário (2026-11-18): o caro é cabeça e mãos; só de perto ficam as originais, depois pode ser LOD ou
impostor. Cartão fica a 20 m; listras do cartão e furinhos do LOD1/LOD2 vistos em print ampliado não precisam de
correção. Abaixado/inclinado: `animations_manager._pose_lod_cap` (RolimaRacer 970ecf9) trava em malha como o ragdoll,
porque o cartão só tem a pose sentada. Triciclo: com o IK do triciclo ligado também fica na malha (RolimaRacer
081f3f4, decisão do usuário em vez de um 2º cartão).

Histórico do protótipo:

Ideia do usuário: o piloto passa a corrida sentado, então o Impostor de Caixa (modo Volume) do corpo inteiro **na pose
sentada do jogo** serve de LOD de longe (um cartão no lugar de malha + esqueleto). Roteiros em
`Enzo/12_impostor_corpo/` (fora do pipeline ainda):
- `assar.py`: abre `06_atlas.range` (corpo CHEIO, melhor qualidade; o 08 já é reduzido), pose sentada
  (`bake_seat_pose`), corpo + cabeça viram uma malha estática `CorpoSentado` e assa o impostor. Variáveis:
  `RES` (512 aprovado pelo usuário; 1024 existe), `ORIGEM=pes` (origem nos pés = origem do Body, obrigatório para
  usar como LOD do corpo), `VARIANTE` (sufixo do arquivo). **Cuidado:** antes de juntar, os slots de textura da
  cabeça precisam de `uv_layer` = UV da cabeça (senão cabelo/rosto leem o UV do atlas: sai careca).
- `montar_lod.py`: abre um piloto (`PILOTO`), põe o cartão como nível de LOD do `Body<Grupo>` a `DIST` m, e níveis
  `use_invisible_mesh` (opção pronta do LOD da engine) no `Body<Grupo>.001` e na `Cabeca<Grupo>` na mesma distância;
  `LOD2_DIST` muda o LOD2 (os níveis têm de ser crescentes). Grava em `SAIDA`.
- `comparar.py` / `rodar_lod3.py`: runtime invisível, malha × impostor e troca de níveis.

Resultados:
- O cartão funciona como LOD de um corpo deformado pelo esqueleto (posição e pose certas, sem cabeça dupla).
- Volume de cima: mancha vermelha da regata no short; não é objeto sobre objeto nem alpha (testado sem faces
  escondidas e sem cabelo/cílios); diminui com a resolução (1024 bem menor). Tentativa no shader (tolerância da
  mistura das vistas em texels) não mudou nada e foi desfeita. Causa provável: dilatação da profundidade no bake.
- Engine: `object.bake_box_impostor` ganhou resolução **1024** (bake ~76 s; 512 ~25 s).
- Carros (`carrinho_caixote`): impostor **ruim** em Volume (fecha o caixote, cordas quebradas) e em Box (fotos na
  caixa, rodas duplicadas) — usuário concordou. Para carros: LOD de malha juntando as peças fixas.

Estado no jogo: `_novos/GroupEnzo` = `09_piloto` + impostor do corpo a **20 m** (LOD1 10 m, LOD2 15 m, pedido do
usuário para testar). Usuário: "ficou bom, mas **o corpo fica invisível na hora errada**".

**Para amanhã:**
1. ~~Corpo invisível na hora errada~~ **RESOLVIDO 2026-11-18.** Não era o ponto de medição (corpo e cabeça
   medem de pontos a ~0,5 m um do outro). Era a **histerese**: a engine dá de folga uma % (cena: 10 %) da distância
   entre o nível e o anterior; o corpo (15→20 m) ficava com 0,5 m e a Cabeca (9→20 m) com 1,1 m, então na volta o
   corpo virava malha sem cabeça a 19,5 m e a Cabeca só reaparecia abaixo de 19 m. Correção:
   `v2.match_lod_hysteresis` (cada nível com a sua % para a folga ser `LOD_HYST_BAND` = 0,5 m nas três partes;
   chamada no `finish_pilot_v2`) e a Cabeca/`Body.001` somem `BODY_CARD_HEAD_MARGIN` = 1 m depois do cartão
   (`montar_lod.py`). Varredura no runtime invisível de 7 a 25 m e de volta, passo 0,25 m: sem nenhum quadro sem
   cabeça. Enzo instalado corrigido no próprio arquivo (cópia `GroupEnzo.range.antes_histerese`).
2. ~~Ragdoll~~ feito 2026-11-18 (`lodLevelMax` + `lod_max_ragdoll`, ver acima).
3. ~~Pipeline~~ feito 2026-11-18 (`E corpo`); falta decidir a distância final.
4. Triciclo: o cartão é da pose do carro.

## Pontos a provar antes da etapa 4 (teste pequeno)

1. **Cabeça rígida ou deformada?** O Mixamo não tem ossos de rosto: a cabeça é rígida no osso `Head`.
   O pescoço dobra com `Neck`. Duas formas:
   - (a) cabeça + pescoço presos ao osso `Head` (parent BONE): o impostor funciona sem código novo
     (já testado), mas a base do pescoço pode abrir uma fresta na gola quando o `Neck` dobra.
   - (b) pescoço fica no corpo (deformando) e a peça separada começa logo abaixo do queixo: emenda
     escondida pela própria dobra do pescoço, peça 100 % rígida.
   Teste: os dois cortes num personagem com as animações do jogo (`CARRO_*`, head_look) e render de perto.
2. **LOD com troca para o card** numa peça presa a osso: confirmar que o card do impostor entra como nível
   de LOD sem o modificador Armature (por isso a peça precisa ser presa a osso, não deformada).
3. **Ângulo**: render real × impostor com a cabeça girada pelo osso em 3 ângulos (o erro de ontem).

## Decisões

- Feitas (2026-11-17): personagem de teste **Enzo**; esqueleto **Full Fingers (52 ossos)**; corte da cabeça:
  testar a seleção automática (cabeça + cabelo + o que segue o osso Head), com a alternativa do usuário
  de marcar uma volta de arestas no pescoço (Mark Seam) e pegar tudo acima.
- As animações `CARRO_*` não animam os dedos novos: precisa de uma pose de pegada (action de dedos por cima).

## Em aberto

- Orçamento de triângulos: cabeça cheia (quantos tris o Fuse dá) até qual distância; mãos.
- Distância de troca da cabeça para o impostor.
