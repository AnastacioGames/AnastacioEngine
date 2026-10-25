# Plano de qualidade e performance dos efeitos de render

Revisão por 10 especialistas em 2026-10-24, só leitura do código. Os custos citados são estimativas e ainda não foram medidos. Antes e depois de cada fase, medir com o timer de GPU por passe, que já existe (`KX_EngineProfiler`), em rodadas de cerca de 10 s.

Já feito em 2026-10-24:

- `a0b077fe`: borrão da névoa por profundidade, céu Very Low e o aviso `show_highlight_active`.
- `e6e4a41c`: SSR. O piso PBR passou a refletir, com profundidade em NDC, espessura proporcional à distância e refino do ponto de acerto.

## Status em 2026-10-25 (para retomar)

- **Fase 1:** enviada em `0e71f644`. Falta o aceite visual do usuário com a janela.
- **Fase 2 (base temporal):**
  - feita na névoa, no SSGI e no SSR;
  - está em `RAS_Temporal2DFilter.glsl`, `SetTemporalResolve` e `RenderTemporalResolve`;
  - `RANGE_TEMPORAL_OFF=1` desliga, para comparar antes e depois, e `RANGE_TEMPORAL_DEBUG=1` mostra o log.
- **Fase 3, partes feitas:**
  - **Sombras:** PCF Poisson rotacionado por IGN e dither entre cascatas.
  - **Materiais:** TBN Gram-Schmidt e specular AA de Kaplanyan.
  - **Céu Very Low:** sem a faixa laranja.
  - **Partículas:** LOD por distância.
  - **SSR:** DDA McGuire, fallback para o céu, blur pela rugosidade e reprojeção pelo ponto de acerto.
  - **SSAO:** meia resolução com bilateral.
  - **Bloom:** dual filter com 6 passes.
  - **DOF:** meia resolução.
  - **Névoa:** PCF de 2 taps no sol.
- **Fase 4:** feita.
  - `quality_preset` em `SCENEFXSettings`, com a tabela em `scene.c`.
  - UI no topo do painel Post Processing.
  - Python: `scene.setQualityPreset()` e `getQualityPreset()`.
- **Pendências:**
  - Build limpo do editor e do runtime, porque o DNA mudou (cerca de 45 min). Depois, teste do usuário com a janela, incluindo câmera em movimento para ver rastro, split screen e o jogo dentro do editor.
  - **SSR:** riscos escuros no reflexo da esfera. Conferir se o temporal liga na iGPU (limite de unidades de textura e MSAA).
  - **SSAO:** grão leve; o trace precisa virar float e ganhar temporal.
  - **DOF:** ainda lê profundidade e cor em resolução cheia, por isso ganhou só ~15%.
  - **Bloom:**
    - entrar no preset;
    - o profiler mede só `bloom_image`.
  - **Preset:**
    - trocar durante o jogo não muda resolução, sombras, DOF nem céu até `restart`;
    - escolher pela UI sobrescreve os valores de cada efeito.
  - **Ainda não feito:** GGX VNDF no SSR, flipbook de partículas, IBL com SH9 e fusão de tonemap, FXAA e lente.
  - **Medições:** ainda não refeitas na iGPU; o notebook agora está sem placa dedicada.

## Fase 1: correções baratas (custo de GPU ~0 e risco baixo)

**Pós-processo**

1. Bloom:
   - buffers em RGBA16F, hoje RGBA8 (`KX_2DFilterManager.cpp:704`);
   - os níveis 1 e 2 leem o mesmo B0 e o raio de amostragem é o mesmo em todos, então não geram bloom largo (`:205-216`, `RAS_Bloom2DFilter_bufH.glsl`).
2. Tonemap, em `RAS_Tonemaps2DFilter.glsl`:
   - o Filmic e o Uncharted aplicam gamma duas vezes;
   - o modo "AGX" na verdade é ACES Narkowicz;
   - falta dither no fim da cadeia.
3. Ordem dos passes, em `RAS_2DFilterManager.h:50-71`:
   - o FXAA deve rodar depois do tonemap;
   - névoa, nuvens e DOF devem rodar antes do tonemap.

**Luz e sombra**

4. Sombra:
   - o raio do PCF deve acompanhar o texel do mapa e a cascata (`gpu_shader_material.glsl:3616-3745`);
   - o bias deve escalar com o texel da cascata (`:3583-3594`).
5. A função `dither()` monta um `int bayer[64]` a cada chamada (`:3596`). Trocar por IGN.
6. No IBL, o especular do metal é contado duas vezes (`:3460-3467`). Usar `coat *= (1-metal)` e aplicar o EnvBRDF de Karis.

**Atmosfera**

