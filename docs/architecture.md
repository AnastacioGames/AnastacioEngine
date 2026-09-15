# Arquitetura da AnastacioEngine

> Visão estrutural do runtime C++. Não é um substituto de `relatorio-melhorias-anastacioengine.md`
> (o que foi modificado/otimizado versus o herdado) nem de `changelog.md` (histórico de trabalho técnico) —
> este documento é o mapa estático de módulos e fluxo, para orientar leitura seletiva de código.

## Linhagem

AnastacioEngine → Range Engine 1.6 Rev1 → UPBGE 0.2.5b → Blender 2.79.

O núcleo do runtime de jogo está em `source/source/gameengine/`, separado da parte "editor Blender"
(`source/source/blender/`, `source/source/creator/`). O nome "Ketsji" que aparece em vários lugares é o
codinome histórico do BGE (Blender Game Engine).

## Fluxo de execução

```
main() [GPG_Ghost.cpp, standalone]        BL_KetsjiEmbedStart.cpp [embedded no Blender]
        |                                              |
        v                                              v
  GPG_Canvas (RAS_ICanvas)                    KX_BlenderCanvas (RAS_ICanvas)
        |                                              |
        +-------------------> LA_Launcher <------------+
                          (LA_PlayerLauncher /
                           LA_BlenderLauncher)
                                   |
                        EngineNextFrame() a cada iteração
                                   v
                          KX_KetsjiEngine
                    StartEngine() -> NextFrame() -> Render()
                        (loop principal do jogo)
                                   |
                 +-----------------+------------------+
                 v                 v                  v
           SCA_LogicManager   Physics (Bullet)    RAS_Rasterizer
           (sensor/controller/  via SG_Node sync   (RAS_OpenGLRasterizer)
            actuator, GameLogic)      |                  |
                 |             SceneGraph (SG_Node)  OpenGL / GHOST
                 v
          KX_GameObject (Ketsji) — envolve um SG_Node,
          referenciado por CValue/PyObjectPlus (Expressions)
```

Dois pontos de entrada de `main()`:
- **Standalone**: `GamePlayer/GPG_Ghost.cpp:817` (`int main(...)`) → constrói `GPG_Canvas` + `LA_PlayerLauncher`.
- **Embutido no Blender** (botão Play do editor): `BlenderRoutines/BL_KetsjiEmbedStart.cpp`, chamado a partir do
  `main()` do próprio Blender em `source/creator/` (fora de `gameengine/`).

Ambos convergem em `LA_Launcher`, que por sua vez dirige `KX_KetsjiEngine`.

## Ordem do frame (`KX_KetsjiEngine::NextFrame()`)

