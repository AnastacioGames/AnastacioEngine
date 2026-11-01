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

- Rig do Mixamo do Enzo em `D:\ProjetoRolimaRacer\personagens - Blender Import(.obj) Export(.fbx) to Mixano\_novo\`:
  `Enzo_sem_dedos.fbx` (25 ossos), `Enzo_dois_dedos.fbx` (41: polegar + indicador), `Enzo_3_dedos.fbx` (49).
  FBX em T-pose, peças separadas com pesos do Mixamo, 20 texturas, 1,695 m, frente −Y.
- **Base padrão: `Enzo_dois_dedos.fbx`**, sem os ossos de ponta (`HeadTop_End`, `*Toe_End`, `*Thumb4`,
  `*Index4`) → 34 ossos, o mesmo esqueleto que o Fabio tinha ao sair do Mixamo. Prefixo `mixamorig:` mantido.
- As outras duas ficam na pasta como opções futuras da biblioteca; o Enzo rigado pelo Mixamo também é o gabarito
  para comparar com o resultado da ferramenta.

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
