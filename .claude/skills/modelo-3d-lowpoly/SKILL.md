---
name: modelo-3d-lowpoly
description: Modela objetos 3D low poly para jogos na Anastacio Engine (bpy 2.79) a partir de fotos/plantas com 3 vistas (frente, lado, topo), gerando um .range novo com peças separadas, empties de pivô e materiais. Use quando o usuário pedir para "modelar", "criar um modelo 3D" ou "fazer um objeto" (veículo, ferramenta, móvel, prop) estilo Blender.
---

# Modelagem low poly na Anastacio Engine

O modelo sai de um gerador em Python rodando no editor em background, usando o kit `tools/modelagem/lowpoly_kit.py`. A API é a do **Blender 2.79**: não use receitas do 2.8+ (`collection`, `select_set`, `view_layer`, Principled por padrão).

## 1. Referência (3 vistas)
- Use primeiro as imagens que o usuário mandar. Leia cada uma e anote as proporções da vista **lateral** (comprimento x altura), **frontal** (largura x altura) e **superior**.
- Sem imagens: procure com WebSearch "<objeto> blueprint", "<objeto> dimensions mm" ou "<objeto> side front top view", e use as medidas de catálogo ou ficha técnica (números em mm são os mais confiáveis). Cite as fontes.
- Antes de modelar, monte uma tabela de medidas em metros: comprimento, largura, altura total, diâmetro de rodas, entre-eixos etc.

## 2. Convenções
- Escala real em metros. Frente em **+X**, Z para cima, origem da raiz no chão (Z=0) e no centro da largura.
- Um empty raiz com o nome do objeto; as peças são filhas dele.
- Peças móveis (rodas, guidão, timão, portas) ficam penduradas num **empty de pivô** posicionado no eixo de rotação.
- Low poly: cilindros de 12–20 lados. Formas orgânicas saem da silhueta lateral extrudada (`perfil_extrudado`), não de sculpt.
- Um material por cor (`diffuse_color`), com cores contrastantes entre as peças. Shading flat por padrão.
- Nomes no formato `<Objeto>_<Peca>` (ex.: `Moto_Tanque`, `Moto_RodaTras_Pneu`).

## 3. Armadilhas da API 2.79 (já resolvidas no kit)
- `bmesh.ops.create_cone(diameter1=...)` recebe o **raio**, não o diâmetro. Use `cilindro(raio=...)`.
- Depois de `objects.new`, o objeto precisa ser linkado na cena com `scene.objects.link`.
- As normais precisam ser recalculadas; `objeto()` já faz isso.

## 4. Fluxo
1. Copie um gerador existente de `tools/modelagem/` (ex.: `criar_moto.py`) para `tools/modelagem/criar_<objeto>.py`.
2. Rode: `build/bin/AnastacioEngine.exe -b --factory-startup --python tools/modelagem/criar_<objeto>.py -- <saida.range> <relatorio.txt>`.
3. Confira o relatório: compare as dimensões de cada peça com a tabela de medidas e corrija a escala antes de mostrar.
4. Salve num arquivo **novo**; não sobrescreva o .range do jogo sem pedido. Para levar o modelo ao jogo, o usuário faz Append, ou você usa um script separado depois de fazer backup.
5. Só abra o editor com janela quando o usuário pedir. O aceite visual é dele.

## 5. Entrega
Informe o arquivo, as medidas usadas, a hierarquia e os pivôs para animação, e o que ficou simplificado. Ofereça próximos passos: mais detalhes, física ou veículo jogável, LOD.
