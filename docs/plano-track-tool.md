# Plano: Track Tool (pistas e vias com calçada e morros)

Status: planejado em 2026-11-03. Nada implementado na engine ainda. O protótipo funcional está em
dois scripts do RolimaRacer (ver "Ponto de partida").

## Objetivo

Ferramenta da engine para criar **pistas de corrida e vias** a partir de um traçado. O usuário desenha
uma spline e escolhe um perfil. A ferramenta gera a estrada, a calçada, as muretas, o talude, os morros
em volta e a decoração, tudo preso ao traçado. Ao mexer numa curva, tudo se refaz.

No jogo, a pista vira **dado consultável**: distância percorrida, lado, borda e inclinação. Isso
alimenta posição na corrida, voltas, IA, minimapa, respawn e câmera de trilho sem checkpoint manual.

Substitui o fluxo atual do Blender (Curve + Array + Curve modifier). Esse fluxo esconde inclinação e
largura (tilt, radius, torção Minimum), não deixa a engine saber onde fica a borda e gera uma colisão
triangulada única e pesada.

## Ponto de partida (protótipo no RolimaRacer)

- `D:\ProjetoRolimaRacer\Tools\gerar_cenario_pista.py`: gera o cenário em volta de uma pista
  Curve + Array. Já resolve:
  - bordas reais tiradas da malha deformada;
  - terreno com altura global suave (IDW numa grade grossa de 25 m) que encosta na calçada e
    rebaixa sob a estrada;
  - `dist_borda` para nada invadir a pista no miolo das curvas fechadas;
  - muretas com colisão (zebradas nas curvas), casas, postes com fio, placas, público e portais;
  - árvores da cena Kits juntas por bloco de 200 m;
  - câmera de trilho (Follow Path).
- `D:\ProjetoRolimaRacer\Tools\ajustar_inclinacao_pista.py`: torção Z Up + inclinação automática
  para dentro da curva (no máximo 6°). O sinal foi conferido na malha.
- Validação usada: raycast terreno x estrada, props x borda e render Blender Internal sem fog
  (prints). Reaproveitar nos testes da ferramenta.

Lições do protótipo:
- inclinação e largura precisam ser **explícitas por ponto**;
- a geometria precisa ser feita **pela ferramenta** (sweep próprio), não pelo Curve modifier;
- material ou dado reaproveitado pelo nome precisa ser repintado ou recriado ao gerar de novo.

## Decisões

1. **Traçado = objeto Curve (Bezier) do próprio editor**, com torção sempre Z Up, e um
   `PropertyGroup` Python `Object.range_track` com os dados de corrida. Não precisa de DNA novo nas
   fases 1-4. O radius do Bezier é ignorado e a largura vem do perfil e das sobreposições.
2. **Sweep próprio em Python** (sem Curve/Array modifier):
   - amostra o traçado a cada ~1 m;
   - monta o referencial de cada amostra (tangente, lateral horizontal, inclinação);
   - estende a seção do perfil.
   A geometria sai em **blocos de 50-100 m** com UV contínua ao longo da pista (v = s / repetição).
3. **Perfil em faixas**, do centro para fora, simétrico ou separado por lado:
   - Asfalto: largura, faixas pintadas, material.
   - Guia/sarjeta: altura, cor.
   - Calçada: largura, material.
   - Borda: nenhuma, mureta, guard-rail, grade ou muro.
   - Talude: corte ou aterro, inclinação, largura.
   - Morro: altura, ondulação, distância.

   Uma faixa pode ser **paramétrica** ou **por malha**: uma seção desenhada pelo usuário, como a
   `Pista4_Track` atual, que mantém os materiais `Guia`, `Calcada_velha` e `RoadAgua`.
4. **Perfis reaproveitáveis**: coleção na cena + presets JSON em `scripts/presets/range_track/`
   (Rua de bairro, Estrada de serra, Autódromo, Terra).
5. **Trechos (sobreposições por s)**: de s0 a s1, lado E/D/ambos, troca de faixa ou de parâmetro, com
   transição suave de N metros. Exemplos: barranco à esquerda, precipício com guard-rail, ponte.
6. **Pontos de controle por ponto do Bezier**: largura E/D, inclinação Auto ou manual (graus) e piso.
   A inclinação Auto usa a regra do protótipo: ganho por grau de curva, limite e suavização.