Chamado a cada iteração por `LA_Launcher::EngineNextFrame()`. Sequência oficial (reconstruída por
leitura em `docs/changelog.md`, entrada "2026-09-07 — Ketsji Plano 8: levantamento e limpeza de
código morto"):

```
NextFrame()
  -> input / ImGui / joystick
  -> simulação: m_simulationPipeline->Update()
       (direto, ou via loop do acumulador de passo fixo quando use_fixed_timestep está ligada)
  -> processamento de libs/cenas agendadas (lib load/free, troca de cena)
  -> retorna m_doRender

  se m_doRender == true:
      BeginFrame()
      Render()  -> m_renderPipeline->Render()
      EndFrame()
          -> UpdateSleepTime()  (chamado primeiro, dentro de EndFrame)
          -> motion blur / log / debug UI / swap de buffers

  se m_doRender == false:
      UpdateSleepTime() chamado direto dentro de NextFrame()
```

`UpdateSleepTime()` é o algoritmo de catch-up baseado em sleep (compara `m_deltatime` acumulado
contra `m_timestep`, dorme quando está adiantado). `FrameOver()`/`FrameTiming()` são os
auxiliares de baixo nível que atualizam `m_overframetime`/`m_average_framerate`/`m_timestep` etc.
consumidos por ele. Esses ~24-30 membros `m_*time*` e as três funções (`UpdateSleepTime`,
`FrameOver`, `FrameTiming`) são candidatos a uma futura extração para uma classe própria
(`KX_FrameClock`), identificada mas **não executada** no Plano 10 por ser a mudança de maior risco
comportamental do módulo — decisão do usuário foi priorizar limpeza de comentários/nomes e esta
documentação primeiro.

O profiling de cada trecho usa `KX_TimeCategoryLogger` (`m_logger.StartLog(tc_XXX)`), com
categorias no enum `KX_TimeCategory` (`KX_KetsjiEngine.h`) rotuladas em paralelo por
`m_profileLabels[]` (`KX_KetsjiEngine.cpp`), que é o que `GetPyProfileDict()` expõe a Python. A categoria
`tc_scenegraph`/"UpdateParents" nunca recebe `StartLog()` (foi superada por
`tc_scenegraph_logic`/`_actuators`/`_physics`) e por isso sempre aparece como zero nesse
dicionário — código morto de profiling, documentado mas não removido (ver `docs/changelog.md`,
"Ketsji Plano 10: limpeza de comentários e nomes"). `tc_network`/"CameraCulling" é usada
normalmente (culling + LOD update em `KX_RenderPipeline::RenderFrame`).

## Ownership dos componentes do maestro (`KX_KetsjiEngine`)

Dois grupos, com ciclos de vida opostos:

- **Injetados, não possuídos** (`RAS_ICanvas *m_canvas`, `RAS_Rasterizer *m_rasterizer`,
  `BL_Converter *m_converter`, `KX_Imgui *m_imgui`, `KX_DebugMode *m_debugMode`,
  `KX_NetworkMessageManager *m_networkMessageManager`, `SCA_IInputDevice *m_inputDevice`): ponteiros
  crus, atribuídos pelos setters (`SetCanvas`/`SetRasterizer`/`SetConverter`/`SetInputDevice`/
  `SetNetworkMessageManager`, mais os construídos direto pelo launcher — `m_imgui`/`m_debugMode`).
  `KX_KetsjiEngine` nunca faz `delete` neles. O único ponto de construção de `KX_KetsjiEngine` no
  repositório é o launcher (`LA_Launcher::InitEngine`), que cria e injeta esses objetos antes de
  `StartEngine()` e é quem decide quando destruí-los — confirmado por auditoria no Plano 3, 5ª
  unidade (ver `docs/ketsji-engine-modernization-plan.md`).
- **Possuídos internamente**: `std::unique_ptr<KX_ShadowRenderer> m_shadowRenderer`,
  `std::unique_ptr<KX_RenderPipeline> m_renderPipeline`,
  `std::unique_ptr<KX_SimulationPipeline> m_simulationPipeline`,
  `std::unique_ptr<KX_SceneScheduler> m_sceneScheduler` (extraídos nos Planos 5-7) e
  `CustomMouseCursor *m_CustomMouseCursor` (ponteiro cru, mas com dono explícito: criado/substituído só
  via `SetCustomMouseCursor`, liberado por `FreeCustomMouseCursor` no destrutor — ver Plano 1A, item 5).
  Esses vivem e morrem com a instância de `KX_KetsjiEngine`.

`m_scenes` (`EXP_ListValue<KX_Scene>*`) é uma terceira categoria: possuído pelo motor, mas seu conteúdo
é adicionado/removido/substituído em runtime pelo `m_sceneScheduler`, não diretamente por
`KX_KetsjiEngine`.

## Módulos (`source/source/gameengine/`)

| Módulo | Responsabilidade | Entrada/arquivos-chave | Depende de |
|---|---|---|---|
| **Common** | Utilitários base sem dependências (clock, threading, logging, containers, refcount). | `CM_Clock`, `CM_Thread`, `CM_Message`, `CM_RefCount` | — (base de tudo) |
| **Expressions** | Sistema genérico de valores dinamicamente tipados; ponte C++↔Python. | `EXP_Value.h` (`CValue`), `EXP_PyObjectPlus.h`, `EXP_ListValue.h` | Common |
| **Device** | Abstração de dispositivos de input (teclado, mouse, joystick/vibração). | `DEV_InputDevice.h`, `DEV_EventConsumer`, `DEV_Joystick*` | Common |
| **SceneGraph** | Grafo de transformações hierárquico, independente de render/física. | `SG_Node.h/.cpp`, `SG_Controller.h/.cpp`, `SG_Familly.h/.cpp` | Common |
| **GameLogic** | Sistema de "logic bricks" (Sensor-Controller-Actuator), independente de renderer. | `SCA_LogicManager.h/.cpp` (avaliação por frame), `SCA_IObject.h`, `SCA_PythonController.h/.cpp` | Expressions, Device |
| **Physics** | Abstração de física com backend Bullet (e um dummy). | `Physics/Common/PHY_IPhysicsEnvironment.h`, `Physics/Bullet/CcdPhysicsEnvironment.h/.cpp` | SceneGraph, Bullet (3rd party) |
| **Rasterizer** | Abstração de render + implementação OpenGL; filtros 2D de pós-processo. | `RAS_Rasterizer.h/.cpp`, `RAS_ICanvas.h/.cpp`, `RAS_OpenGLRasterizer/`, `RAS_OpenGLFilters/` (bloom, SSAO, SSR, FXAA) | SceneGraph, OpenGL/GHOST |
| **Converter** | Converte dados Blender (Main/Object/bActuator) em objetos de runtime Ketsji. | `BL_BlenderDataConversion.h/.cpp`, `BL_Converter.h/.cpp`, `BL_SceneConverter.h/.cpp` | Blender DNA/BKE, GameLogic, Ketsji, Physics, Expressions |
| **Ketsji** | Maior módulo: runtime de cena/game object e camada de API Python; contém o **loop principal**. | `KX_KetsjiEngine.h/.cpp` (`StartEngine`/`NextFrame`/`Render`), `KX_Scene.h/.cpp`, `KX_GameObject.h/.cpp`, `KX_PythonInit.h/.cpp` | GameLogic, Rasterizer, Physics, SceneGraph, Converter, Expressions, Device |
| ├─ `KXImgui/` | Integração ImGui exposta ao Python. | `KX_Imgui.h/.cpp` (`KX_Imgui::Init(DEV_InputDevice*)`), `KX_PythonImgui.cpp` | Ketsji, Device |
| ├─ `KXNetwork/` | Sensores/atuadores de mensagens de rede. | — | Ketsji |
| **Launcher** | Camada abstrata que dirige o loop de frames do `KX_KetsjiEngine`. | `LA_Launcher.h/.cpp` (`EngineNextFrame`, `RunPythonMainLoop`), `LA_PlayerLauncher.h/.cpp`, `LA_BlenderLauncher.h/.cpp` | Ketsji, Rasterizer, Device |
| **GamePlayer** | Shell da aplicação standalone (fora do editor Blender). | `GPG_Ghost.cpp` (`main()`, linha 817), `GPG_Canvas.h/.cpp` | Launcher, Rasterizer, GHOST |
| **BlenderRoutines** | Ponte entre o "Play" embutido no editor Blender e o Ketsji. | `BL_KetsjiEmbedStart.cpp`, `KX_BlenderCanvas.h/.cpp` | Ketsji, Rasterizer, Blender core |
| **VideoTexture** | Add-on de captura de vídeo/render-to-texture exposto ao Python (`bge.texture`). | `Texture.h/.cpp`, `VideoFFmpeg.h/.cpp`, `ImageRender.h/.cpp`, `VideoDeckLink.h/.cpp` | Ketsji, Rasterizer, FFmpeg/DeckLink (3rd party) |

## Pontos de integração Python / ImGui

- **Python**: `Ketsji/KX_PythonInit.h/.cpp` — `initGamePython(Main*, PyObject*)`, `initPlayerPython(int argc, char**argv)`.
  Registro adicional de tipos em `KX_PythonInitTypes.cpp` e em `GameLogic/SCA_PythonController.cpp`.
- **ImGui**: `Ketsji/KXImgui/KX_Imgui.h/.cpp` — classe `KX_Imgui`, `Init(DEV_InputDevice*)`;
  bindings Python em `KX_PythonImgui.h/.cpp`; input em `KX_Imgui_Impl_Inputs.cpp`.
  O histórico do menu ImGui está nas entradas de 2026-08-25 de `docs/changelog.md`.

## Herdado vs. modificado pela AnastacioEngine

Este documento não tenta refazer essa distinção — ela já está mantida em:
- `relatorio-melhorias-anastacioengine.md` (raiz do repo) — o que existe/funciona vs. gaps confirmados,
  com caminhos de arquivo concretos (ex.: `RAS_InstancingBuffer`, `KX_LodManager`).
- `docs/changelog.md` — log corrente de mudanças técnicas.

Ao investigar se algo é herdado do UPBGE/Range Engine ou é modificação própria, consultar esses dois arquivos
primeiro; usar `git log`/`git blame` pontualmente só onde eles forem omissos.

## Guia de manutenção

Para "o que mais preciso tocar" ao fazer um tipo comum de mudança (propriedade com checkbox na UI, função
Python nova, shader compat/core, struct DNA) — cadeias de arquivos extraídas de episódios reais do
changelog: ver `docs/maintenance-guide.md`.

## Manutenção deste mapa

Atualize este arquivo quando módulos forem adicionados, removidos ou tiverem sua responsabilidade alterada.
Planejamento, instruções de build e histórico pertencem, respectivamente, ao roadmap, às notas de build e
ao changelog; não devem ser duplicados aqui.
