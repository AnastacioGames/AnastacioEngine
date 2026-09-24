# Relatório de melhorias — AnastacioEngine

Este documento registra o estado técnico vigente da engine. O trabalho ainda aberto fica em
[`docs/roadmap.md`](docs/roadmap.md), e o histórico detalhado de implementação e medições fica em
[`docs/changelog.md`](docs/changelog.md).

## Contexto

RangeArmor estÃ¡ validada para runtimes Windows/Linux x86_64, com cÃ³pia dos runtimes disponÃ­veis,
exportaÃ§Ã£o `.zip`/`.tar.xz` e interface sem alvos 32-bit. Campos 32-bit antigos permanecem aceitos
somente para leitura de projetos legados.

A AnastacioEngine é um fork da Range Engine 1.6 Rev1, derivada da UPBGE 0.2.5b e do Blender 2.79. As
frentes principais são performance, iluminação/renderização e ferramentas de runtime.

A validação nativa em Linux x86_64 de 2026-09-15 também é uma evidência importante para os exports Web e
Android: o runtime já roda fora do Windows/MSVC com toolchain Unix, Python 3.11 isolado, OpenAL, SDL/X11,
RPATH e empacotamento próprio. Isso não substitui o trabalho específico de Emscripten/NDK, mas reduz o risco
de portabilidade e fornece um modelo concreto para runtimes empacotados por plataforma.

Um item só entra no roadmap de engine quando exige mudança em `source/` e recompilação. Configuração de
cena, preparação de assets e scripts independentes são registrados no changelog ou na documentação da
ferramenta correspondente.

## Capacidades herdadas que não devem ser reimplementadas

- GPU instancing com `RAS_InstancingBuffer` e `RAS_DisplayArrayBucket::RunInstancingNode`.
- Batching estático com `RAS_BatchDisplayArray` e `RAS_BatchGroup`.
- LOD por distância com `KX_LodManager` e `KX_LodLevel`.
- Frustum culling com `SG_CullingNode`, `KX_CullingHandler` e `SG_Frustum`.
- Occlusion culling por DBVT do Bullet. A cena usa `use_occlusion_culling`, e objetos grandes podem ser
  marcados como `Occluder`; isso é configuração de conteúdo, não um gap de C++.
- Principled BSDF/PBR herdado do fork. Não criar outro modelo PBR antes de verificar a exposição existente.
- MSAA de ponta a ponta, já confirmado no código e no runtime.

## Melhorias implementadas

### Performance

- O buffer de instancing conserva capacidade e só realoca quando necessário; o rebind redundante dos
  atributos por frame também foi eliminado.
- Resolução dinâmica opt-in preserva a resolução da janela e escala apenas os offscreens internos do
  jogo para perseguir um FPS-alvo. A decisão usa `GL_TIME_ELAPSED`, média suave, histerese e cooldown;
  o usuário configura alvo, escala mínima/máxima e passo em `Game Render Properties > Dynamic Resolution`.
  Ela vale para Play e standalone, nunca para a 3D View de edição.
- GPU Skinning move a deformação por bones para o vertex shader e está liberado para uso.
- Z-prepass para materiais alpha-cutout reduziu o tempo de GPU do benchmark de 28,29 ms para 21,45 ms.
- Streaming por distância está disponível em `projects-teste/scripts/streaming_manager.py`.
- LOD de impostor possui billboard cilíndrico e bake automático de atlas multiângulo.
- Partículas GPU por objeto usam transform feedback, shader cache compartilhado, sprites/texturas, curvas,
  presets, debug ImGui e colisão Ground Plane/Screen-Space.
- Fragment shader customizado por emissor (Fase P): arquivo `.glsl` externo (`object.particles.fragmentShaderPath`
  em Python, campo "Fragment Shader File" na UI), com hot-reload automático (poll de mtime a cada ~0,5s) —
  edita-se o arquivo com o jogo rodando e o efeito atualiza sozinho. Exemplos prontos em
  [`projects-teste/shaders/particles/`](projects-teste/shaders/particles/).
- **Animações de objetos de pool**: objetos reciclados que já chamaram `playAction()` uma vez ficavam permanentemente
  registrados em `KX_Scene::m_animatedlist`, gerando custo de dispatch de atualização de animação a cada frame mesmo
  quando suspensos no pool. Corrigido expondo `KX_GameObject::SuspendAnimations()`/`ResumeAnimations()` (wrappers
  Python para `BL_ActionManager::Suspend/Resume`), wired no sistema de pool para suspender/resumir objetos ao
  reciclar/reativar. Elimina o custo residual de "Animations" relatado em efeitos de piscina (fumaça, faísca,
  terra/asfalto, slipstream) após terminar — GPU particles (sistema separado) não são afetadas.