7. **Terreno em duas partes**:
   - perto: o talude faz parte do sweep e a costura com a calçada é exata;
   - longe: grade de 5 m com a mesma função de altura do protótipo, rebaixada sob a estrada.
8. **Decoração por regra presa à faixa** (casas na faixa Muro/Casas, árvores na faixa Morro, postes a
   cada X m na calçada, placas e zebra quando a curva passa de Y graus). Fonte dos modelos: Group ou
   cena Kits. Junta por bloco, como o protótipo, para ter poucos objetos e o Auto Static Batch.
9. **Âncoras**: objeto colocado à mão com `range_track_anchor` (pista, s, lado, distância da borda,
   altura) é reposicionado a cada geração.
10. **Gerado x autoral**: todo objeto gerado leva `range_track_owner` e só esses são apagados ao gerar
    de novo. Nada do usuário é apagado.
11. **Colisão**:
    - estrada: malha simples por bloco (asfalto + guia, sem detalhe), STATIC triangle mesh;
    - muretas: idem;
    - decoração e morros: sem física.

    Vértices de borda compartilhados entre blocos evitam o carro bater na emenda (ver "Riscos").
12. **Dado de jogo**: na geração, a ferramenta **cozinha** uma tabela por amostra (s, posição, tangente,
    lateral, largura E/D, inclinação, piso, linha ideal). A forma de leitura no runtime está em
    "A validar".

## Interface (editor)

- Painel **Track** na barra N da 3D View, visível com um traçado selecionado (ou botão "Make Track"
  numa Curve):
  - Perfil (dropdown + salvar/carregar preset) e lista de faixas (UIList: adicionar, remover, subir,
    descer, propriedades da faixa);
  - lista de trechos (s0, s1, lado, sobreposição, transição);
  - inclinação Auto (ganho, limite) e piso padrão;
  - regras de decoração (lista);
  - botões **Generate Road**, **Generate Terrain**, **Generate Decoration**, **Bake Track Data**;
    "Live" refaz só a estrada ao editar (com espera curta).
  - subpainel **Light Probe Volumes** ([plano](plano-track-probes.md)): Preview (conta e caixas no
    overlay), **Generate** (confirma com a conta) e **Clear**.
- Overlay na viewport (bgl): bordas das faixas, marca de s a cada 100 m, setas de inclinação e trechos
  coloridos.
- Operador **Convert Curve+Array to Track**: lê o Bezier e o perfil por malha, passa para Z Up,
  converte radius em largura e calcula a inclinação Auto. Primeiro alvo: Pista_4 e Pista_5.

## Runtime (jogo)

API desejada (nome a confirmar):

```python
track = Range.track.get("Pista_4")
s, lado, dist = track.project(pos)        # metros percorridos, -1/+1, distância do centro
track.pointAt(s); track.tangentAt(s); track.bankAt(s); track.widthAt(s)  # (esq, dir)
track.length; track.racingLine(s)         # linha ideal da IA
track.isOnRoad(pos)
```

Usos no RolimaRacer: posição e voltas por `s` (substitui checkpoints, de forma opcional), IA pela
linha ideal (o "Bézier p/ IA" atual vira entrada), respawn no último `s` válido, zonas de nitro por s,
minimapa (`Bake Map Image` existente) e câmera de trilho.

## Etapas

| Etapa | Entrega | Aceite |
|---|---|---|
| **F0** | Modelo de dados (`range_track`, perfil, trechos) + operador Convert | Pista_4 convertida mantém traçado e perfil; a inclinação Auto bate com o protótipo |
| **F1** | Sweep da estrada (faixas paramétricas e por malha), blocos, UV, colisão | Pista_4 pela ferramenta igual à atual; carro roda sem bater nas emendas; FPS igual ou melhor (rodada ~10 s) |
| **F2** | Talude + morros pelas faixas; trechos com transição | Raycast: 0 ponto da estrada sob terreno; mudar uma curva refaz calçada, talude e morro |
| **F3** | Decoração por regra + âncoras + Kits | Props sem invadir a pista (checagem `dist_borda`); regerar não apaga objetos autorais |
| **F4** | Bake de dados + API Python no runtime + demo de voltas/posição na Pista_4 | `project()` estável em toda a volta; posição igual à do sistema de checkpoints |
| **F5** | API em C++ (grade espacial), linha ideal automática, respawn | Custo de `project()` < 0,01 ms por carro com 20 carros |
| **F6** | Cruzamentos e bifurcações (vias urbanas) | A definir após F5 |