7. Light Scatter: a máscara lê a profundidade do pixel atual em vez da do ponto amostrado (`RAS_LightScaterring_Buffer2DFilter.glsl:32-45`).
8. Nuvens:
   - o dither está fixo em 1920x1080 (`RAS_Clouds2DFilter.glsl:248-287`);
   - o histórico não é invalidado no resize (`RAS_2DFilterManager.cpp:183-218`).

**Quadro anterior**

9. A cópia de `previous` e do cloud history ignora o offset do viewport, o que quebra o jogo dentro do editor e o split screen (`RAS_2DFilterManager.cpp:161,213`). O `prevViewProjection` é um só por manager (`:484`), então no split screen cada câmera recebe o da outra.
10. O `static grainFrame` é global e avança uma vez por cena (`KX_2DFilterManager.cpp:568`).

**Partículas e destruição**

11. A explosão não limita a mudança de velocidade por massa (`KX_DestructionManager.cpp:1500-1515`). Limitar a ~10 m/s e o `upBias` a 0.5.
12. Partículas mortas continuam sendo desenhadas (`RAS_ParticleShaderCache.cpp:230`). Descartar no vertex shader.
13. Fogo:
    - blend aditivo pré-multiplicado;
    - curva de heat com núcleo branco e amarelo (`:390-442`).

**Web e celular**

14. Criar o RGBA16F de SSGI e névoa só quando houver `EXT_color_buffer_float`, com fallback (`KX_2DFilterManager.cpp:276,455`).

## Fase 2: base temporal compartilhada (o que tira o ruído de vez)

- Classe `RAS_TemporalHistory`, com ping-pong RGBA16F, profundidade, VP anterior e chave por câmera e viewport. Migrar o cloud history para ela.
- Include `RAS_Temporal.glsl` com:
  - reprojeção pela profundidade;
  - rejeição por oclusão;
  - clamp de vizinhança em YCoCg;
  - alpha de ~0.1.
- Aplicar no buffer de baixa frequência de cada efeito, nunca na cor final: névoa, SSGI, SSR e nuvens.
- O jitter tem que variar por quadro. Hoje o do SSGI é estático (`RAS_SSGI2DFilter.glsl:70`).
- Riscos e cuidados:
  - objetos em movimento deixam rastro (sem velocity buffer);
  - corte de câmera e resize precisam invalidar o histórico;
  - na Web não há cópia de profundidade.

## Fase 3: cada efeito

- **SSGI:**
  - pré-passe de profundidade e normal em resolução baixa;
  - jitter desacoplado por quadro;
  - à-trous com variância;
  - padrão de 2 raios, 6 passos e divisor 2.
- **SSR:**
  - ray march em screen space (DDA McGuire);
  - GGX VNDF;
  - fades de borda;
  - fallback para o World;
  - meia resolução com histórico;
  - buffer com `RAS_CANVAS_DIVISOR` e `GetRenderWidth()`.
- **SSAO:**
  - meia resolução em R8;
  - blur bilateral;
  - matrizes como uniform;
  - aplicar só no ambiente.
- **Névoa:**
  - blue noise;
  - PCF de 2 a 4 taps no sol;
  - mais tarde, froxels.
- **Céu Very Low:** usar Chapman analítico (opção B) e depois uma Sky-View LUT.
- **Pós-processo:**
  - bloom dual filter (COD/Unreal);
  - DOF em meia resolução;
  - fundir tonemap, FXAA e lente;
  - ping-pong no lugar de `glCopyTexSubImage2D`.
- **Sombras:**
  - Poisson com rotação e `sampler2DShadow`;
  - dither entre cascatas;
  - PCSS opcional.
- **Materiais:**
  - TBN ortogonalizado;
  - filtro de aliasing especular (Toksvig/Kaplanyan);
  - IBL pré-filtrado com SH9.
- **Partículas:**
  - flipbook;
  - meia resolução;
  - LOD por distância;
  - ordenação ou OIT para a fumaça.
- **Lens Flare:** oclusão por várias amostras e skip pelo CPU. Trocar os hashes `fract(sin)` por hashes inteiros.

## Fase 4: preset global de qualidade

- `quality_preset` em `SCENEFXSettings`:
  - níveis Custom, Very Low, Low, Medium, High, Ultra e Auto;
  - Auto vale Medium no desktop e Low na Web e no Android.
- Tabela única por efeito. Laços compilados com `#define`.
- `scene.setQualityPreset()` em Python e, opcionalmente, um governador térmico.

## Medição

- Dar nomes distintos aos passes de bloom no profiler (`KX_2DFilterManager.cpp:83-86`).
- Medir também `final_copy` e `prev_copy`.
- Ablação, desligando um efeito por vez, em 720p e 1080p, na GPU dedicada e na iGPU.