### Iluminação e renderização

- O caminho usado pelo `RangeRuntime` foi migrado para OpenGL core profile, mantendo o editor em
  compatibility profile. Os no-ops aceitos no core são motion blur legado, clipping de espelho/água e
  texto de debug baseado em `BLF_draw`.
- CSM para luzes Sun usa três cascatas ajustadas ao frustum e considera os bounds dos casters no recorte Z.
  O bug de sombra estática ausente no ângulo inicial foi corrigido e confirmado visualmente.
- Novas Lamps já nascem com o preset de sombras para Sun: mapa Simple com filtro PCF, 1024 px na cascata
  Near, com CSM e debug desativados, splits 0,40/0,35 e cascatas Medium/Low em 512/128 px. Os valores continuam
  editáveis por lamp e dados existentes não são alterados.
- FXAA foi atualizado para uma implementação no estilo 3.11 com nove amostras.
- Bloom, SSAO, SSR, Tonemap e Light Scattering podem ser controlados pelo actuator Filter 2D com faixas de
  passes reservadas.
- Depth Transparency possui captura de profundidade dedicada e comportamento seguro fora do jogo.
- Weather nativo no `World` oferece chuva, nuvens e lens flare; a chuva inclui modos Classic e Volumetric.
- Automatic Sun orbits a ground reference 5 m ahead of the active camera at a 10 m radius and always targets it.
  The reference estimates ground elevation from the camera's initial height. Its `Sun Hour` is backed by the
  World World Property `sun_hour` (Float, 0-24; 12 is directly overhead), so Logic Bricks can control it.
- `Scene > Automatic Sun` cria um Sun e o atribui ao `World Sun`; somente esse Sun marcado orbita a referÃªncia
  de chÃ£o 5 m Ã  frente da cÃ¢mera ativa, mirando-a durante o runtime. Suns escolhidos manualmente em `World Sun`
  preservam seu comportamento e transformaÃ§Ã£o normais.
- IBL (irradiância/reflexo de ambiente vindo do céu/HDRI) somado às luzes de cena já funciona no shader do
  Principled (`059766dc`). Sombra projetada (shadow map simples de Sun/Spot) no loop de luzes do Principled
  foi implementada em 2026-09-21 (`GPU_material_bind_shadow_lamps`, ver `docs/changelog.md`); **falta apenas
  a validação visual no jogo real** — CSM/VSM e Point/Local ainda não projetam sombra nesse caminho (mesma
  limitação de engine já documentada). Ver `docs/roadmap.md` ("Iluminação e gráficos").
- No Web (perfil CORE), as luzes de cena do Principled/Diffuse/Glossy chegam por `unflightsource[]`
  (`GPUSceneLight`, calculado em `RAS_OpenGLLight` junto do `glLight*`), não por `gl_LightSource`. Mudança no
  formato de luz deve atualizar os dois caminhos. No Emscripten, `GPU_max_textures()` é limitado a 28 pela
  emulação GL legada.

### Runtime e ferramentas

- Arrastar um arquivo `.obj` para a janela da Vista 3D importa o modelo diretamente na cena, sem abrir
  o seletor de arquivos. O addon OBJ incluído é ativado automaticamente na primeira importação, se necessário.
- Compatibilidade de scripts BGE/UPBGE: `import bge` e seus submódulos (`bge.logic`, `bge.events`,
  `bge.types`, `bge.constraints`, `bge.render`, `bge.application`, `bge.imgui` e `bge.texture`) são aliases
  dos mesmos objetos de `Range`. Jogos legados podem rodar sem renomear esses imports; scripts novos devem
  continuar usando `Range`.
- Compatibilidade Python legada: a inicialização do jogo restaura em `collections` as ABCs que o Python
  moderno moveu para `collections.abc` (inclusive `MutableMapping`). Dependências antigas como TinyTag
  podem manter `from collections import MutableMapping`, sem modificação dentro de cada projeto. O console
  expõe `aud.Factory` como alias de `aud.Sound`, para scripts de áudio BGE antigos. O console informa quando
  algum alias de compatibilidade foi aplicado.
- `External Files` registra bibliotecas sem misturá-las a Links/Appends
  normais, inclusive quando o conteúdo é um Group. O Outliner lista seus
  datablocks `Text`; uma dependência ausente é marcada como quebrada e pode
  ser importada individualmente para o arquivo raiz, sem sobrescrever um Text
  local nem trazer os demais dados da biblioteca.
- Pathfinding/navmesh (`KX_NavMeshObject`, `KX_SteeringActuator`) usa a API moderna do Detour
  (`dtNavMesh`/`dtNavMeshQuery`), substituindo a antiga `dtStatNavMesh`; walkable
  Height/Radius/Climb do bake respeitam a configuração da cena. Navmesh dinâmica (rebake em
  runtime) não existe e está no roadmap.