Cada etapa: painel e operadores com testes headless em `tools/debug/track_tool/`, prints sem fog
(Blender Internal) para revisão e aceite visual do usuário com janela.

## Onde mexer

- `source/release/scripts/modules/range_track/`: núcleo puro (amostragem, referencial, sweep, terreno,
  regras, bake), testável em background.
- `source/release/scripts/startup/bl_operators/anastacio_track.py`: operadores e painel, no padrão de
  `anastacio_hlod.py` e `anastacio_lod_auto.py`.
- Depois de editar scripts: copiar para `build/bin/2.79/scripts`.
- F5: módulo C++ no gameengine (ver `docs/code-map-gameengine.md` antes de mexer em KX_Scene e
  KX_PythonInit).
- Integra com o que já existe: HLOD/LOD Auto, Auto Static Batch, Scene Doctor (avisos de colisão),
  Minimap da UI Tree e cooking (`.cooked`).

## Contrato entre módulos

Pacote `source/release/scripts/modules/range_track/` (unidade: metros; "esquerda" = +lateral).
Cada arquivo tem um dono. Quem consome usa só o que está aqui.

### `props.py`: dados salvos no .range

- `bpy.types.Object.range_track` → `RangeTrackSettings`:
  - `enabled`, `profile` (nome do perfil), `sample_step` (1.0), `chunk_length` (75.0), `uv_repeat` (8.0);
  - `bank_auto` (True), `bank_gain` (0.08 grau/grau), `bank_max` (6.0 graus);
  - `points`: coleção `RangeTrackPoint` (`index` do ponto Bezier, `width_left`, `width_right` (0 = usa o
    perfil), `bank_mode` AUTO/MANUAL, `bank_deg`, `surface`);
  - `segments`: coleção `RangeTrackSegment` (`s_start`, `s_end`, `side` LEFT/RIGHT/BOTH, `band` (nome),
    `kind` (troca o tipo; vazio = mantém), `width`, `height`, `slope_deg`, `border_type`, `blend` (m));
  - `rules`: coleção `RangeTrackRule` (`kind` HOUSES/TREES/POLES/SIGNS/KERBS/PEOPLE/CUSTOM, `band`,
    `side`, `spacing`, `density`, `offset`, `source_group`, `source_scene`, `name_prefix`, `curve_min_deg`,
    `seed`, `enabled`);
  - terreno: `terrain_enabled`, `terrain_margin` (260), `terrain_cell` (5), `hill_height` (28),
    `hill_scale` (220), `horizon_enabled`.
- `bpy.types.Scene.range_track_profiles` → coleção `RangeTrackProfile` (`name`, `symmetric`, `bands`:
  coleção `RangeTrackBand`):
  - `name`, `kind` (ASPHALT/CURB/SIDEWALK/BORDER/SLOPE/HILL/MESH), `side` (BOTH/LEFT/RIGHT);
  - `width`, `height` (degrau em relação à faixa anterior), `slope_deg`, `material` (Material);
  - `border_type` (NONE/WALL/GUARDRAIL/FENCE/HOUSE_WALL), `border_height`, `mesh_object` (Object, para
    MESH), `collision`, `lane_count`, `kerb_on_curves`.
  - As faixas vão do centro para fora. ASPHALT tem `width` = meia largura.
- `bpy.types.Object.range_track_owner` (String): nome do traçado que gerou o objeto. Só esses são
  apagados ao gerar de novo.
- `bpy.types.Object.range_track_anchor` → `RangeTrackAnchor` (`track`, `s`, `side` -1/+1, `offset`
  (m além da borda da faixa `band`), `band`, `height`, `follow_bank`, `enabled`).
- `register()` / `unregister()`.

### `frames.py`: amostragem do traçado

`sample(curve_obj, settings) -> Frames`. Torção Z Up e radius ignorado. Listas por amostra `i`:
- `s`, `pos` (Vector, centro), `tan` (unitário 3D), `lat` (horizontal, esquerda), `up` (normal já
  inclinada);
- `bank` (rad, + = cai para a esquerda), `turn_deg` (curvatura com sinal, + = vira à esquerda);
- `wl`, `wr` (meia largura do asfalto), `surface`.

