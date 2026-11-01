# Personagem automático (Fuse → armature base) — plano

Export do Fuse: Export in new folder + Remove occluded polygons; sem Pack Textures, Triangulate, Flip
Normals nem Combine; Character Scale 1.

Status: planejado em 2026-11-01, revisto com as pastas reais do usuário. Nada implementado ainda.

## Processo de hoje (D:\ProjetoRolimaRacer\personagens)

| Pasta | Etapa | Manual hoje |
|---|---|---|
| 1 - File Original Fuse | `.fuse` (Fuse em D:\SteamLibrary\steamapps\common\Fuse) | criar o personagem |
| 2 - File Exported from Fuse in (.obj) | OBJ + texturas por peça (`<nome>_<Peça>_diffuse/normal/specular/gloss.png`) | exportar |
| 3 - Blender Import(.obj) Export(.fbx) to Mixano | importar OBJ, exportar FBX | sim |
| 4 - File Exported from Mixano To Blender | subir no site, baixar FBX rigado, importar, bake do atlas | sim (site) |
| 5 - Personagem Link | `Group<Nome>.range` pronto para o jogo | sim |
| Animacao - Mixano | animações FBX do Mixamo | — |

Como fica o personagem pronto (conferido em `GroupFabio.range`):

- Armature `Armature` com **22 ossos** `mixamorig:*` (sem dedos: o Mixamo dá 34 e os dedos são tirados).
  O prefixo `mixamorig:` **fica** (as animações da pasta usam esse nome).
- Uma malha `Body` só (peças juntadas), escala 1, um material com o atlas (`UV_Atlas`, 2048, DDS em `textures/`),
  vertex groups dos 22 ossos, modificador Armature.
- LOD em 3 níveis: `Body`, `Bodylod1`, `Bodylod2`.
- Ragdoll: caixas `AnastacioRagdoll-mixamorig:<osso>` do addon Anastacio Ragdoll.
- Empty `Group<Nome>` com propriedade `is_pilot`; armature com `pilot.armature` e `active_ragdoll`; grupo `Group<Nome>`.

## Ideia

Passar pelo Mixamo **uma vez só por tipo de corpo**. Personagens prontos viram **bases** guardadas numa
**biblioteca de esqueletos dentro do editor**. Um personagem novo sai do Fuse em OBJ e um botão liga a malha
na base escolhida (pesos copiados da malha da base), sem o site. Todos têm o mesmo esqueleto: as animações do
Mixamo servem em todos.

## Biblioteca de esqueletos

- Pasta de bases do editor: `2.79/datafiles/characters/` (um `.range` por base, com armature + malha de
  referência com pesos + `base.json` com nome, tipo e medidas). O usuário também pode apontar uma pasta própria
  nas preferências (bases que não vão no pacote público).
- Primeira base: **Fabio** (`GroupFabio.range`, homem adulto). Depois: mulher, criança (ex.: Menina, Menino).
- Botão "Salvar como base" pega um personagem pronto e grava na biblioteca (tira LOD, ragdoll, lógica).
- Atenção ao pacote público: malhas do Fuse/Mixamo têm licença da Adobe; só distribuir bases cujo uso
  permita. Até decidir, a biblioteca do pacote pode ir vazia e as bases ficam na pasta do usuário.

## Fluxo do botão "Criar personagem do Fuse"

1. **Importar o OBJ** do Fuse (pasta 2), aplicar escala/rotação; manter peças (Body, Hair, Tops...).
2. **Escolher a base** (lista da biblioteca; sugestão automática pela altura).
3. **Encaixar o esqueleto**: cópia da armature base com os ossos ajustados à malha nova (escala por
   segmento: tronco, braços, pernas, a partir das medidas da malha).
4. **Copiar os pesos** da malha da base com Data Transfer (vizinho mais próximo / face interpolada) em pose
   de repouso. Fallback: Automatic Weights.
5. **Ligar** a malha na armature (modificador Armature, parent).
6. **Materiais do Fuse**: diffuse/normal/specular por peça; transparência em cabelo, cílios, sobrancelhas.
7. **Atlas**: juntar as peças e fazer o bake num atlas 2048 (`automate_atlas_bake.py`, mesmo resultado da pasta 4).
8. **LOD** 3 níveis (`game.lod_generate_batch`, `anastacio_lod_auto.py`).
9. **Ragdoll**: caixas pelos nomes `mixamorig:*` (`anastacio_ragdoll.py`), sem marcar osso por osso.
10. **Grupo** `Group<Nome>` com o Empty, `is_pilot`, `pilot.armature`, `active_ragdoll`; salvar em
    `5 - Personagem Link/Group<Nome>/`.

