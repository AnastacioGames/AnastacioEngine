# Diagramas da arquitetura

Visão desenhada da AnastacioEngine, para quem chega ao projeto. O texto completo está em
[architecture.md](architecture.md); este arquivo só desenha. Conferido com o código em 2026-09-26.

Os diagramas usam Mermaid e aparecem desenhados no GitHub. Caminhos de código são relativos a
`source/source/gameengine/`, salvo indicação.

---

## 1. Mapa do repositório

```mermaid
flowchart TB
    root["AnastacioEngine/"]
    root --> src["source/<br/>raiz do CMake e presets"]
    root --> tools["tools/<br/>web, android, linux, índices de código"]
    root --> docs["docs/<br/>documentação"]
    root --> builds["build*/<br/>saída dos builds (fora do git)"]

    src --> ss["source/source/"]
    src --> intern["source/intern/<br/>cycles, ghost, audaspace..."]
    src --> extern["source/extern/<br/>Bullet, ImGui, Recast, SDL2..."]
    src --> rel["source/release/<br/>scripts Python e datafiles"]

    ss --> ge["gameengine/<br/>runtime do jogo (Ketsji)"]
    ss --> bl["blender/<br/>editor herdado do Blender 2.79"]
    ss --> cr["creator/<br/>main() do RangeEngine"]
    ss --> bp["blenderplayer/<br/>alvo do RangeRuntime e stubs"]

    rel --> ui["scripts/startup/<br/>painéis e operadores"]
    rel --> rw["scripts/modules/range_web/<br/>export Web/Android e traduções"]
    rel --> df["datafiles/<br/>startup.blend, splash, ícones"]
```

**Legenda.** O jogo roda a partir de `gameengine/`; o editor é o Blender 2.79 modificado (`blender/`). Os dois
executáveis são `RangeEngine` (editor, `main()` em `creator/`) e `RangeRuntime` (player, montado em
`blenderplayer/`). A interface do editor é quase toda Python, em `source/release/scripts/`.

---

## 2. Módulos do runtime

```mermaid
flowchart TB
    subgraph entrada["Pontos de entrada"]
        GP["GamePlayer<br/>RangeRuntime"]
        BR["BlenderRoutines<br/>Play no editor"]
    end
    LA["Launcher<br/>LA_Launcher"]
    KX["Ketsji<br/>KX_KetsjiEngine, KX_Scene, KX_GameObject,<br/>API Python, ImGui"]
    CV["Converter<br/>.blend para objetos do jogo"]
    GL["GameLogic<br/>sensores, controladores, atuadores"]
    PH["Physics<br/>Bullet"]
    RA["Rasterizer<br/>OpenGL / WebGL2, filtros 2D"]
    VT["VideoTexture<br/>bge.texture"]
    SG["SceneGraph<br/>SG_Node"]
    DV["Device<br/>teclado, mouse, joystick"]
    EX["Expressions<br/>valores e ponte C++/Python"]
    CM["Common<br/>clock, log, refcount"]

    GP --> LA
    BR --> LA
    LA --> KX
    KX --> CV
    KX --> GL
    KX --> PH
    KX --> RA
    KX --> VT
    CV --> GL
    CV --> PH
    GL --> DV
    GL --> EX
    PH --> SG
    RA --> SG
    KX --> SG
    EX --> CM
    SG --> CM
    DV --> CM
```