Atributos e métodos:
- `length`, `cyclic`;
- `nearest(x, y) -> (i, s, side, dist_lateral)`;
- `at(s) -> (pos, tan, lat, up, bank)`, interpolado.

### `layout.py`: faixas no espaço

`band_edges(frames, profile, settings) -> Edges`. `Edges.band(i, side, name_or_kind)` →
`(off_in, off_out, z_in, z_out)`: deslocamento lateral a partir do centro e altura absoluta das duas
bordas da faixa, já com inclinação e trechos aplicados.

Outros métodos:
- `Edges.outer(i, side, upto=None)` → borda externa (`off`, `z`) até a faixa `upto` (`None` = última);
- `Edges.point(i, side, off, z_extra=0)` → Vector no mundo;
- `Edges.dist_to_edge(x, y, upto='BORDER')` → distância XY até a borda mais próxima entre os trechos
  vizinhos. É negativa dentro da pista.

### Geração

- `sweep.py`: `generate_road(scene, track_obj, frames, edges) -> [objetos]`. Faixas ASPHALT, CURB,
  SIDEWALK, BORDER e MESH. Blocos de `chunk_length`. Colisão STATIC triangle mesh só onde
  `collision`, com vértices de emenda idênticos.
- `terrain.py`: `generate_terrain(scene, track_obj, frames, edges) -> [objetos]`. Faixas SLOPE e HILL,
  grade longe da pista, horizonte. Garante o terreno abaixo da estrada.
- `decor.py`: `generate_decor(scene, track_obj, frames, edges) -> [objetos]` (regras + Kits) e
  `update_anchors(scene, track_obj, frames, edges)`.
- `generate.py`: `generate(track_obj, parts={'ROAD','TERRAIN','DECOR','BAKE'})`. Apaga os gerados
  (`range_track_owner`), chama os módulos acima e marca o dono. `convert.py`:
  `convert_curve_array(track_mesh_obj) -> curve_obj`.

### `bake.py` e `runtime.py`: dado de jogo

- Bake: Text datablock `TRACK_<nome do traçado>.json`. Formato v1:
  - cabeçalho `{"version":1, "name", "length", "cyclic", "step", "count"}`;
  - arrays planos (floats) `s`, `px`, `py`, `pz`, `tx`, `ty`, `tz`, `lx`, `ly`, `bank`, `wl`, `wr`,
    `el`, `er` (borda da faixa BORDER: deslocamento), `race` (deslocamento lateral da linha ideal);
  - `surface` (ints) + `surfaces` (nomes).
- `runtime.py`: Python puro, sem bpy, referência da semântica. `Track.from_json(text)`:
  - `project(pos) -> (s, side, dist)`;
  - `pointAt(s)`, `tangentAt(s)`, `bankAt(s)`, `widthAt(s) -> (esq, dir)`;
  - `racingLine(s) -> ponto`, `isOnRoad(pos)`, `length`, `surfaceAt(s)`.
- No jogo: `Range.track.get(nome)` (C++, F5) com os mesmos nomes e resultados (tolerância 1 mm). Até lá
  vale `range_track.runtime.get(nome)`.

## A validar antes de F4

- **Como o runtime lê o dado cozido.** Opções:
  - (a) Text datablock importável como módulo Python (o jogo importa textos internos);
  - (b) arquivo `//tracks/<nome>.track.json` incluído no export e no cooking;
  - (c) direto no C++ na conversão da cena (F5).

  Preferência: (a) em F4, por não depender do empacotamento; (c) em F5.
- Se `scripts/modules` está disponível no runtime exportado. Se não estiver, o leitor vai junto ao jogo.
- Teste da emenda de colisão entre blocos com o veículo nativo (Bullet), em alta velocidade.

## Riscos

- **Desempenho do sweep em Python** em pistas de 5 km+: gerar por bloco, e só os blocos tocados no
  modo Live.
- **Emendas de colisão**: vértices exatamente iguais nas bordas dos blocos. Se o Bullet ainda acusar
  impacto, juntar a colisão da estrada numa malha única e manter só o visual em blocos.
- **Undo e tamanho do arquivo** ao regerar muitas vezes: liberar meshes órfãs a cada geração (o
  protótipo já faz).
- **Inclinação com sinal invertido**: a regra de sinal fica num só lugar e é conferida por teste
  automático na malha (borda de dentro mais baixa).