- Menu in-game em ImGui com suporte por mouse, teclado e bindings de gamepad.
- Debug Mode expõe bounding boxes, frusta de câmera/sombra e render queries.
- Console ImGui espelha o log da engine no Play e no standalone.
- World Properties podem ser compartilhadas pelo `World` no runtime. A criação automática das propriedades
  de World Status continua pendente e está no roadmap.
- Runtime Properties tipadas ampliam Property Sensors/Actuators; detalhes e pendências estão em
  [`docs/logic-bricks-modernization.md`](docs/logic-bricks-modernization.md).
- Atlas externo de ícones configurável em `User Preferences > Files > Icons`, com fallback embutido.
- `Create Project`, disponível no splash e em `File`, abre o navegador de pastas e cria uma estrutura pronta
  para o fluxo RangeArmor: `data/` com o `.range`, a cópia protegida `.rasec`, scripts e assets; pastas
  independentes de engine, launcher, ícones e builds em `release/`. Pastas existentes nunca são sobrescritas.
- Objetos podem ser marcados nativamente como chassi de veículo (`game.is_vehicle`, DNA/RNA) com uma lista
  editável de rodas (`ob.vehicle_wheels`, com raio/suspensão/steering por roda), no painel "Vehicle" da aba
  Physics. Ao converter a cena, o próprio motor cria o `PHY_IVehicle`/`KX_VehicleWrapper` e as rodas
  automaticamente a partir desses dados — não é mais só um marcador de design. `KX_GameObject::getVehicle()`
  expõe o veículo já pronto para Python. O painel Vehicle também tem um botão para criar/anexar o
  `vehicle_player_component.py` de controle jogável direto no objeto.
- "Export Game (1 Click)" (`Scene > Export (RangeArmor)`) empacota o jogo direto do Blender sem
  precisar abrir o RangeArmor Panel manualmente antes: scaffold do projeto (`config.json`,
  `Launcher.exe`, ícones, runtime), geração do `.rasec` protegido e chamada do `build_release.py`
  são todos automáticos, com barra de progresso/cursor de espera durante o processo. O template de
  `Launcher.exe` usado no scaffold também se mantém sempre atualizado sozinho: se estiver mais
  antigo que seu source Rust (`source/launcher/src/main.rs`), é recompilado automaticamente com
  `cargo build --release` antes de ser copiado, sem diálogo nem passo manual — evita que um
  binário desatualizado volte a causar o jogo exportado "abrindo e fechando" na hora. Ver
  `docs/export-presets-plan.md` e `docs/changelog.md` (2026-09-12).

## Decisões técnicas vigentes

- `KX_Scene::GetOptimizationReferencePosition()` exposes one optimization reference, refreshed before Activity
  Culling and after physics by `UpdateOptimizationReference()`. It currently follows the active Scene camera and
  will be replaceable by the Player later. The Camera Properties tab identifies this active reference. Activity
  Culling and Foliage/Grass material wind consume it; outside the chosen `Wind Distance`, the vertex shader skips
  procedural wind.

- O port Web usa WebGL2/GLES3 e chama diretamente as entradas equivalentes para shaders, VAOs,
  framebuffers e renderbuffers. Os ponteiros de extensão OpenGL desktop mantidos pelo GLEW não são
  considerados disponíveis no Emscripten; adaptações Web devem usar a API GLES3 correspondente. O
  runtime já carrega a cena e executa frames. No Web, materiais gerados ativam
  apenas draw buffers com saídas presentes no shader ligado, restaurando o
  roteamento anterior ao terminar. FXAA, chuva, nuvens, lens flare e tonemap
  são reconhecidos pelo código-fonte no link e usam temporariamente apenas
  o primeiro anexo. Filtros personalizados mantêm o roteamento existente.
  O quad de tela também salva/restaura os divisores dos atributos e usa zero
  durante o draw Web: a emulação deixava o UV com divisor 1, produzindo imagem
  preta apesar de draws válidos. Após correção: milhares de draws sem erro GL,
  cor confirmada por leitura numérica dos passes e cubo/Python/input validados
  no navegador real. Permanecem validações visuais dos filtros ampliados, smoke
  test de persistência IDBFS e documentação de deploy.
  Ver roadmap e changelog de 2026-09-14.
- A rota recomendada para Android v1 (revisão de 2026-09-20) é um APK com WebView que embute o pacote Web,
  condicionada à prova com o jogo real em aparelho físico; ainda não há execução Android comprovada.
  Primeiro validar APK mínimo, toque simultâneo, memória/desempenho, save e pausa/retomada; depois CLI e editor.
  Sensores podem usar adaptador Android pequeno quando necessário. NDK fica congelado até limitação medida
  que justifique reabertura (bloqueios conhecidos: `malloc_stats` na Bionic, `GL/glu.h`, sem GHOST Android).
  Plano em [`docs/android-export-plan.md`](docs/android-export-plan.md).
