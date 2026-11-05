# Revisão: fontes de referência em tecnologia (Claude)

Revisão de 2026-11-04 do mapa de fontes (`docs/fontes-referencia-tecnologia.md`, do Codex), conferindo no código o que ele
diz sobre a engine. Serve de fila de execução: cada item ainda precisa de cena de teste controlada, gerada
por script, e de aprovação.

## O que foi conferido

| Afirmação do mapa | No código |
|---|---|
| Web/Android usam texturas sem compressão; DDS só desktop | Certo ([plano-texturas-dds.md](plano-texturas-dds.md), linha 52) |
| "Prepare Textures" exclui normal maps | Certo: exclusão pelo nome da imagem (`anastacio_prepare_textures.py`, regex de `normal`) |
| `textureGather` no GLSL desktop, ausente no GLSL ES 3.00 | Certo (`gpu_shader_material.glsl` já usa no desktop) |
| Nenhuma chamada a `glInvalidateFramebuffer` | Certo |
| Todos os atributos de vértice em float32 | Quase: cor já é `GL_UNSIGNED_BYTE` normalizado (`RAS_StorageVao.cpp`) |
| Ampliação da resolução dinâmica "a conferir" | Conferido: a imagem reduzida é desenhada esticada na tela com interpolação simples em `RAS_Rasterizer::DrawOffScreen(canvas, offScreen)`. Ponto único para trocar por FSR 1 |

## Avaliação por candidato

1. **FSR 1 (EASU + RCAS) na resolução dinâmica: aceito, primeiro da fila.** Há um ponto único de troca e
   ataca o limite conhecido da iGPU. Cuidados: a UI/HUD tem de ser desenhada depois da ampliação, na
   resolução da tela, senão o texto borra ou recebe nitidez; comparar também contra o filtro Sharpen e o
   `taaSharpen` existentes, não só contra a ampliação simples; Web precisa de variante sem `textureGather`.
2. **DDS na Web do desktop: teste barato antes do KTX2.** Quase todo navegador de desktop expõe
   `WEBGL_compressed_texture_s3tc`. Habilitar o DDS existente lá (com fallback quando faltar a extensão)
   pode dar boa parte do ganho sem biblioteca nova.
3. **Normal maps BC5: aceito, só desktop.** Exige reconstruir Z em todos os nós que leem normal map.
4. **KTX2/Basis: aceito, o mais pesado.** O carregamento hoje entrega imagens decodificadas; falta um
   caminho de upload de blocos comprimidos na Web, e o transcodificador aumenta o `.wasm`. Alvo principal:
   Android (celular não lê BC).
5. **XeGTAO: estudo** para o granulado do SSAO.
6. **Vértices compactos: estudo.** Ressalva: malhas deformadas na CPU reenviam vértices a cada quadro, e
   compactar acrescenta CPU justamente nelas. A engine raramente é limitada por vértices; só com medição.
7. `glInvalidateFramebuffer`, Tracy, Blender pós-2.79: como no mapa.

## Ordem de execução proposta

1. FSR 1: cena com texto, bordas e grade; ampliação simples x Sharpen x FSR 1 em 0,5 / 0,67 / 0,75;
   nitidez e ms de GPU no simulador de PC fraco (`RANGE_WEAK_GPU`).
2. DDS na Web do desktop: N texturas fixas; VRAM, tamanho do pacote e tempo de carregamento.
3. Normal maps BC5: diferença de imagem e memória contra o original.
4. KTX2/Basis no Android.

Este mapa substitui, como próximo passo, a junção de faixas contíguas do Static Batch (A2 em
[revisao-directx-claude.md](revisao-directx-claude.md)), de ganho incerto.
