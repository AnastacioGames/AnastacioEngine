# Plano de qualidade e performance dos efeitos de render

RevisÃ£o por 10 especialistas em 2026-10-24, sÃ³ leitura do cÃ³digo. Os custos citados sÃ£o estimativas e ainda nÃ£o foram medidos. Antes e depois de cada fase, medir com o timer de GPU por passe, que jÃ¡ existe (`KX_EngineProfiler`), em rodadas de cerca de 10 s.

JÃ¡ feito em 2026-10-24:

- `a0b077fe`: borrÃ£o da nÃ©voa por profundidade, cÃ©u Very Low e o aviso `show_highlight_active`.
- `e6e4a41c`: SSR. O piso PBR passou a refletir, com profundidade em NDC, espessura proporcional Ã  distÃ¢ncia e refino do ponto de acerto.

## Status em 2026-10-25 (para retomar)

- **Fase 1:** enviada em `0e71f644`. Falta o aceite visual do usuÃ¡rio com a janela.
- **Fase 2 (base temporal):**
  - feita na nÃ©voa, no SSGI e no SSR;
  - estÃ¡ em `RAS_Temporal2DFilter.glsl`, `SetTemporalResolve` e `RenderTemporalResolve`;
  - `RANGE_TEMPORAL_OFF=1` desliga, para comparar antes e depois, e `RANGE_TEMPORAL_DEBUG=1` mostra o log.
- **Fase 3, partes feitas:**
  - **Sombras:** PCF Poisson rotacionado por IGN e dither entre cascatas.
  - **Materiais:** TBN Gram-Schmidt e specular AA de Kaplanyan.
  - **CÃ©u Very Low:** sem a faixa laranja.
  - **PartÃ­culas:** LOD por distÃ¢ncia.
  - **SSR:** DDA McGuire, fallback para o cÃ©u, blur pela rugosidade e reprojeÃ§Ã£o pelo ponto de acerto.
  - **SSAO:** meia resoluÃ§Ã£o com bilateral.
  - **Bloom:** dual filter com 6 passes.
  - **DOF:** meia resoluÃ§Ã£o.
  - **NÃ©voa:** PCF de 2 taps no sol.
- **Fase 4:** feita.
  - `quality_preset` em `SCENEFXSettings`, com a tabela em `scene.c`.
  - UI no topo do painel Post Processing.
  - Python: `scene.setQualityPreset()` e `getQualityPreset()`.
- **2026-10-25, aceito com janela** (cena `tools/debug/cenas/criar_cena_efeitos_render.py`):
  - SSR sem riscos na borda da esfera, GGX VNDF e blur da composiÃ§Ã£o que respeita profundidade e normal;
  - SSAO temporal (trace RGBA16F, `TEMPORAL_SSAO`);
  - Bloom com `GPUBLOOMSettings.quality` (Full/Half), Very Low e Low usam Half;
  - tonemap: Filmic, AGX e Uncharted voltaram Ã s curvas originais (a cor jÃ¡ chega em gamma; a "gamma Ãºnica" da Fase 1 deixava a imagem acinzentada), fica sÃ³ o dither;
  - crash: o SSR lia as cores do cÃ©u de `KX_GetActiveScene()` durante a construÃ§Ã£o da cena (ponteiro solto); agora vÃªm do World da prÃ³pria cena em `KX_Scene`;
  - SSR da 3D View (`gpu_shader_fx_ssr_frag.glsl`): fresnel de Schlick, sem jitter e com fade de borda, parecido com o do jogo;
  - preset trocado em jogo pelas teclas 1/2/3 da cena de teste funciona.