- Export Android: a lógica fica em `range_web/android.py`; o painel "Android (Range)" e
  `tools/web/package-android.py` só a chamam. Ele consome o pacote do export Web (conferido por `SHA256SUMS.txt`),
  copia `tools/android/webview-template` para uma pasta temporária e roda o Gradle. JDK e Android SDK não vêm com a
  engine: procura em `JAVA_HOME`/`ANDROID_HOME`, depois no Android Studio instalado, depois nas pastas do painel, e
  sem eles mostra erro sem instalar nada. `applicationId` é a identidade do app (mudar perde o save). Release
  assinado: a chave (PKCS12, criada pelo keytool do JDK) fica fora de repositórios git e nunca é sobrescrita; o
  JSON guarda só caminho e alias; a senha vem de `RANGE_ANDROID_KEYSTORE_PASSWORD` ou de um campo de sessão do
  painel e chega ao Gradle pelo ambiente. Perder a chave obriga a publicar como outro app; um APK debug instalado
  não é atualizado por um release (chaves diferentes).
- Controles na tela (A1): desenho e captura de toque na página (HTML/Pointer Events); a engine recebe o estado por
  `Module.rangePad` e o entrega como gamepad 0 (somado ao controle físico) ou como teclas. Estende o input existente
  (gamepad, sensores, Range Input System); não criar sistema de ações paralelo. Texto usa o teclado do sistema.
  O overlay só aparece em tela de toque (`pointer: coarse`) ou com `?touch=1`; layout padrão stick + A/B.
  O layout é configuração do export Web (Properties > Scene > Web (Range) > Controle na tela, gravado no `.range`);
  o APK embute esse pacote e herda o layout, sem campo próprio no `android-export.json`.
  Plano em [`docs/android-touch-controls-plan.md`](docs/android-touch-controls-plan.md).
- O contexto compatibility já expõe OpenGL 4.6 no hardware testado; core profile é uma decisão de
  arquitetura e validação estrita, não um desbloqueio automático de performance.
- Filtros 2D do jogo e efeitos multipass nativos são pipelines diferentes e devem ser validados
  separadamente.
- Dados por objeto não devem ser armazenados ingenuamente em meshes compartilhadas durante a conversão
  Blender → Ketsji.
- `object.particles.enabled` pode ser sincronizado pela Game Property `GPU_Particles_Enabled`; scripts que
  precisam persistir o controle devem alterar essa property.
- Mudanças em DNA exigem clean rebuild. O procedimento completo está em
  [`docs/build-notes.md`](docs/build-notes.md).
- A checagem de range em tempo de compilação da RNA (`USE_RNA_RANGE_CHECK`, `rna_internal.h`) está ativa
  também no Emscripten desde o M2. Cinco campos DNA (`ImageUser.fie_ima`, `Material.seed1`/`seed2`,
  `ToolSettings.skgen_subdivision_number`, `ThemeSpace.handle_vertex_size`) passaram de `char` para `unsigned char`;
  o `makesdna` descarta `unsigned`, então SDNA, tamanhos e offsets não mudam (comparados antes/depois). Não alargar
  o tipo nem reduzir o hardmax para satisfazer o compilador. O MSVC nativo não define `__STDC_VERSION__` C11 e
  portanto nunca executa a checagem. Evidência em [`docs/changelog.md`](docs/changelog.md) (2026-09-20).

## Fontes relacionadas

- [Roadmap atual](docs/roadmap.md)
- [Histórico técnico](docs/changelog.md)
- [Arquitetura](docs/architecture.md)
- [Guia de manutenção](docs/maintenance-guide.md)

### Interface do Outliner

- `Outliner > View > Show Alternating Rows` liga/desliga as faixas alternadas. Desligado por padrão, usa fundo
  sólido na cor do tema. Escolha por Outliner salva no projeto; destaques de seleção preservados.

### Interface da 3D View

- Uma única barra flutuante, 20 px acima do canto inferior esquerdo da 3D View, traz `Play`, `Standalone` e
  Debug/Console, os modos de sombreamento e sua seta de opções, os controles de viewport (o ícone de câmera
  para atualização contínua, Only Render e painel de overlay), o bloqueio de câmera/camadas e o seletor de
  camadas, e os controles de transformação (manipulador, eixos, orientação e pivô). Ao entrar em Edit Mode,
  acrescenta Auto Merge, Occlude Geometry e visualização da malha; ao sair, esses controles desaparecem. Os
  controles correspondentes foram removidos do cabeçalho.
