# Plano: Câmera do jogo com foco nativo e pacote "Camera FX"

## Contexto
Hoje a câmera do Range Engine não tem foco nem profundidade de campo. O painel Depth of Field fica escondido no jogo, e `YF_dofdist` só serve para o estéreo. O jogo Rolima Racer compensa isso com scripts Python: `BokehDoF.py` (em `scripts/effects`), `SpeedBlurFX.py` e `DirectionalBlurFX.py` (em `scripts/camera_system`). Cada script procura o carro por conta própria, e alguns ficam fixos no `player_1_2_PC == 1`.

A proposta é levar tudo isso para dentro da engine:
- **Sensor de foco na câmera**: o alvo pode ser um objeto, uma propriedade true, o centro da tela (automático) ou uma distância manual. A câmera devolve a posição e a distância do foco.
- **Um único módulo de efeitos de câmera**, ligado e desligado por efeito: DOF Bokeh, Speed Blur, Directional Blur e a "lente", que tem 3 opções de olho de gato.
- **Tremor de câmera próprio**, somado ao tremor do terremoto do World.

Decisões do usuário: uma câmera ativa (sem tela dividida), configurações na câmera, olho de gato com as 3 opções selecionáveis.

## O que já existe e será reaproveitado
- `Camera` DNA ([DNA_camera_types.h](../source/source/blender/makesdna/DNA_camera_types.h)) já tem `dof_ob` (objeto de foco) e `gpu_dof` (`focus_distance`, `fstop`, `num_blades`). Esses campos serão reaproveitados para foco e abertura, e os campos novos vão em uma struct ao final.
- Padrão de filtro nativo reservado: `FILTERPASS_*` e `reservedPassIndex` em [RAS_2DFilterManager.h](../source/source/gameengine/Rasterizer/RAS_2DFilterManager.h), `Ensure*Filters` em [KX_2DFilterManager.cpp](../source/source/gameengine/Ketsji/KX_2DFilterManager.cpp) (modelo: `EnsureLensFlareFilters`), uniforms em `RAS_2DFilter.cpp` via `BuildInFilters` e atualização por frame em `KX_RenderPipeline::PostRenderScene` (como já é feito com `flare_time`/`flare_sun_x`).
- Tremor: `KX_Camera::SetShakeShift` e `KX_Scene::UpdateEarthquake` ([KX_Scene.cpp:627](../source/source/gameengine/Ketsji/KX_Scene.cpp#L627)).
- Shaders GLSL embutidos via `datatoc` em `Rasterizer/RAS_OpenGLFilters/` (CMakeLists).
- Algoritmos de referência: os shaders do jogo (bokeh com anéis, blur radial em buffer de meia resolução, blur direcional com 24 amostras e peso `pow`).

## Arquitetura

### 1. Sensor de foco (CPU, em `KX_Camera`)
Novos campos na struct `CameraGameFX` (DNA, ao final de `Camera`):
- `focus_mode`: `MANUAL`, `OBJECT` (`dof_ob`), `PROPERTY` ou `AUTO` (centro da tela).
- `focus_prop[64]`: nome da propriedade. Serve de alvo o objeto em que ela existe e é true.
- `focus_smooth`: suavização da distância entre frames.
- `focus_range`: faixa nítida em metros.
- Modo `PROPERTY`: a varredura da cena é espaçada (a cada 0,5 s ou quando um objeto é adicionado ou removido). O alvo fica guardado em cache enquanto for válido, e, se houver mais de um objeto, vale o mais próximo da câmera. Se o objeto for destruído, o sensor volta para `MANUAL` sem travar.
- Modo `AUTO`: raycast físico a partir do centro da tela (ou de `focus_screen` x,y), com distância suavizada. Usar raycast em vez de ler o depth buffer evita travar a GPU.
- Saída calculada 1 vez por frame em `KX_Camera::UpdateFocus()`, chamada no update da cena antes do render: `m_focusPosition`, `m_focusDistance`, `m_focusObject`.

Python (`KX_Camera`):
- `focusMode`, `focusObject` (RW), `focusProperty` (RW), `focusRange` e `fstop`.
- `focusPosition` (RO, Vector), `focusDistance` (RO), `focusScreenPosition` (RO, x,y).

### 1b. Rastreio do foco: a câmera gira no próprio eixo seguindo o alvo
Campo `track_mode` (DNA `CameraGameFX`), com o painel e o Python `cam.trackMode`:
- **OFF**: a câmera não gira sozinha (padrão, para os arquivos antigos não mudarem).
- **LOOK_AT**: só a rotação da câmera se volta para `focusPosition`, suavizada. A posição não muda.
- **DRONE**: LOOK_AT mais o movimento do `update_drone_movement` do jogo (`scripts/camera_system/camera_change.py:430`), convertido para a engine:
  - **Troca de alvo suave (slow parent)**: quando o foco muda de objeto, a rotação faz slerp até o novo alvo, e não pula.
  - **Flutuação (hover)**: um deslocamento local pequeno em seno/cosseno (no jogo: Z `sin(t·2,5)·0,03`, Y `cos(t·1,5)·0,015`) somado à posição, com amplitude e frequência configuráveis.
  - **Inclinação leve (bank)** na direção da curva, proporcional à velocidade angular do giro (opcional).

Parâmetros: `track_speed` (suavização em segundos, independente do FPS: `1 - exp(-dt/τ)`, no lugar do `0.08` fixo por frame do script), `track_up_lock` (mantém o horizonte e não rola), `track_limit` (ângulo máximo em relação à orientação original, ao estilo do `Camera_LR`), `track_deadzone` (não gira se o alvo estiver perto do centro) e `track_screen_offset` (enquadrar o alvo fora do centro, por exemplo um pouco abaixo).

Como funciona sem brigar com parent e scripts:
- A câmera guarda a orientação **base**, que é a que o parent ou os scripts do frame definiram. A rotação de rastreio é um **offset** aplicado por cima, e o hover é um offset de posição. Nada se acumula nos dados do objeto, então desligar o rastreio devolve a câmera ao estado normal na hora.
- A aplicação acontece 1 vez por frame em `KX_Scene`, depois da lógica e da física (e do `UpdateFocus`) e antes do render. O tremor (seção 3) entra por último, por cima de tudo.
- No Python, `worldOrientation` continua sendo a orientação base (a que os scripts escrevem). A orientação final renderizada, com o rastreio, fica em `cam.trackOrientation` (RO), para os scripts do jogo não passarem a acumular o offset.

### 2. Módulo Camera FX (GPU): no máximo 2 passes
Para ser rápido, os efeitos são agrupados por custo, e cada grupo só é compilado com o que está ligado (`#define USE_DOF`, `USE_SPEEDBLUR`...). O shader é recompilado só quando a combinação de efeitos ligados muda, e nunca por frame.

- **Passe A, `FILTERPASS_CAMERA_DOF`** (só existe se o DOF estiver ligado): bokeh com anéis e amostras configuráveis (qualidade Baixa/Média/Alta). Usa a profundidade linear, `focusDistance` e `focusRange`. O **olho de gato opção 1 (Bokeh olho de gato)** fica aqui: o disco de amostragem é recortado conforme a distância do pixel ao centro da tela.
- **Passe B, `FILTERPASS_CAMERA_LENS`** (um passe único para o que é barato):
  - **Speed Blur radial**: centro no `focusScreenPosition` (o carro), não no meio fixo da tela. A força vem da velocidade da câmera calculada pela engine (delta de posição), com override por Python.
  - **Directional Blur**: direção calculada pela engine a partir do delta de rotação da câmera, com limite `max`.
  - **Proteção do foco**: os dois borrões pulam os pixels na faixa de profundidade do foco, para o carro ficar nítido (mesma técnica do CarFireAura).
  - **Olho de gato opção 2, aberração cromática**, com força e opção de subir com a velocidade.
  - **Olho de gato opção 3, vinheta / olho de peixe**, com força, raio e curvatura.
- Os dois passes entram no fim da cadeia reservada, depois do `FILTERPASS_LENSFLARE`. O `reservedPassIndex` é ajustado de acordo (os filtros de Python do jogo continuam depois deles).
- O seletor "Lens Style" (Bokeh olho de gato / Aberração / Vinheta-Olho de peixe) é um enum com flags. Dá para marcar mais de um.

### 3. Tremor de câmera
- `KX_Camera` passa a somar fontes de tremor em vez de sobrescrever: `m_shakeEarthquake` (setado pelo `UpdateEarthquake`, que hoje sobrescreve) mais `m_shakeUser`.
- Modelo "trauma": `cam.shake(intensidade, duracao)` em Python soma trauma, que decai. O deslocamento sai de `trauma²` × ruído suave, por lens shift (como o terremoto) e com rolagem leve opcional.
- Painel: amplitude máxima, frequência e rolagem liga/desliga.

### 4. Dados, RNA e UI
- DNA: `struct CameraGameFX` ao final de `Camera` (flags de efeito, parâmetros, foco, tremor). Defaults em `versioning_range.c`, que é o padrão usado pelo `csmCacheMaxStaleFrames`.
- RNA: [rna_camera.c](../source/source/blender/makesrna/intern/rna_camera.c).
- UI: [properties_data_camera.py](../source/release/scripts/startup/bl_ui/properties_data_camera.py), só `BLENDER_GAME`, com os painéis "Focus", "Camera Effects" (um subpainel ou caixa por efeito, cada um com checkbox no cabeçalho) e "Camera Shake".
- Python: toggles `cam.fx.dof`, `cam.fx.speedBlur`… ou atributos planos `cam.useDof` etc. (seguir o estilo dos atributos existentes de `KX_Camera`) e `cam.speedBlurOverride`.
- Conversão: ler DNA → `KX_Camera` em [BL_BlenderDataConversion.cpp:1065](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp#L1065).

## Fases (cada uma compila e é testada antes da próxima)
1. **Foco**: DNA, RNA, painel Focus, `UpdateFocus` e API Python. Sem efeito visual, dá para validar só pelo Python (`focusPosition`).
1b. **Rastreio do foco**: OFF, LOOK_AT e DRONE (troca suave, hover e bank), com limites, zona morta e offset.
2. **DOF Bokeh nativo**, com o olho de gato opção 1.
3. **Passe Lens**: Speed Blur, Directional Blur, proteção do foco, aberração e vinheta/olho de peixe.
4. **Tremor**: soma com o terremoto e `cam.shake()`.
5. **Docs**: changelog, roadmap, relatório e referência de Python. Depois, uma nota de migração para o jogo (sem alterar o jogo): trocar BokehDoF/SpeedBlur/DirectionalBlur pelos toggles da câmera e usar `cam.focusProperty` no lugar da busca por `player_1_2_PC`.

## Arquivos principais
- `source/blender/makesdna/DNA_camera_types.h`, `makesrna/intern/rna_camera.c`, `blenloader/intern/versioning_range.c`
- `gameengine/Ketsji/KX_Camera.{h,cpp}`, `KX_Scene.cpp` (earthquake + chamada UpdateFocus)
- `gameengine/Converter/BL_BlenderDataConversion.cpp`
- `gameengine/Rasterizer/RAS_2DFilterManager.h`, `RAS_2DFilterData.h`, `RAS_2DFilter.cpp`
- `gameengine/Ketsji/KX_2DFilterManager.cpp`, `KX_RenderPipeline.cpp`
- Novos: `RAS_OpenGLFilters/RAS_CameraDof2DFilter.glsl`, `RAS_CameraLens2DFilter.glsl` (+ CMakeLists)
- `release/scripts/startup/bl_ui/properties_data_camera.py`

## Verificação
- Build pela skill `build-anastacio` (vcvars64 + `VSLANG=1033`). Como a DNA muda, fazer `ninja -t clean` na área afetada antes, seguindo o AGENTS.md. Os shaders exigem rebuild de `ge_rasterizer_shaders`, e os erros de GLSL só aparecem no console em runtime.
- Cena de teste `.range`: câmera seguindo um cubo com a propriedade `foco = True` e objetos em várias distâncias.
  - Imprimir `cam.focusPosition`/`focusDistance` e remover o objeto em jogo para ver o fallback.
  - Ligar e desligar cada efeito pelo painel e pelo Python, e conferir que o shader recompila só na troca.
  - Verificar o DOF nítido no alvo, o Speed Blur centrado no alvo e o carro protegido do blur.
  - Rastreio: câmera parada, com parent, seguindo o cubo em LOOK_AT e em DRONE. Trocar a propriedade de foco para outro objeto e ver a transição suave; testar os limites de ângulo e a zona morta; desligar em jogo e ver a câmera voltar à orientação base; conferir a mesma velocidade a 30 e a 144 FPS.
  - Terremoto + `cam.shake()` juntos, somando sem um anular o outro.
- Medir o custo com o profiler da engine (`tc_filters2d`): tudo desligado deve custar zero passes; comparar com os scripts Python atuais no Rolima Racer.
- Abrir um `.blend` antigo e conferir que os defaults vêm com todos os efeitos desligados.