**Legenda.** Setas mostram quem usa quem na arquitetura pensada: de cima (aplicação) para baixo (base).
**Ressalva:** no código real os `#include` cruzam camadas em quase todas as direções (até `Common` inclui
`Expressions` e `SceneGraph`, e `Rasterizer` inclui `Ketsji`), herança do BGE. Use o diagrama para entender
papéis, não como regra de dependência garantida. Tabela de módulos em [architecture.md](architecture.md#módulos-sourcesourcegameengine).

---

## 3. Pontos de entrada até o loop do jogo

```mermaid
flowchart LR
    A["RangeRuntime<br/>GamePlayer/GPG_Ghost.cpp main()"] --> PL["LA_PlayerLauncher"]
    B["Play no editor<br/>BlenderRoutines/BL_KetsjiEmbedStart.cpp"] --> BLL["LA_BlenderLauncher"]
    C["Navegador (WebAssembly)<br/>mesmo GPG_Ghost.cpp"] --> PL
    PL --> L["LA_Launcher"]
    BLL --> L
    L -->|"desktop: laço while"| F["EngineNextFrame()"]
    L -->|"Web: emscripten_set_main_loop_arg<br/>o navegador chama 1 frame por vez"| F
    L -->|"jogo com main loop em Python"| P["RunPythonMainLoop"] --> F
    F --> K["KX_KetsjiEngine::NextFrame()"]
    K -->|"se precisa desenhar"| R["KX_KetsjiEngine::Render()"]
```

**Legenda.** Os três caminhos acabam no mesmo `LA_Launcher::EngineNextFrame()`
(`Launcher/LA_Launcher.cpp`). A diferença da Web é só quem chama cada frame: o navegador, não um `while`.
O Android é um APK com WebView que carrega o pacote Web, então entra pelo caminho do navegador.

---

## 4. Um frame do jogo

```mermaid
flowchart LR
    subgraph NF["1 · KX_KetsjiEngine::NextFrame()"]
        direction TB
        N1["ImGui e eventos de joystick"]
        N2["Simulação: KX_SimulationPipeline::Update()<br/>1 vez, ou N passos com passo fixo"]
        N3["Limpa input e mensagens"]
        N4["Carrega/libera libs e troca cenas<br/>(KX_SceneScheduler)"]
        N1 --> N2 --> N3 --> N4
    end
    subgraph SIM["2 · Simulação, para cada cena"]
        direction TB
        S1["Atividade dos objetos"]
        S2["Animações e deformação"]
        S3["Cutscene"]
        S4["Lógica: sensores e controladores"]
        S5["Atuadores"]
        S6["Física Bullet"]
        S7["Atualiza hierarquia (UpdateParents)"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
    end
    subgraph RD["3 · KX_RenderPipeline::Render()"]
        direction TB
        R1["BeginFrame"]
        R2["Sombras (KX_ShadowRenderer)"]
        R3["Render-to-texture"]
        R4["Cada câmera: culling, LOD e desenho"]
        R5["Filtros 2D da cena"]
        R6["EndFrame: ImGui, debug, troca de buffers"]
        R1 --> R2 --> R3 --> R4 --> R5 --> R6
    end
    NF -.->|"passo 2 chama"| SIM
    SIM -->|"depois do NextFrame,<br/>se m_doRender"| RD
```

**Legenda.** `NextFrame()` sempre roda a simulação; o render só acontece quando `m_doRender` é verdadeiro
(senão o motor só calcula quanto dormir). A hierarquia de objetos é atualizada várias vezes no frame (depois
da lógica, dos atuadores e da física); o diagrama resume. Código: `Ketsji/KX_KetsjiEngine.cpp`,
`Ketsji/KX_SimulationPipeline.cpp`, `Ketsji/KX_RenderPipeline.cpp`.

---

## 5. Do editor para o jogo

```mermaid
flowchart LR
    U["Painel Python<br/>release/scripts/startup/bl_ui"] --> R["Propriedade RNA<br/>blender/makesrna/intern/rna_*.c"]
    R --> D["Struct DNA<br/>blender/makesdna/DNA_*_types.h"]
    D --> F[".blend salvo"]
    V["Versioning de arquivos antigos<br/>blenloader/intern/versioning_range.c"] --> F
    F --> C["Converter<br/>BL_BlenderDataConversion.cpp<br/>BL_Convert*.cpp"]
    C --> O["Runtime<br/>KX_GameObject, SCA_*, física, materiais GLSL"]
```

**Legenda.** O jogo nunca lê o editor, só o `.blend`. Uma opção nova de jogo costuma tocar todas essas
caixas; a lista exata por tipo de mudança está em [maintenance-guide.md](maintenance-guide.md). Coisas só do
editor (Asset Browser, pastas do Outliner, temas) param antes do conversor.

---

## 6. Plataformas e builds

```mermaid
flowchart TB
    code["Mesmo código-fonte"]
    code -->|"preset v142-ninja<br/>build/"| W["Windows x64<br/>RangeEngine + RangeRuntime<br/>Cycles: Embree, CUDA, OpenCL"]
    code -->|"presets linux-editor / linux-runtime"| L["Linux x86_64<br/>RangeEngine + RangeRuntime"]
    code -->|"presets web-runtime / web-runtime-release<br/>build-web-release/"| WB["Runtime Web<br/>WebAssembly + WebGL2"]
    WB -->|"range_web: Exportar Web"| PK["Pacote do jogo para o navegador"]
    PK -->|"range_web/android.py"| AN["Android<br/>APK/AAB com WebView"]
    code -.->|"build-android/ (NDK)<br/>congelado"| X["Android nativo<br/>não usado"]
```

**Legenda.** Windows e Linux compilam editor e player nativos. A Web compila só o runtime; o jogo é exportado
pelo editor e empacotado com ele. O Android oficial reaproveita o pacote Web dentro de um app com WebView.
Nomes e estado de cada pasta de build: [build-dirs.md](build-dirs.md).
