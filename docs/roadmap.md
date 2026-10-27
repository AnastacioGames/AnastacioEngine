# Roadmap

Somente itens abertos, pendentes de validação ou explicitamente adiados ficam neste arquivo. Recursos
concluídos estão resumidos em [`../relatorio-melhorias-anastacioengine.md`](../relatorio-melhorias-anastacioengine.md)
e detalhados no [`changelog.md`](changelog.md) (histórico antigo em [`changelog-arquivo.md`](changelog-arquivo.md)).
Ao concluir um item, apague-o daqui e registre no changelog.

## Scene Doctor: colisao simplificada (fase 1)

- Regra Python implementada e validada em background: formas primitivas com encaixe >=85%, fix/revert
  e exclusoes conservadoras. Detalhes no relatorio de melhorias.
- Pendente: conferir contatos/folgas e medir custo de fisica em um jogo com objetos elegiveis.
  As 30 cenas do RolimaRacer auditadas nao tiveram sugestoes; o arquivo permaneceu intacto.
- Proxy de colisao e mudancas no `.cooked` continuam fora desta fase.

## Sumário

- [Segunda revisão da frente 8](#segunda-revisão-da-frente-8)
- [Revisão de KX_Scene](#revisão-de-kx_scene)
- [Revisão de KX_GameObject](#revisão-de-kx_gameobject)
- [Revisão de SceneGraph e loop](#revisão-de-scenegraph-e-loop)

- [Atlas de materiais](#atlas-de-materiais)
- [Prioridade atual](#prioridade-atual)
  - [Carregamento mais rápido ("Cozinhar")](#carregamento-mais-rápido-cozinhar)
  - [Multiplayer nativo](#multiplayer-nativo)
  - [Web (WebGL/WebAssembly)](#web-webglwebassembly)
  - [VR no celular (Web, estilo Cardboard)](#vr-no-celular-web-estilo-cardboard)
  - [Idioma (English, Português, Español, Русский)](#idioma-english-português-español-русский)
  - [Linux x86_64](#linux-x86_64)
  - [Cutscene nativo](#cutscene-nativo)
  - [World Status](#world-status)
  - [World Sound (gerenciador de áudio nativo)](#world-sound-gerenciador-de-áudio-nativo)
  - [Animation Events](#animation-events)
  - [Vehicle System / Vehicle Lab](#vehicle-system--vehicle-lab)
  - [Destruição e explosões](#destruição-e-explosões)
  - [Deformação por impacto](#deformação-por-impacto)
  - [Câmera: foco, rastreio e Camera FX](#câmera-foco-rastreio-e-camera-fx)
  - [Logic Bricks → Python Component](#logic-bricks--python-component)
  - [Logic Tree (lógica por nós)](#logic-tree-lógica-por-nós)
  - [Android / iOS](#android--ios)
  - [Outros](#outros)
- [Performance](#performance)
- [Iluminação e gráficos](#iluminação-e-gráficos)
- [Validações manuais pendentes](#validações-manuais-pendentes)
- [Fora do escopo atual](#fora-do-escopo-atual)

## Segunda revisão da frente 8

- Definir comportamento efetivo de `overwrite_lib` no export nativo (EXP-03).

## Revisão de KX_Scene

- [Revisão integral e reproduções](revisao-kx-scene.md): corrigir crashes por mutação de lista de callbacks
  e falha no acesso à sequência `explode(ignore=...)`, restauração indevida da gravidade sem terremoto
  e índice de templates desatualizado após rename. Os quatro casos foram reproduzidos no standalone.
- Conferir também posse de referências Python/EXP_Value, transferência de registros no merge e validade
  de objetos após callbacks de animação; resultados e limites estão no relatório. Sem correções nesta rodada.

## Revisão de KX_GameObject

- Definir contratos de herança das listas de callbacks de colisão e parâmetros armazenados de veículo.
  Validar separadamente remoção do chão das partículas e liberação de bibliotecas com LOD;
  [análise e correções do núcleo](revisao-kx-gameobject.md).
- Helper comum de parsing corrigido e 25 usos conferidos; [revisão](revisao-parser-python.md).
  Editor/player compilados e validados; regressões passaram.
  Reproduzir o caminho de buffer não liberado em erro de `LibLoad`, conferir signedness de
  `load_scripts` e ajustar o nome informado em erros de argumentos de `lookAt`.
- Validar o wrapper de partículas retido após remoção/reconstrução do buffer e sincronização imediata
  após atribuição de matrizes completas; [análise e correções dos bindings](revisao-kx-gameobject-python.md).

## Revisão de SceneGraph e loop

- [Primeira rodada da frente 2](revisao-scenegraph-loop.md): corrigir e validar por integração
  propagação do vertex parent (SG-01), orientação sob escala singular (SG-02) e movimento global
  com pai escalado (SG-03). As reproduções atuais compilam os fontes reais em harness serial.
- Conferir estado inicial de `m_modified` na cópia de nó (SG-05), eliminar sincronização no
  movimento zero (SG-06) e corrigir guarda de fila secundária no método sem uso atual (SG-04).
- Segunda rodada no mesmo relatório: definir pausa zero antes da conversão de passos (CLK-01),
  unificar relógios/delta e desconto de suspensão (CLK-02), validar limite de catch-up (CLK-03),
  pausar tempo local da cutscene (CLK-04) e conferir contrato de relógio externo (CLK-05).
  Diagnóstico aritmético compilado/executado; integração na engine ainda pendente.
- ANI-01 corrigido: ações/poses/eventos por passo elegível e deformação ao fim do catch-up.
  Quatro casos no player `--server` passaram com armature e filho de osso. Pendentes: skinning
  e ImageRender no jogo com render, interação com corpos dinâmicos, auditoria em cena parada
  com render e medição do custo de CPU do catch-up. Nenhuma janela aberta nesta revisão.
- Validar INP-01/02/03 com controle físico e integração do joystick no jogo. Regressões de
  zero/um/quatro passos e modo variável passaram, incluindo Evaluate dos sensores e duas cenas
  simuladas com hardware/pipeline substituídos; editor/player compilados e smoke em segundo plano
  passaram após a liberação dos testes do Claude.
- Próxima peça: propagação do vertex parent (SG-01), seguida das demais correções SG/CLK por partes.
  Definir fronteira de aplicação das taxas alteradas por callback antes das correções de relógio.
  INP-01 corrigido com regressão dos 15 botões e rebuild editor/player; teste físico,
  concorrência e FPS pendentes.

## Atlas de materiais

- [Ferramenta nativa e plano](material-atlas-plan.md): primeira versão para um mesh com materiais PBR opacos. Pendente: usuário validar no jogo real, Escape físico/fechamento da janela, Linux e integração GI com denoise/light volume. GPU OpenCL, Undo/Redo automático na conclusão modal, restauração persistente, cancelamento via API/rollback, Web no navegador e bakes de GI nas duas ordens passaram em cena controlada. Próximas peças, após revisão: materiais legados, vários objetos, transparência e grafos mais amplos; combinação direta sem bake permanece futura.

## Prioridade atual

- **Windows: conferir com janela** o que entrou via Linux (FFmpeg 5+/OpenColorIO 2.x/ImGui): export de vídeo,
  video texture, views do Color Management (Filmic etc.), menu ImGui no jogo (fonte e `imgui.ini` ao lado do
  executável) e bake de lightmap. Build e `ctest` 15/15 no Windows já passaram (2026-10-23 e 2026-10-24).
- Migração Windows: editor `AnastacioEngine.exe` e player `AnastacioRuntime.exe` compilados.
  Cooking, standalone pelo editor e export nativo passaram em cena controlada; usuário
  confirmou que o jogo funciona após a migração. Pendente: console,
  Steam/LAN, associações HKCU/HKLM e Windows sem Visual Studio; [plano](executable-rename-plan.md).
  Linux e artefatos Web/Android mantêm nomes anteriores.

### Carregamento mais rápido ("Cozinhar")

- RangeArmor: preparo de `.cooked` na exportação, opção de exportar sem cache, staging e launcher
  Windows atualizado passaram em cena controlada e pacote extraído. Pendente: jogo real,
  Linux/outra GPU e migração dos runtimes dos projetos antigos; [plano](rangearmor-update-plan.md).
  Cópia da instalação real, Cook e execução pelo player copiado passaram em caminho com
  espaço/acento. Destino não ASCII em `ANASTACIO_COOK` corrigido (lido em UTF-16 no Windows, 2026-10-21).
  Painel Rust recompilado com tratamento de exit code; 26 testes e abertura/fechamento
  passaram. Exportação pela GUI e diagnóstico de falha passaram em cena controlada;
  export comprimido pela GUI também passou, com execução do ZIP extraído e uso do cache.
  Usuário confirmou execução do jogo; falta validar LibLoad, benefício do cache no jogo
  real e outras plataformas/GPU. Pacotes locais sem símbolos de debug foram extraídos e
  executados; permanece validação em Windows limpo antes de publicar.

Plano: arquivo `.cooked` preparado para o jogo ao lado do `.range`, com fallback para o cru. Etapas 1 (medição
`[Load]`) e 2 (cache de shader GLSL, merge do LibLoad só com materiais novos) feitas em 2026-10-03; comparação
visual automática sem diferenças atribuíveis ao cache. Biblioteca GLSL enxuta por shader (só as funções
usadas) também feita: compilação ~4× mais rápida, imagens idênticas. Falta o usuário conferir jogos reais.

Aberto:

- Fast Shader Loading (valores como uniform) é opção no painel Render, desligada por padrão: carrega muito
  mais rápido, mas custa ~45% do FPS em cena pesada. Ideia aberta: uniform só para materiais repetidos (mesma
  estrutura) e constante para os únicos.
- Etapa 4 parcial (2026-10-03, sem formato novo): normais/tangentes e BVH de física compartilhadas entre malhas
  de conteúdo igual (800 esferas: conversão 2,9 s → 0,8 s). Malhas únicas ainda calculam tudo; guardar pronto
  exigiria o `.cooked`.
- `.cooked` começou (2026-10-07): pontos do Convex Hull gravados ao jogar o `.blend` e copiados pelo Export
  Game (física 1,6 s → 0,04 s no teste de 12 objetos). Binário dos shaders de material também (310 → 3 ms);
  com o botão Cook o LibLoad do teste foi de 2,4 s → 0,47 s. Buffers de malha (2026-10-08): malhas com
  10 mil loops ou mais guardam de que loop vem cada vértice e os índices; LibLoad do teste 850 → 295 ms.
  Tangentes cozidas também (2026-10-08): malha do teste 32 → 4 ms. Sem mínimo de loops: 200 malhas de 112 loops 45 → 21 ms. Normais e BVH de física cozidas: 200 malhas de 8 064 loops 1 820 → 259 ms. Falta conferir num jogo real. Jogo exportado guarda os shaders num cache do
  usuário e aquece todos na primeira abertura em cada GPU/driver, com tela de texto (sem barra de progresso).
- Texturas (2026-10-03): PNG decodificados em paralelo, 80 imagens 2048² 2,2 s → 0,7 s. O resto é upload
  serial na GPU. [Preparar texturas DDS](plano-texturas-dds.md), no main: derivados fora do `.cooked`,
  upload BC1/BC3 e fallback RGBA8 passaram no player em cena controlada. Build final do editor/player,
  regressao completa incluindo PREMUL e conferencia visual da textura alpha pelo usuario passaram.
  Pendente: visual no jogo real, load/VRAM no RolimaRacer/iGPU e execucao Linux.
  Marco 4 no main (2026-10-22): DXT POT carrega so os blocos, sem RGBA na CPU; pixels decodificados
  sob demanda (Python, pintura, VideoTexture, fallback sem S3TC). Falta medir load/RAM/VRAM contra PNG.
- Preparar Audio (2026-10-22, no main): OGG Vorbis q5/q4 por encoder externo (FFmpeg com libvorbis),
  streaming dos longos. Export runtime/RangeArmor monta copias de todos os `.range` da pasta (LibLoad
  incluso) com DDS e audio. Falta ouvir no jogo, LibLoad em gameplay e medir pacote real do RolimaRacer.
- Tela de loading do LibLoad (2026-10-03): `asynchronous=True` agora tem progresso real (conversão por
  objeto, depois texturas e shaders um a um) e o merge se espalha em frames de ~8 ms. Falta o usuário testar
  num jogo real; a abertura/link do arquivo ainda é síncrona. Luz nova recompila a cena uma vez só depois
  de todas as bibliotecas da fila (20 arquivos com lâmpada: 9,8 s → 5,6 s); sobra o custo de compilar ~15 ms por
  shader com muitas luzes. `Range.logic.setLibLoadFrameBudget(30)` na tela de loading: 5,3 s → 3,6 s. Ideia aberta:
  com lâmpada, cada material novo compila duas vezes; esconder os objetos até a recompilação final cortaria ~metade.
  Compilação paralela no driver testada e descartada (despacho já custa ~4 ms por shader).
- Cena com tela de loading (2026-10-03): `addScene(nome, 0, asynchronous=True)` compila os shaders aos poucos e só
  então põe a cena na lista; aplicado no `BrainCore` do RolimaRacer. Falta o usuário testar no jogo.
- Último caso (decisão do usuário): etapa 3, `.cooked` v1 (`.range` enxuto + texturas DDS), interruptor e
  status na UI. Só se o `[Load]` ainda mostrar ganho a buscar.

Descartado: cache de shader em disco (`glProgramBinary`, etapa 5). Testado em 2026-10-03 com 200 esferas:
todos os binários carregaram, mas a cena ficou mais lenta (4,4 s contra 3,2 s), porque o cache do próprio
driver NVIDIA já é mais rápido; o pedido de binário recuperável ainda desliga esse cache (1ª rodada 13 s).
Código revertido.

### Multiplayer nativo

Núcleo (`source/source/gameengine/Network/`, frentes A–J), integração na engine (`KX_NetworkManager`,
`Range.network`, `--server` headless, predição, RPC, troca de cena) e runtime Web com WebSocket estão na main e
validados no Linux e no Windows. Plano em [`multiplayer-plan.md`](multiplayer-plan.md), contrato em
[`multiplayer-protocol.md`](multiplayer-protocol.md), registro técnico em
[`NOTES-engine.md`](../source/source/gameengine/Network/NOTES-engine.md).

Aberto:

- **Complemento Steam** (Windows implementado, SDK 1.55, `Range.network.steam`;
  [guia](steam-complement-development.md),
  [plano](steam-multiplayer-plan.md)). Pendentes: dois jogadores em redes distintas com relay confirmado,
  convites aberto/fechado, corrida real com carros e saída/reentrada, AppID comercial, revisão de
  distribuição, Linux, conquistas e avaliação visual no RolimaRacer. Web segue com WebSocket; não há cross-play Steam.
- `scene-change` não tem cenário no `run_net_test_win.sh` (só no Linux).
- IPv6: o build é `ENET_IPV4_ONLY`; dual-stack compila e funciona entre dispositivos, mas `::1` falha nesta
  máquina Windows por configuração local de rede (Hyper-V/WSL), não por código.
- Predição de veículo fora da v1 (só interpolação); replay completo do Bullet fica para pós-v1.

### Web (WebGL/WebAssembly)

Estado: runtime Web com render, entrada (teclado, mouse, gamepad, toque), save (IDBFS), áudio, troca de cenas
e Python; validador, pré-voo e empacotamento prontos. Planos: [web-profile-validation-plan.md](web-profile-validation-plan.md),
[web-deploy.md](web-deploy.md), [web-remaining-execution-plan.md](web-remaining-execution-plan.md).

Aberto:

- **Build Linux com Python wasm32:** configure, build e carga no Chrome headless passam (alinhamento do `ImBuf`
  corrigido em 2026-10-13; ver `web-python-poc-plan.md`). Falta teste ponta a ponta jogável/visual antes de
  refazer o pacote Linux com `web/` (o atual usa `SKIP_WEB=1`).
- **Pré-voo M1:** falta importar o relatório de erros de shader/Python no editor (passo 5, UI); hoje o
  "Importar pré-voo Web" lê JSON manual.
- **M4 (picos de frame no celular) adiado** em 2026-09-23: reabrir só se um jogo com filtros 2D medir mal.
- **Reverb Area:** validar ouvindo no jogo real; no Web o EFX não existe no backend SDL (sem diferença audível,
  confirmado em 2026-10-07). Falta desenhar no viewport a zona de efeito total.
- **Áudio 3D/efeitos OpenAL** e `Sound.data()`/`buffer()` (sem numpy): só se algum jogo precisar.
- **Filtros 2D:** refinamento visual e custo de múltiplos passes ficam para depois; opcionais na Internet.

### VR no celular (Web, estilo Cardboard)

Estado: pose da cabeça pelo `deviceorientation`, head tracking
na câmera, distorção de lente no Side-by-Side e botão "Entrar em VR". OpenXR (headset) adiado até haver hardware.

### Idioma (English, Português, Español, Русский)

Editor compilado com i18n e painel Web traduzido no Windows (ver changelog de 2026-09-20). Pendente:

- Conferir na janela real do Windows: Preferências > System > **International Fonts**, escolher **Language** e ligar
  **Interface**; ver fonte, acentos e o menu (Default, English, Português, Español, Русский; cirílico depende da fonte Roboto). Decidir se o padrão de fábrica deve vir
  com a tradução ligada (hoje segue o 2.79: desligada).
- Auditoria: `RangeEngine -b --python tools/tests/web_profile/i18n_audit.py -- <idioma> [saida.txt]` lista textos sem
  tradução. Restam lacunas do catálogo do Blender 2.79 (pt_BR ~455, es ~511, ru ~1 124). Textos fixos dos layouts Python
  (`layout.label(text=...)` etc.): scan estático em `i18n_scan_labels.py` e traduções em `translations_labels.py`
  (2026-09-24; restam só nomes próprios, códigos e palavras iguais nas duas línguas). Textos em C fora do RNA
  (`IFACE_`/`TIP_`/`N_`): scan em `i18n_scan_c.py` e traduções em `translations_c.py` (2026-09-24; em pt/es restam
  códigos e nomes; no ru, 90 lacunas do catálogo russo do Blender). O russo (e o es) de `translations_ui.py`, `translations_labels.py` e `translations_c.py` precisa de revisão nativa.
- Complemento dos catálogos `.po` ausente do MO instalado: 436 entradas pt_BR e 493 es foram carregadas por
  `translations_catalog.py` (2026-09-24). Na auditoria de fonte, as lacunas passaram de 1 279 para 1 030 (pt_BR) e
  de 1 336 para 1 089 (es); o restante inclui identificadores, ícones e termos técnicos/iguais ao inglês.
- Mensagens das regras Web traduzidas (2026-09-23, `translations_rules.py`; es/ru pedem revisão nativa). Textos em
  português dos operadores da Range (flowmenu: editor externo e assistente de componente; veículo; partículas)
  passaram ao inglês com tradução (2026-09-24, bloco `MESSAGES` de `translations_labels.py`), inclusive o addon opcional
  `addon_editor_shot_tool.py` (a cópia antiga em `tools/ProjetoCutscene` ficou como estava). As mensagens `self.report` do flowmenu e do veículo já passam por `tip_()`.
- Linux: `linux-editor` recompilado com `WITH_INTERNATIONAL=ON` e `engine_i18n.py` com 36 ok (2026-09-26); os
  `blender.mo` (pt_BR, pt, es, ru) saem em `bin/2.79/datafiles/locale/` e o `package-runtime.sh` copia o `bin`
  inteiro. Seletor de idioma conferido na janela pelo usuario (2026-09-26).
- Roteiros manuais citam os botões pelo nome em português; em inglês são Validate Web, Export Web, Open in browser.

### Linux x86_64

`RangeRuntime` e `RangeEngine` compilam e rodam em Linux nativo; pacote compilado em container Ubuntu 22.04
(glibc 2.35) com as `.so` em `lib/`. Ver [linux-build.md](linux-build.md). Pendente:

- **Export RangeArmor no Linux (musikai/Fumangy, 2026-10-20) — fazer ao abrir no Linux**: corrigido no
  código, falta validar lá. (1) Gerar o pacote com `tools/linux/package-runtime.sh` e conferir que
  `2.79/python/bin/python3.11` está dentro e roda fora da máquina de build (sem `/opt/anastacio-python311`).
  (2) Recompilar o painel no container (`stage_rangearmor_linux.sh`) e criar um New Project: `EngineLinux64`
  deve vir `./engine/Linux64/AnastacioRuntime`. (3) Exportar pelo botão de um clique do editor um `.range`
  qualquer, inclusive com config.json antigo (`python3.10`/`RangeRuntime`). Depois publicar como 0.5.4.
- **Confirmações de usuários do Discord:** Fumangy no Ubuntu 26.04 (dependências, desde 0.4.5); Kitsuy com
  `.mp3`/`.ogg` e `colormanagement` (0.4.6), clone limpo + presets e `setHalfAnimations(1)` no build próprio;
  mandar ao Kitsuy o build com as correções de 2026-09-28.
- **Zip Windows 0.4.4 refeito com `/`:** falta abrir os `.exe` da cópia extraída e subir o asset
  (`gh release upload --clobber`). Não usar `Compress-Archive` do PowerShell 5.1.
- **API float/int/bool do Kitsuy** (`m_float1..9` etc., 2026-09-29): não integrada. Perguntar o caso de uso e,
  se valer, propor propriedades tipadas com nome ou um vetor `own.data`.
- **Cycles OpenCL no Linux com GPU AMD:** sem máquina para testar (WSL não serve). Roteiro: Preferences > System >
  Cycles Compute Device = OpenCL, Render Device = GPU Compute, renderizar a cena padrão e bake de AO comparando com
  a CPU. Cubins CUDA sm_75/86/89/120 no release, só sm_120 testado em hardware. OSL desligado.
- **FFmpeg 5+/OpenColorIO 2.x (2026-10-13):** compila no Ubuntu 24.04 e no Windows; falta decidir se o pacote Linux liga o FFmpeg (`WITH_CODEC_FFMPEG=OFF` hoje).

### Cutscene nativo

Fases 0–2 e 4–5 implementadas; validação manual (Play → Stop → Play e standalone) aceita em 2026-09-20.
Aberto: Fase 3 (ícones PNG próprios, sem substituir os `ZOOMIN`/`ZOOMOUT`). Ver
[plano](cutscene-native-integration-plan.md) e [roteiro](cutscene-native-example.md).
Evento Camera Path (2026-09-30): falta relinkar `RangeEngine` e o usuário testar no jogo. Export/import JSON cobre
os 18 tipos de evento (schema 2) e o Wait Trigger é liberado por mensagem ou `scene.release_cutscene_trigger()`
(branch `cutscene/events`, 2026-10-04, testes headless no Linux passaram; falta o usuário testar no Windows/jogo
real). Pendente: liberar por propriedade (decisão em aberto, ver [notas](notes-cutscene-events.md)).

### World Status

Causa raiz achada e corrigida em 2026-09-20 (o World do `startup.blend` não passava por `BKE_world_init`); as oito
propriedades aparecem em `scene.world.properties` num File > New. Painel Global Properties aceito pelo usuário na janela
do editor (2026-09-20). Nomes passados para inglês em 2026-09-25 (`horario_sol` virou `sun_hour`); falta o usuário
conferir o File > New na janela do editor. Ver changelog, seções "World Status".

### World Sound (gerenciador de áudio nativo)

Etapas 1 e 2 feitas em 2026-10-12 (aba no editor, `KX_AudioManager`, `Range.audio`; ver changelog e relatório).
Pendente:

- **Ouvir no jogo real**: só a parte sem som foi testada (registro, API, troca de cena, em `--server`). Falta o
  usuário conferir a aba na janela e ouvir crossfade, avanço da playlist, pausa/retomada e o eco das Reverb
  Areas em Music/Ambient (som 2D com efeito OpenAL nunca foi ouvido aqui). Cena:
  `tools/debug/cenas/criar_cena_world_sound.py`.
- **Etapa 3 (comando por mensagem)** feita em 2026-10-24; falta ouvir `play`/`next`/`stop` por mensagem com janela.
- Escopo fechado pelo usuário em 2026-10-12: só os módulos Music e Ambient. Efeitos e fala continuam nos
  próprios objetos (Speaker / Sound actuator); não haverá módulos Efeitos nem Voz.
- Depois: salvar volumes do jogador, música atravessando a carga de outro `.range`, conferir se o export
  Web/Android leva os áudios externos.

### Animation Events

Revisados em 2026-09-25 (crashes, threads, sensor, painel; ver changelog). Testes headless do editor e do runtime
passaram. Falta o usuário validar o painel na janela do editor e um jogo real com Animation Events (callback Python
e sensor Animation Event).

### Vehicle System / Vehicle Lab

[Ragdoll — plano de evolução](ragdoll-modernization-plan.md) (2026-10-14):
módulos confirmados e dois scripts do RolimaRacer corrigidos; 100 ciclos por cada um
dos quatro rigs reais passaram no player (20/20/22/23 corpos), além de regressão de
menu, Active inicial e falha de alvo. Usuário validou os scripts no jogo; rodada
`194141` teve três inputs, dois impactos, cinco retornos, sem erros ou SPIKE próximo.
Novo addon de [autoria](ragdoll-authoring.md) com prévia por osso, caixas, geração
transacional e Undo/Redo passou no editor; usuário validou a prévia em rig próprio.
Collections por armature organizam corpos e empties, com persistência e Undo/Redo
verificados; painel acessível pela armature em Object Mode ou por um objeto gerado.
Addon legado removido do fonte/instalação a pedido do usuário; scripts do jogo preservados.
Novo [componente comum](ragdoll-runtime.md) passou em cinco rigs simultâneos, 100 ciclos
por modo FREE/ANCHOR, Active inicial, NPC permanente, retorno automático, herança
angular/linear, bloqueio/veto de retorno e Undo/Redo da preparação completa. Demo com
cinco humanoides/50 corpos passou 370 frames. Presets Duro/Equilibrado/Leve, massa e
juntas por osso implementados. Pendentes: avaliação visual dos presets/personagem real,
migração do adaptador RolimaRacer, colisões configuráveis, cápsulas/Character, volume
de retorno em cenários complexos, blend/animação de levantar, instâncias por grupo e
exportadores/Web. Não houve C++ novo; adicionar somente por limitação demonstrada.
Baseline: duas rodadas com picos dominados por `endframe.swap`. Instrumentação opt-in dos
scripts validada em jogo real: rodada `20261014-192125`, três inputs e três impactos,
seis retornos sem erros; nenhum SPIKE nas janelas das quedas. Ativação do componente
0,436–0,538 ms (20 corpos), retorno do controlador até 1,076 ms; pausas longas entre
quedas dominadas por swap. Esse baseline é do componente legado corrigido; não é
benchmark do novo núcleo. Refinamentos e validações restantes estão indicados acima.
Ver [eventos](engine-profiling.md#eventos-de-ragdoll-do-rolimaracer).

[Plano revisado de veículos](vehicle-system-plan-2.md) (2026-10-22): integração
proposta com Smart Components e reaproveitamento do controlador avançado do
RolimaRacer. Pendentes: V0 baseline em cena e contrato de configuração/entrada;
V1 modernizar o componente básico; V2 extrair assists arcade por etapas;
V3 presets/documentação; V4 adaptador e validação no jogo real. As antigas fases
A/B/C já estão no código e saem do inventário de recursos ausentes; validações
específicas de dirigibilidade continuam necessárias. Primeiro lote V1: campos
tipados, diagnóstico e gizmos no básico; demo/template alinhados, 25 checagens
de editor e smoke no player (força legada e torque/câmbio) PASS. V0 ganhou
inventário dos cinco veículos salvos do RolimaRacer, sem alterar o jogo. Pendentes
na V1: preparação com Undo/Redo e avaliação com janela; V0–V4 não estão fechadas.
Início V2: controlador arcade com LUT de direção do RolimaRacer, comandos externos
e botão próprio; editor e player força/torque PASS. Drift, boost, roll e
estabilização ainda pendentes; jogo original preservado.

### Destruição e explosões

Plano aprovado em 2026-09-29; F0 (DNA, RNA e painéis), F1 (Generate Fragments), F2 (quebra por colisão e `shatter()` no runtime), F3 (`scene.explode()`, pavio, impacto, cadeia, Effect e `detonate()`), F4 (Max Debris, `onBreak`/`onExplode`, impulso por massa nos pedaços) e F5 (demo em `source/release/demos/Destruction/`, API no `.rst`) prontas; falta o usuário jogar a demo e ajustar a sensação: objetos
pré-fraturados (Cell Fracture) e explosivos, com os painéis Destruction e Explosive na aba Physics e
`scene.explode()`, em fases F0–F5. Protótipo Python validado por teste automático no runtime
0.4.5 (fora do git, em `tools/ADD na engine anastacioEngine/`).

Em 2026-10-12 o painel Explosive ganhou Particle Explosion (5 tamanhos, estilos Fire/Electric/Concrete/Water, cores e
quantidades), Ground Mark (decal no chão) e Mark Nearby Objects, todos com binding Python em `KX_GameObject` (ver
changelog). Light Flash (clarão de luz) feito em 2026-10-21; falta o usuário conferir no editor (lâmpada some ao parar o jogo) e na demo.

### Deformação por impacto

Implementada em 2026-10-02 (painel Deformation, `KX_DentDeformer`, `dent()`/`resetDent()`; ver changelog). Falta validar no
`RangeRuntime` com `tools/create_dent_test.py` e ajustar a sensação numa cena real (lataria de carro). Possível v2: máscara de
amassado na cor de vértice para o material misturar tinta arranhada.

### Câmera: foco, rastreio e Camera FX

Implementado em 2026-09-29 (fases 1 a 5 do plano original); referência em [camera-fx.md](camera-fx.md).
Validado no `RangeRuntime` com `tools/create_camera_fx_scene.py` (foco por propriedade, Drone, shake, fallback
após remover o alvo, efeitos desligados em jogo). Pendente: conferência visual dos filtros e custo medido
(`tc_filters2d`) no Rolima Racer; troca dos scripts do jogo fica para quando o usuário decidir.

### Logic Bricks → Python Component

Botão **To Python** no Logic Editor (`bl_operators/logic_to_python.py`), fases F1–F12 feitas (modos Component,
Module e Script; todos os bricks cobertos, exceto o controller Python, Add Object de camada ativa e Sound
empacotado). Cenas `tools/create_logic_convert_scene*.py`. Pendente:

- Usuário testar no editor com um objeto real lotado de bricks e num jogo real; bricks sem cobertura em jogo:
  Vibration, Screenshot, Load Config. Conferir os rótulos traduzidos do brick Property.
- Limites conhecidos: nos modos Module/Script outro controller Python que leia o objeto no mesmo quadro vê a
  mudança um quadro antes; Near/Radar medem até o centro (a engine usa esfera/cone físico) e só enxergam Actor
  com física.

### Logic Tree (lógica por nós)

[Plano v1](logic-tree-plan.md). F0 a F7 implementadas e testadas em background/runtime (2026-10-23);
complemento aos Logic Bricks, compila para bricks nativos. Pendente: aceite visual com janela (cores por
conjunto, Active, painel N em caixas, teste dos 15 s "Espaço → pular"). Futuro na seção 20 do plano
(pinos de dado, Convert to Nodes para Expression/Xor/Xnor/Python Script).

### Android / iOS

Android v1 concluído (2026-09-24): APK/AAB com WebView embutindo o pacote Web, export pelo editor, release
assinado, controles por toque e sensores, validados em aparelho físico. Publicação na Play Console adiada por
decisão do usuário. Plano em [android-export-plan.md](android-export-plan.md) e
[android-touch-controls-plan.md](android-touch-controls-plan.md). Rota nativa (NDK) abandonada; iOS fora do escopo.

- **Release sem template Android (2026-10-13):** zip Windows da 0.5.0 sem `web/android-template` e tar Linux sem
  `web/`. Corrigido no código (`stage_release_web.py`, `android.template_dir()`); falta publicar a versão
  corrigida e rodar o pacote Linux com o script novo.
- **Alternância manual de controles para menus (2026-10-14):** implementada no template Web/APK; falta validar em
  celular real (menu, retorno à partida, rotação), incluindo iframe do itch.io.

### Outros

- **Associação de arquivos**: abrir `.blend` e `.range` direto com os executáveis adequados (instalação/registro
  no Windows, duplo clique).
  Registro/remoção (`-r`/`-u`) e comandos do Registro validados em 2026-09-24; falta somente validar o duplo clique no Explorer.
- **Export presets (RangeArmor)**: falta o teste manual (projeto novo e antigo) do plano.
  `company_name`, `icon_path` e toggles desktop já são gravados por `wm.py`, com extensão do schema
  registrada no plano; a pendência é de validação manual, não de implementação desses campos.
- **Auditoria de `source/blender`** ([relatório](relatorio-varredura-bugs-silenciosos.md)): os 26 itens têm
  correção ou descarte; falta só GPU-001, testar `gl_load()` numa sessão interativa já aberta.
- **Auditoria do Cycles** ([relatório](relatorio-varredura-cycles.md)): CYC-001 a CYC-012 corrigidos; faltam as
  validações funcionais listadas no relatório (I/O injetado, corpus IES, cópias acima de 2 GiB em CUDA/OpenCL).
- **Release**: antes da próxima distribuição, declarar se o fork sai como GPLv2-or-later ou GPLv3 e incluir o
  arquivo de licença correspondente na raiz/pacote.
- **Metaball no jogo (futuro, sem pressa)**: hoje o conversor (`BL_BlenderDataConversion.cpp`) ignora
  `OB_MBALL` e a metaball some no Play; a saída é Alt+C → Mesh. Proposta: converter a superfície em malha
  estática ao dar Play, como curva/texto (custo só no carregamento). Versão dinâmica (re-tessellar a cada
  frame) descartada por ora: pesada na CPU; só com caso de uso concreto, de preferência na GPU.
- **Compositing no jogo — próximas fases**: Texture nodes só como bake. Glare do Blender 5 feito
  (Bloom, Sun Beams, Blender 5 Style com Smoothness); o tipo Kernel (convolução/FFT) fica fora. Defocus pesado e
  Denoise ficam fora. O que já roda está no changelog (2026-10-26).

## Performance

- **Range Trace ([range-trace.md](range-trace.md))** — fases 1 a 4 feitas (scripts/runtime no relatório e no
  launcher em 2026-10-24). Falta usar num jogo real com som (o `--server` não toca).
- **Static Batch:** com ele ligado empatamos com a ThunderPlayer no benchmark de 2026-10-09
  ([batching estático e culling](batching-estatico-e-culling.md)). Grupos dupli entram desde 2026-10-21; grupo só
  RAS ficou impossível (construtor protegido). Opção Auto Static Batch na cena feita em 2026-10-26; falta medir
  no benchmark da Thunder com ela ligada e decidir se vira padrão em arquivo novo.
- **Travadas do RolimaRacer (2026-10-10):** `Speed_FX` com Preload/Keep falta aplicar no `.range` do jogo. Abertos:
  picos longos no swap sem causa identificada; conferir de novo com 10 pilotos pelo menu (Range Trace, módulos
  `frames`, `shaders` e `profile`).
- **Trabalho repetido por frame:** contadores, detector (`61d35afc`) e `tools/check_trabalho_repetido.py` feitos.
  Falta rodar o detector nos jogos reais, parado e em movimento, com o usuário jogando (Range Trace, módulo `work`).
  Plano em [auditoria-trabalho-repetido.md](auditoria-trabalho-repetido.md); suspeitos e decisões em
  [auditoria-suspeitos.md](auditoria-suspeitos.md). Correções do nível 0 só compiladas, falta conferir em jogo.
- **Itens da auditoria ainda sem medição no jogo real** (detalhes em [auditoria-suspeitos.md](auditoria-suspeitos.md)
  e [resultados GL/RA](auditoria-claude-resultados.md)):
  - KX14: cache de `Text-Res` e envios de `KX_Speaker`; falta benchmark, visual do texto e áudio 3D (Doppler, pausa).
  - RA3 ([plano](ra3-transparencia-plan.md)): aceito visualmente; faltam casos adicionais do plano e benchmark conclusivo.
  - RA2 e Damage/GP8: falta benchmark/visual no jogo e avaliar cache das inversas por draw.
  - KX11/RA9: medir ganho em cena com muitas luzes, validar Point/Spot/CSM/Area e a reconstrução de
    `dynamicCasterSet` com Static Split.
  - KX10 (Auto Shadow): faltam Spot, deformadores, layers/parâmetros, ganho no jogo real e visual.
  - CV3/CV4/CV5/CV6, KX6/KX7/KX8/KX9: corrigidos; falta visual/runtime no jogo (o que falta em cada um está no relatório).
  - GL2/GL3 (replicação): compilados, não testados em rede.
  - Adiados com motivo: PH1, PY7, LP3 (estéreo), LP9/LP10, GP3, GP7, SP6/SP7/SP9/SP10/SP11/SP14/SP15.
  - RA4: em 2026-10-26 a cena de instancing fecha após `endGame()` no `--server` (código 0); falta conferir com janela.
- **Uploads repetidos de estado no PBR (2026-10-08):** cache de probes ausentes (+20% FPS com 1600 objetos PBR) e
  da camada de objeto. Falta validar o visual no jogo com probes e veículo; sombras e luzes/IES seguem sem cache.
  Procedimento em [engine-profiling.md](engine-profiling.md).
- **Contadores de render para o usuário final:** `Range.logic.getRenderStats()` e o overlay ImGui já existem;
  decidir se vira um HUD próprio de FPS + contadores, ligável no painel Render. Painel ImGui do profiler e
  `Range.logic.getEngineProfile()` só se fizer falta.
- Avaliar folhagem e LOD na cena real; impostor e bake de atlas já existem.
- **Navmesh dinâmica:** passos 1–7 feitos e aceitos em 2026-09-28. Restam: o aviso de Create Obstacle sem navmesh
  dinâmica não foi visto na tela; DetourCrowd fica para depois; segmentos de borda da Obstacle Simulation seguem
  os do build inicial.

## Iluminação e gráficos

- **Fog - Volumetric:** 10 itens em [plano-volumetric.md](plano-volumetric.md); itens 1-3 (vento/manhã, raios de
  sol, Fog Volumes) aguardando aceite visual; item 4 (Python/Logic) com o Codex.
- **Luz indireta (GI) baked** ([plano técnico](baked-lighting-plan.md)): lightmap Cycles + OIDN + light volume,
  painel com AO, `Static Lighting + Shadows` e GTAO feitos; AO e modo estático aceitos em cena simples. Falta:
  avaliação visual em cena maior e materiais variados, confirmar no jogo o fim do aviso OpenCL
  `kernel_lamp_emission`, validar no Linux e no Web, UV da lightmap por xatlas. Se o `LNK1104` do executável
  voltar, capturar o processo pelo Restart Manager antes de repetir o link.
- **SSGI nativo experimental** ([plano](ssgi-native-plan.md)): pendentes avaliação visual no jogo/Play, MSAA,
  core profile completo, VRAM total, temporal/Hi-Z e suporte além de Principled opaco direto.
- **Compatibilidade UPBGE 0.2.5b:** feita (9450a3b0): Mouse Logic Bricks, `World.skytype` e
  `Lamp.shadow_filter` migrados quando `upbgeversionfile != 0`. Conferido em 2026-10-26 com
  `tools/arquivo_upbge.blend` (sol abre como PCF Bail).
- **Sombra em Principled/PBR** (opcional): comparar lado a lado com material legado sob as mesmas luzes e ver o
  efeito de `ProcessLighting(true)` em todo material com nodes numa cena maior.
- **Sombra de CSM no Principled:** feita em 2026-10-26 (primeiro sol com cascata por draw, sem VSM nem sombra
  colorida no slot CSM); falta aceite visual com janela. PCSS já funciona nos dois caminhos (2026-10-25). Menu Hard/Soft/Realistic e PCSS
  virando sombra dura em Low/Very Low feitos em 2026-10-26.
- **Nós de material Game × Cycles × BI** ([matriz](node-material-support.md)): fases 1–6 feitas e validadas.
  Sem suporte: Point Density e Script.
- **Material rápido (receitas de nós):** falta o usuário conferir no editor e no jogo
  (`tools/create_material_recipes_test.py`, PBR e `legacy`). Próximos: mistura pela altura e Texture Array (só se 8+ camadas).
- **Nós de shader com estágios de vertex e geometry** ([shader-nodes.md](shader-nodes.md)): aceitos visualmente em
  2026-10-13. Falta: validar com o caso real do Naut; viewport desenhando quads com geometry stage; build Web;
  cor do cabeçalho do nó por estágio; presets Wind Leaves/Triplanar/Hologram; Show Generated Code;
  custo/`max_vertices` no painel; opção de sombra própria; conferir no editor o painel Script Uniforms e o nó
  GLSL Script vermelho com tooltip de erro; inspeção visual de Billboard/Strands/Explode e da direção do Fur Shells.
- **Bloom e SSR pelo World node graph:** compilado, falta validação visual.

## Validações manuais pendentes

- Nenhuma no momento.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
