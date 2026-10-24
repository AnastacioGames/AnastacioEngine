---
name: pintura-textura-lowpoly
description: Pinta e texturiza modelos low poly de jogos na Anastacio Engine (bpy 2.79) com atlas de paleta (uma textura só, cores em blocos com degradê), UV por face, filtro sem interpolação e, quando preciso, textura de imagem com UV unwrap. Use quando o usuário pedir para pintar, colorir, texturizar ou otimizar materiais de um modelo, ou depois do skill modelo-3d-lowpoly.
---

# Pintura e texturização low poly na Anastacio Engine

A API é a do **Blender 2.79** (BGE/GLSL): textura via `material.texture_slots`, UV via `mesh.uv_textures` e `mesh.uv_layers`. Não use nós do 2.8+ por padrão.

## Escolher a técnica
1. **Atlas de paleta (padrão para low poly):** uma textura pequena com todas as cores do jogo. Cada face aponta o UV para o bloco da sua cor. Vantagens: **1 material e 1 draw call** por modelo (ou por cena inteira), recolorir é só trocar a imagem, e o visual fica limpo. Fica em `lowpoly_kit.atlas_de_paleta(objs, nome)`.
2. **Degradê no bloco:** o atlas do kit já escurece a base (`degrade=0.35`) e o UV sobe pela altura Z. Isso dá volume sem luz baked. Use `degrade=0` para cor chapada.
3. **Textura de imagem (detalhe real):** em placas, logotipos, pneus com sulco, madeira ou asfalto, use `bpy.ops.uv.smart_project` (no edit mode do objeto), uma imagem tileável e um material à parte. Prefira 256–512 px em objetos pequenos e 1024 em heróis.
4. **Vertex color:** só quando o usuário pedir; o atlas é mais fácil de editar.

## Regras (dicas de arte low poly)
- **Paleta limitada:** 8 a 16 cores por modelo, com valores (claro/escuro) bem distintos entre peças vizinhas. Teste a leitura em escala de cinza.
- **Cor principal + secundária + acento:** a cor principal na maior área (ex.: pintura da moto), o escuro/metal nas mecânicas e uma cor viva só em pontos pequenos (farol, lanterna, gatilho).
- **Transparentes ficam de fora:** materiais com `use_transparency` (vidro, lanterna) mantêm o material próprio; o kit já os pula. O atlas usa um brilho só, então mantenha à parte qualquer peça que precise de brilho muito diferente.
- **Bordas limpas:** use `use_interpolation=False`, `use_mipmap=False` e `filter_type='BOX'`; o kit já configura. Assim as cores vizinhas no atlas não se misturam.
- **UV no centro do bloco** e um bloco de pelo menos 8–16 px, para evitar o vazamento da cor do lado.
- **Compartilhe o atlas** entre modelos do mesmo jogo, adicionando cores em vez de criar outro. Menos materiais significa menos draw calls (ligue também o Static Batch nas cenas estáticas).
- **Imagens sempre empacotadas** (`image.pack(as_png=True)`) ou salvas em `textures/` do projeto com caminho relativo (`//textures/...`). Nunca deixe caminho absoluto de outra máquina.
- Brilho: `specular_intensity` baixo em borracha e tecido (0.1), médio em pintura (0.5) e alto em metal ou vidro (0.8–1.0).

## Fluxo
1. Abra o .range do modelo em background e rode um script que chame `atlas_de_paleta(list(scene.objects), "<Objeto>_Atlas")`.
2. Salve como arquivo **novo** (`<Objeto>_Atlas.range`); o original com materiais por cor fica para edição.
3. Confira: todos os meshes com o mesmo material, a imagem empacotada e o tamanho do atlas. A inspeção grava em arquivo.
4. O aceite visual é do usuário: abra a janela só quando ele pedir. Para ver a textura na viewport, use o modo Textured/Material.

## Entrega
Informe o arquivo, o tamanho do atlas, o número de cores e de materiais antes e depois, e como recolorir (editar a imagem `<Objeto>_Atlas` no UV/Image Editor ou trocar `diffuse_color` e regenerar).