Cada etapa é um operador separado (dá para rodar uma só) e o botão encadeia todas, com Undo.

## Teste

Base Fabio + `2 - File Exported from Fuse in (.obj)/_novos/<Nome>/<Nome>.obj` (os 9 personagens atuais; os
antigos ficaram em `_antigos`). Comparar com um
personagem que já passou pelo Mixamo (deformação nas animações Idle, Running, Jumping da pasta de animações).

## Base escolhida: Enzo com dois dedos (2026-11-01)

- Rig do Mixamo do Enzo em `D:\ProjetoRolimaRacer\personagens\3 - Blender Import(.obj) Export(.fbx) to Mixano\_novos\`:
  `Enzo_sem_dedos.fbx` (25 ossos), `Enzo_dois_dedos.fbx` (41: polegar + indicador), `Enzo_3_dedos.fbx` (49).
  FBX em T-pose, peças separadas com pesos do Mixamo, 20 texturas, 1,695 m, frente −Y.
- **Base padrão: `Enzo_dois_dedos.fbx`**, sem os ossos de ponta (`HeadTop_End`, `*Toe_End`, `*Thumb4`,
  `*Index4`) → 34 ossos, o mesmo esqueleto que o Fabio tinha ao sair do Mixamo. Prefixo `mixamorig:` mantido.
- As outras duas ficam na pasta como opções futuras da biblioteca; o Enzo rigado pelo Mixamo também é o gabarito
  para comparar com o resultado da ferramenta.

## Esqueleto e pesos (feito, 2026-11-01, falta aceite visual)

`range_character_autorig`: `load_base(fbx)` (aplica transformações, tira pontas, junta as peças, guarda a altura
do corpo em `arm["autorig_height"]`), `align_to_base` (agora na altura da base), `fit_skeleton` (copia a
armature e estica os braços pela envergadura) e `transfer_weights` (BVH: face mais próxima da malha base,
pesos dos cantos pelo inverso da distância, 4 ossos por vértice, normalizado). O modificador Data Transfer foi
descartado: em `-b` deixou o corpo com um osso só e sapato/cabelo sem peso.

Medidas:
- Juntas do Enzo no corpo do Fabio (rig do Mixamo como gabarito): média 2,3 cm, máx. 4,2 cm (quadril);
  braços caem de 8 cm para 3 cm com o ajuste pela envergadura.
- Nos 9 personagens: todos os vértices com peso; osso dominante entre os 3 mais próximos em 98,1-99,5 %.
- Enzo da ferramenta x Enzo do Mixamo correndo: esqueleto idêntico; malha a 0,64 cm em média (igual parado,
  é a diferença OBJ x FBX), máx. 2,3 cm.
- Animações do Mixamo no rig com transformações aplicadas: localização das f-curves × 0,01 (cm → m).
- Cena para conferir com janela: `tools/debug/autorig_demo_correndo.py`.

Falta: aceite visual (Patty correndo), materiais, atlas, LOD, ragdoll, grupo, painel.

## Biblioteca de esqueletos (feita, 2026-11-01)

`source/release/datafiles/characters/<id>/` (instalada em `2.79/datafiles/characters`), gerada por
`tools/build_skeleton_library.py` a partir dos FBX do Mixamo do Enzo:

| id | Nome | Ossos |
|---|---|---|
| mixamo_two_fingers (padrão) | Two Fingers (thumb + index) | 34 |
| mixamo_no_fingers | No Fingers | 22 |
| mixamo_three_fingers | Three Fingers | 40 |
| mixamo_full_fingers | Full Fingers | 52 |

Formato igual ao dos pilotos do RolimaRacer: rotação 0, escala 1, frente **+Y** (o FBX do Mixamo vem com 90° em X,
escala 0,01 e frente −Y; `load_base` aplica e gira 180° em Z). As ações `CARRO_*` do jogo estão em metros e
servem; as `PLAYER_*` estão em cm (rig antigo com escala 0,01).
Cada `base.range` (~1,3 MB) tem só a armature e `WeightProxy` (malha decimada ~8 mil faces, sem material, UV,
textura, olhos nem cílios), para não redistribuir o personagem do Fuse/Mixamo. `base.json`: nome, ordem,
ossos, altura do corpo. API: `list_skeletons()`, `load_library_base(pasta)`; pastas: USER, LOCAL e SYSTEM
(`datafiles/characters`) + extras.
Proxy x malha completa nos 9 personagens: mesmo osso dominante em 97,5-99,4 % dos vértices, diferença média
de peso 0,008-0,023.

## Ragdoll (feito, 2026-11-01, falta teste no jogo)

- 14 caixas, só ossos grandes (pedido do usuário): Hips, Spine1, Spine2, Head, Arm, ForeArm, UpLeg, Leg, Foot
  (L/R). Mão, dedos, ombro, pescoço e Spine ficam de fora (seguem o pai). Spine1 é obrigatório: a câmera do
  ragdoll do RolimaRacer mira a peça com `foco_camera_ragdoll`, que fica nele.
- Tamanhos medidos na WeightProxy ao gerar a biblioteca (`ragdoll_sizes_from_mesh`, vértices com o osso
  dominante, no espaço do osso, ×0,85) e guardados nos ajustes do addon Anastacio Ragdoll do esqueleto. Ao criar
  o personagem não usa malha: `add_ragdoll(arm)` = addon `generate` + `prepare_physics`.
- Formato do jogo (`GAME_RAGDOLL`, conferido no RolimaRacer.range): nomes `RagdollPart-<armature>-<osso>-Dynamic`
  e pivô `-Empty` (o componente `scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll` exige esse prefixo),
  Copy Transforms nos ossos, juntas cone twist, grupo de colisão 3 / máscara 1 (`fix_ragdoll_collisions.py`),
  2 kg por peça. Outras propriedades do jogo: `Group<Nome>` com `is_pilot` no grupo `GroupAll_Pilotos`;
  armature `Armature<Group>` com `pilot.armature` e `active_ragdoll`; cabeça achada pelo nome do osso (Head).
  `body_ragdoll` não é mais usada pelos pilotos atuais.

## Atlas (feito, 2026-11-01) e o que falta para o grupo

- `build_atlas(peças, pasta, nome)`: sem bake. Cada textura do Fuse vai para uma célula de um atlas 2048
  (corpo 1/4; Tops/Bottoms 1/4 se couber; resto 1/16), UV `UV_Atlas` reposicionado, diffuse (com alfa) e
  normal em PNG, um material só. Olhos e cílios usam a textura do corpo. `join_pieces` junta tudo em `Body`.
  Sara: 5,3 s, atlas conferido.
- Pilotos prontos (RolimaRacer.range, conferido 2026-11-01): material **OPAQUE** `Group<Nome>Material`
  (trocar o CLIP atual para opaco no formato do jogo); malha em duas partes filhas da armature:
  `Body<Group>` e `Body<Group>.001` com `camera_hide_fp` (cabeça + alto do tronco, acima de ~62 % da altura;
  `scripts/VehicleSystem/fp_body_visibility.py` esconde na câmera 1ª pessoa); `aura_rain_effect` no corpo e no
  LOD1; LOD 3 níveis `Bodylod1<Group>`/`Bodylod2<Group>` a 10 m e 25 m; armature só com `pilot.armature`,
  `active_ragdoll` e o componente `scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll` (Active e Debug Lines
  False), física No Collision, sem constraints além das do ragdoll; Empty `Group<Nome>` com `is_pilot` no
  grupo `GroupAll_Pilotos`.
- Próximos: separar a parte `camera_hide_fp`, LOD (`game.lod_generate_batch` ou distâncias fixas 10/25),
  propriedades e componente, grupo, salvar `5 - Personagem Link/Group<Nome>/Group<Nome>.range` + textures/
  (DDS); depois painel e aceite com janela. Os OBJ/FBX ficam em D:\ProjetoRolimaRacer (só na máquina local).

## Personagem pronto (feito, 2026-11-01, falta aceite com janela e teste na corrida)

`create_character(obj, pasta_do_esqueleto, Nome, saída)` faz tudo; linha de comando em
`tools/create_fuse_character.py` (`-- <obj> <Nome> <saída> [esqueleto] [--sem-ragdoll] [--projeto <jogo>]`).
`finish_pilot`: material opaco `Group<Nome>Material`; LOD por decimate 0,45/0,21 a 10/25 m
(`Bodylod1/2<Group>`); `split_fp_part` separa `Body<Group>.001` com `camera_hide_fp` (Head/Neck dominantes +
o que está acima de 62 % da altura, menos braços); `aura_rain_effect` no corpo e LOD1; armature com
`pilot.armature`, `active_ragdoll` e o componente do jogo; Empty `Group<Nome>` com `is_pilot`; grupo com 34
objetos (com ragdoll; corrigido 2026-11-01: grupo = armature + 2 partes + ragdoll, LOD fora, Empty instancia o grupo). Arquivo sem texturas empacotadas (o editor liga autopack em arquivos novos: desligado
aqui), atlas em `textures/`. Os 9 personagens de `_novos` passam, 5,6-6,7 MB cada (GroupFabio: 7,6 MB).
No editor: **File > Import > Fuse Character (.obj)** (`bl_operators/anastacio_fuse_character.py`): escolhe
esqueleto, nome, ragdoll, pasta de saída e pasta do jogo; roda `cli_main` num Blender em segundo plano (não mexe no
arquivo aberto) e liga o grupo pronto na cena, no cursor 3D. Textos em pt/es/ru.
Peso (2026-11-01): o corpo do Fuse (20-26 mil triângulos) não entra no jogo. O nível 0 já sai reduzido para
`BODY_TRIS` = 9000, 6000 deles na parte de cima (`FP_TRIS`, cabeça e peito reduzidos à parte; com 6000 por igual o rosto amassava; Collapse High Quality) e os LOD têm metas fixas, 2500 a 10 m e 900 a 25 m (`LOD_LEVELS`),
perto do Mestre Deen (3450/1268/427). Objetos salvos na camada 2 com a cena mostrando só a 1
(`hide_for_libload`): no LibLoad do jogo entram inativos, prontos para o `addObject`.
No RolimaRacer os pilotos passam a ser carregados por LibLoad (`scripts/pilotos.py`): arquivos em
`5 - Personagem Link/_antigos` e `_novos`; a corrida carrega só os do grid.
Cartão do menu (2026-11-01): `render_card` fotografa a malha cheia (antes da redução) numa pose da animação do jogo
(`CARD_POSE`, ginga da PLAYER_IDLE_CAPOEIRA, quadro 50), luz Sun, fundo transparente, 512x1024 em
`textures/<Nome>_card.png`; sem jogo, pose manual com os braços abaixados.
Foto do botão: `<Nome>_foto.png` 256x256, rosto na mesma pose e luz. No RolimaRacer.range e no trailer os 9 entraram
na escolha (grade 3x4 com os botões a 72 %, cartão `<Nome>` na _menu, botão `btn_Group<Nome>`).
Falta: aceite com janela, teste de queda na corrida, jogador da carreira (3ª pessoa) e cutscene sem ragdoll, tirar os pilotos de dentro do
RolimaRacer.range, DDS.

## Como pôr um piloto novo no jogo (passo a passo, RolimaRacer)

Convenção: um nome só, `<Nome>` (ex.: `Patty`, `Quarta_Feira`, sem espaço). Grupo, Empty e pasta são
`Group<Nome>`; o cartão do menu é `<Nome>` (o `replace_object` de `scripts/_button_shared.py` tira o `Group`).

1. **Fuse:** exportar OBJ com *Export in new folder* + *Remove occluded polygons*, sem Pack, em
   `D:\ProjetoRolimaRacer\personagens - File Exported from Fuse in (.obj)\_novos\<Nome>\<Nome>.obj`.
2. **Gerar** (File > Import > Fuse Character no editor, ou linha de comando):
   ```
   buildin\AnastacioEngine.exe -b --factory-startup --python tools\create_fuse_character.py -- ^
     "<...>\_novos\<Nome>\<Nome>.obj" <Nome> ^
     "D:\ProjetoRolimaRacer\personagens - Personagem Link\_novos\Group<Nome>" --projeto D:\ProjetoRolimaRacer
   ```
   Sai `Group<Nome>.range` + `textures/` (atlas, `<Nome>_card.png`, `<Nome>_foto.png`). Conferir no log
   `PERSONAGEM {...}` (sem `aviso`) e os triângulos: 6000 na parte de cima + 3000, LOD 2500/900.
   O `--projeto` é obrigatório: dá o componente do ragdoll e a pose do cartão (animação do jogo).
3. **Lista do jogo:** pôr `"Group<Nome>"` em `PILOTOS_NOVOS` de `D:\ProjetoRolimaRacer\scripts\pilotos.py`.
   Só isso já põe o piloto no sorteio das CPUs e no LibLoad da corrida.
4. **Menu de escolha:** backup dos dois `.range` e:
   ```
   buildin\AnastacioEngine.exe -b --factory-startup D:\ProjetoRolimaRacer\RolimaRacer.range ^
     --python D:\ProjetoRolimaRacer	oolsdicionar_pilotos_menu.py -- <Nome> [<Nome2> ...]
   ```
   Repetir com `RolimaRacer_trailer.range` (é cópia do principal). Cria cartão, botão e foto e redistribui a grade
   (3 colunas, 4 linhas: **cabem 12**; hoje já são 12. Para o 13º, a tela precisa de outro layout, como páginas ou setas).
5. **Conferir sem abrir o jogo:** render da tela de escolha (câmera do `_menu` movida para `Plane.043`) e
   `pilotos.disponiveis()`; depois o usuário testa com janela: prévia no hover, piloto na corrida, queda (ragdoll).
6. **Commit** no repo do jogo: só os scripts com caminho explícito (`.range` não vai pelo git).

Pilotos sem ragdoll (jogador da carreira em 3ª pessoa, `GroupMarco_TP`, e o da cutscene): mesmo gerador com
`--sem-ragdoll`. Ainda falta ligar no jogo (o botão `GroupAldebaran_TP` aponta para um grupo que não existe).
Pastas: pilotos antigos em `5 - Personagem Link\_antigos`, novos em `_novos`; o caminho vem de `pilotos.caminho()`.

## Decisões

- Feitas (2026-11-01): base Enzo dois dedos (34 ossos), no lugar do Fabio; prefixo `mixamorig:` mantido; 22 ossos; LOD 3 níveis; ragdoll pelo
  addon Anastacio Ragdoll; nome `Group<Nome>`; biblioteca de esqueletos dentro do editor.
- Em aberto: quais bases entram no pacote público (licença Adobe); bases de mulher e criança.

## Riscos

- Corpos muito diferentes da base: ombro/quadril podem precisar de ajuste manual (mitigação: várias bases).
- Roupa larga e cabelo: pesos podem esticar; retoque no Weight Paint.
- Validação visual da deformação fica com o usuário (com janela).

## Frente e escala (feito, 2026-11-01)

`range_character_autorig.align_to_base(peças, armature_base)` roda antes de qualquer outra etapa:

- **De pé:** se a malha estiver deitada, gira 90° em X; se ficar de cabeça para baixo (a fatia mais larga,
  os braços em T, cai na metade de baixo), gira 180°.
- **Unidade:** altura acima de 20 = centímetros (Fuse e Mixamo), multiplica por 0,01.
- **Frente da malha:** a peça `Eyes` do Fuse fica à frente do centro da cabeça; sem olhos, a ponta do pé passa
  mais da canela para a frente do que o calcanhar para trás (o eixo dos braços em T é o lado). **Frente da base:** osso
  `LeftFoot` → ponta de `LeftToeBase`. Se forem diferentes, gira em Z para casar. Confiança baixa vira aviso.
- **Posição:** pé no chão, centro em X/Y = 0. Transformações aplicadas (escala 1, rotação 0).
- Medido: o Fabio (base) olha para **+Y**; os OBJ do Fuse olham para **−Y** (giram 180°) e vêm em cm.
  Os 9 personagens de `_novos` (Azeite, Bia, Biel, Celesty, Enzo, Patty, Quarta_Feira, Sara, Tio) passam,
  olhos e pés concordando (pé à frente da canela 9-16 cm); alturas 1,68-1,80 m.
  A diferença de altura entre corpos não é corrigida aqui: é o encaixe do esqueleto (etapa 3 do fluxo).
- Teste `tools/debug/teste_autorig_alinhar.py`: como vem, de costas, de lado, deitado para os dois lados e de
  cabeça para baixo → PASS.

## Ordem de implementação

1. Importar OBJ, copiar pesos e ligar, com o Fabio como base (testável sem janela).
2. Encaixe do esqueleto.
3. Materiais, atlas, LOD, ragdoll e grupo (encadear as ferramentas que já existem).
4. Biblioteca de esqueletos + "Salvar como base" + painel com botão único; doc de uso.