- **PendÃªncias:**
  - **DOF:** passe de redução feito e aceito com janela (2026-10-25): `FILTERPASS_CAMERA_DOF_REDUCE` (24) grava cor 2x2 + CoC em meia resolução e o gather lê só ela. RX 6800M, cena de efeitos com `TESTE_EFEITOS_DOF=1`: gather 1,76 → 0,57 ms, DOF total ~1,98 → ~0,91 ms.
  - **Preset:** escolher pela UI sobrescreve os valores de cada efeito.
  - **Flipbook de partÃ­culas** (2026-10-25, aceito com janela): `RangeGPUParticleSettings.flipbook_cols/rows/cycles/random`, `particle_texture()` no preÃ¢mbulo do fragment (mistura os 2 quadros vizinhos; looks e shaders custom tambÃ©m podem usar), `object.particles.flipbook = (colunas, linhas, ciclos, aleatÃ³rio)`. Cena: `tools/debug/cenas/criar_cena_flipbook_particulas.py`.
  - **FusÃ£o de tonemap, FXAA e lente:** adiada. O FXAA lÃª ~12 vizinhos (cada um teria de passar pelo tonemap) e o lens flare fica entre eles; o ganho seria sÃ³ 1-2 cÃ³pias de tela.
  - **IBL com SH9** (2026-10-25, aceito com janela): a luz difusa do World em imagem (equiretangular, angular, cubo) vem de 9 coeficientes projetados uma vez por imagem na CPU (`gpu_world_sh9()`), no lugar de 5 leituras num mip baixo. Junto: o caminho dos nós passava a normal sem negar e iluminava o difuso do lado oposto (cor do chão no topo), inclusive sondas e captura do World. Cena: `tools/debug/cenas/criar_cena_sh9_ambiente.py`. Sondas e captura do World em nós também usam SH9 (9f7e1e0a, aceito com janela; `TESTE_SH9_NOS_WORLD=1`, `RANGE_PROBE_SH9_OFF=1` compara); sondas em tempo real e WebGL seguem nas 5 leituras. O nó Environment Texture quebrava de forma instável por falta do `lodbias` (c5de159a). O ambiente segue o Normal Map do Principled (ef9ac4a3, aceito com janela; `TESTE_SH9_RELEVO=1`).
  - **MediÃ§Ãµes:** ainda nÃ£o refeitas na iGPU. O profiler jÃ¡ separa os passes (`bloom_down0..3`, `bloom_up`, `bloom_image`...).

## Fase 1: correÃ§Ãµes baratas (custo de GPU ~0 e risco baixo)

**PÃ³s-processo**

1. Bloom:
   - buffers em RGBA16F, hoje RGBA8 (`KX_2DFilterManager.cpp:704`);
   - os nÃ­veis 1 e 2 leem o mesmo B0 e o raio de amostragem Ã© o mesmo em todos, entÃ£o nÃ£o geram bloom largo (`:205-216`, `RAS_Bloom2DFilter_bufH.glsl`).
2. Tonemap, em `RAS_Tonemaps2DFilter.glsl`:
   - o Filmic e o Uncharted aplicam gamma duas vezes;
   - o modo "AGX" na verdade Ã© ACES Narkowicz;
   - falta dither no fim da cadeia.
3. Ordem dos passes, em `RAS_2DFilterManager.h:50-71`:
   - o FXAA deve rodar depois do tonemap;
   - nÃ©voa, nuvens e DOF devem rodar antes do tonemap.

**Luz e sombra**

4. Sombra:
   - o raio do PCF deve acompanhar o texel do mapa e a cascata (`gpu_shader_material.glsl:3616-3745`);
   - o bias deve escalar com o texel da cascata (`:3583-3594`).
5. A funÃ§Ã£o `dither()` monta um `int bayer[64]` a cada chamada (`:3596`). Trocar por IGN.
6. No IBL, o especular do metal Ã© contado duas vezes (`:3460-3467`). Usar `coat *= (1-metal)` e aplicar o EnvBRDF de Karis.

**Atmosfera**

7. Light Scatter: a mÃ¡scara lÃª a profundidade do pixel atual em vez da do ponto amostrado (`RAS_LightScaterring_Buffer2DFilter.glsl:32-45`).
8. Nuvens:
   - o dither estÃ¡ fixo em 1920x1080 (`RAS_Clouds2DFilter.glsl:248-287`);
   - o histÃ³rico nÃ£o Ã© invalidado no resize (`RAS_2DFilterManager.cpp:183-218`).

**Quadro anterior**

9. A cÃ³pia de `previous` e do cloud history ignora o offset do viewport, o que quebra o jogo dentro do editor e o split screen (`RAS_2DFilterManager.cpp:161,213`). O `prevViewProjection` Ã© um sÃ³ por manager (`:484`), entÃ£o no split screen cada cÃ¢mera recebe o da outra.
10. O `static grainFrame` Ã© global e avanÃ§a uma vez por cena (`KX_2DFilterManager.cpp:568`).

**PartÃ­culas e destruiÃ§Ã£o**

11. A explosÃ£o nÃ£o limita a mudanÃ§a de velocidade por massa (`KX_DestructionManager.cpp:1500-1515`). Limitar a ~10 m/s e o `upBias` a 0.5.
12. PartÃ­culas mortas continuam sendo desenhadas (`RAS_ParticleShaderCache.cpp:230`). Descartar no vertex shader.
13. Fogo:
    - blend aditivo prÃ©-multiplicado;
    - curva de heat com nÃºcleo branco e amarelo (`:390-442`).

**Web e celular**

14. Criar o RGBA16F de SSGI e nÃ©voa sÃ³ quando houver `EXT_color_buffer_float`, com fallback (`KX_2DFilterManager.cpp:276,455`).

## Fase 2: base temporal compartilhada (o que tira o ruÃ­do de vez)

- Classe `RAS_TemporalHistory`, com ping-pong RGBA16F, profundidade, VP anterior e chave por cÃ¢mera e viewport. Migrar o cloud history para ela.
- Include `RAS_Temporal.glsl` com:
  - reprojeÃ§Ã£o pela profundidade;
  - rejeiÃ§Ã£o por oclusÃ£o;
  - clamp de vizinhanÃ§a em YCoCg;
  - alpha de ~0.1.
- Aplicar no buffer de baixa frequÃªncia de cada efeito, nunca na cor final: nÃ©voa, SSGI, SSR e nuvens.
- O jitter tem que variar por quadro. Hoje o do SSGI Ã© estÃ¡tico (`RAS_SSGI2DFilter.glsl:70`).
- Riscos e cuidados:
  - objetos em movimento deixam rastro (sem velocity buffer);
  - corte de cÃ¢mera e resize precisam invalidar o histÃ³rico;
  - na Web nÃ£o hÃ¡ cÃ³pia de profundidade.

## Fase 3: cada efeito

- **SSGI:**
  - prÃ©-passe de profundidade e normal em resoluÃ§Ã£o baixa;
  - jitter desacoplado por quadro;
  - Ã -trous com variÃ¢ncia;
  - padrÃ£o de 2 raios, 6 passos e divisor 2.
- **SSR:**
  - ray march em screen space (DDA McGuire);
  - GGX VNDF;
  - fades de borda;
  - fallback para o World;
  - meia resoluÃ§Ã£o com histÃ³rico;
  - buffer com `RAS_CANVAS_DIVISOR` e `GetRenderWidth()`.
- **SSAO:**
  - meia resoluÃ§Ã£o em R8;
  - blur bilateral;
  - matrizes como uniform;
  - aplicar sÃ³ no ambiente.
- **NÃ©voa:**
  - blue noise;
  - PCF de 2 a 4 taps no sol;
  - mais tarde, froxels.
- **CÃ©u Very Low:** usar Chapman analÃ­tico (opÃ§Ã£o B) e depois uma Sky-View LUT.
- **PÃ³s-processo:**
  - bloom dual filter (COD/Unreal);
  - DOF em meia resoluÃ§Ã£o;
  - fundir tonemap, FXAA e lente;
  - ping-pong no lugar de `glCopyTexSubImage2D`.
- **Sombras:**
  - Poisson com rotaÃ§Ã£o e `sampler2DShadow`;
  - dither entre cascatas;
  - PCSS opcional.
- **Materiais:**
  - TBN ortogonalizado;
  - filtro de aliasing especular (Toksvig/Kaplanyan);
  - IBL prÃ©-filtrado com SH9.
- **PartÃ­culas:**
  - flipbook;
  - meia resoluÃ§Ã£o;
  - LOD por distÃ¢ncia;
  - ordenaÃ§Ã£o ou OIT para a fumaÃ§a.
- **Lens Flare:** oclusÃ£o por vÃ¡rias amostras e skip pelo CPU. Trocar os hashes `fract(sin)` por hashes inteiros.

## Fase 4: preset global de qualidade

- `quality_preset` em `SCENEFXSettings`:
  - nÃ­veis Custom, Very Low, Low, Medium, High, Ultra e Auto;
  - Auto vale Medium no desktop e Low na Web e no Android.
- Tabela Ãºnica por efeito. LaÃ§os compilados com `#define`.
- `scene.setQualityPreset()` em Python e, opcionalmente, um governador tÃ©rmico.

## MediÃ§Ã£o

- Dar nomes distintos aos passes de bloom no profiler (`KX_2DFilterManager.cpp:83-86`).
- Medir tambÃ©m `final_copy` e `prev_copy`.
- AblaÃ§Ã£o, desligando um efeito por vez, em 720p e 1080p, na GPU dedicada e na iGPU.
