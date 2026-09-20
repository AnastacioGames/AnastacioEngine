# Roadmap

Somente itens abertos, pendentes de validação ou explicitamente adiados ficam neste arquivo. Recursos
concluídos estão resumidos em [`../relatorio-melhorias-anastacioengine.md`](../relatorio-melhorias-anastacioengine.md)
e detalhados no [`changelog.md`](changelog.md). O histórico Web que antes ocupava este arquivo (bloqueios de
shader/GL, causas raiz de teclado/mouse/gamepad, IDBFS, cena de filtros) está nas entradas de 2026-09-12 a
2026-09-20 do changelog.

Auditado contra o git log e o changelog em 2026-09-20.

## Prioridade atual

### Web (WebGL/WebAssembly)

Estado: o runtime Web roda no navegador com render (luz GLSL, normal map `.dds`, sombras, filtros 2D), teclado,
mouse, gamepad, save (IDBFS), áudio (WAV/MP3/OGG e módulo `aud`), transição de cenas e Python. O validador
(marcos A–D), o pré-voo (marco E, automático depois do Exportar Web) e o empacotamento estão implementados; os
pacotes de teste 8201–8211 foram aceitos pelo usuário. Planos: [web-profile-validation-plan.md](web-profile-validation-plan.md),
[web-deploy.md](web-deploy.md), [android-web-export-roadmap.md](android-web-export-roadmap.md).

Aberto:

- **Deploy real fora do `localhost`**: CORS, cabeçalhos do `.wasm`, download de ~46 MB. As receitas de hospedagem
  e a compressão medida estão documentadas; falta publicar e testar de fato.
- **Aviso `glBlitFramebuffer` depth/stencil**: aparece uma vez no console; origem desconhecida, sem reprodução.
- **Patch customizado do SDL2/Emscripten** (remoção do gate de timestamp do gamepad): mora no cache de
  toolchain do emsdk, fora do controle de versão; não sobrevive a reinstalação limpa nem se propaga para outra
  máquina. Versionar (patch aplicado no build ou port SDL2 próprio).
- **Extração de erros de shader/Python no pré-voo** é heurística sobre o texto do runtime (não informa
  estágio/material do shader); "Importar pré-voo Web" segue para JSON manual.
- **Áudio 3D/efeitos OpenAL**: só se algum jogo precisar; `Sound.data()`/`buffer()` do `aud` indisponíveis por
  falta de numpy.
- **Filtros 2D**: refinamento visual e custo de múltiplos passes ficam para etapa posterior; tratar como
  opcionais na Internet.
- **Contorno `USE_RNA_RANGE_CHECK` (Emscripten)**: checagem desativada só para Emscripten em `rna_internal.h`.
  Resolver caso a caso (`ImageUser.fie_ima`, `Material.seed1`/`seed2`: tipo do campo DNA vs. hardmax da RNA),
  considerando compatibilidade com `.blend` legado.

### Linux x86_64

`RangeRuntime` e `RangeEngine` compilam e rodam em Linux nativo; pacote 0.4.0 publicado. Ver
[linux-build.md](linux-build.md). Pendente:

- Validar a janela real do `RangeEngine` numa sessão gráfica (GHOST/X11, ícones, i18n, addons Python); só foi
  testado em `--background`.
- Portar `WITH_OPENCOLORIO` (API 1 → 2.x, dezenas de call sites em `intern/opencolorio`) e `WITH_CODEC_FFMPEG`
  do editor para OpenColorIO 2.x/FFmpeg 5+ (desligados no preset `linux-editor`; só o wrapper `audaspace` do
  FFmpeg foi ajustado).

### Cutscene nativo

Fases 0–2 e 4–5 implementadas. Abertos: Fase 3 (ícones PNG próprios, sem substituir os `ZOOMIN`/`ZOOMOUT`) e
validação manual de Play → Stop → Play e standalone, incluindo `Spawn Object` disparar uma vez e limpar a
réplica no Stop/Restart. Ver [plano](cutscene-native-integration-plan.md) e
[roteiro](cutscene-native-example.md).

### World Status

As oito World Properties automáticas (`BKE_world_init`, `BL_ConvertWorldProperties`) foram implementadas e
compilam, mas não aparecem em um World novo (File > New) no teste real. Diagnosticar criação, versionamento e
atualização da UI. Ver changelog, seção "World Status".

### Vehicle System / Vehicle Lab

Executar o [plano 2](vehicle-system-plan-2.md) por marcos: Fase B (Steering & Brakes, incl. volante visual),
Fase C (Powertrain: drive type, torque/RPM, marchas), Fase A (Chassis: Center of Mass offset). Fase D está
fechada.

### Android / iOS

Sem decisão de implementação. Bloqueios conhecidos: `malloc_stats` ausente na Bionic, `GL/glu.h` ausente no
NDK e backend GHOST/APK inexistente. Ver [mobile-export-plan.md](mobile-export-plan.md).

### Outros

- **Associação de arquivos**: abrir `.blend` e `.range` direto com os executáveis adequados (instalação/registro
  no Windows, duplo clique).
- **Export presets (RangeArmor)**: falta o teste manual (projeto novo e antigo) do [plano](export-presets-plan.md).
  `company_name`, `icon_path` e toggle de plataforma não são gravados (whitelist do RangeArmor Panel); estender
  exige mudança no lado Godot, fora desta fase.
- **Auditoria de `source/blender`**: confirmar ou descartar os candidatos de
  [`relatorio-varredura-bugs-silenciosos.md`](relatorio-varredura-bugs-silenciosos.md), com reprodução,
  correção isolada e teste.
- **Release**: antes da próxima distribuição, declarar se o fork sai como GPLv2-or-later ou GPLv3 e incluir o
  arquivo de licença correspondente na raiz/pacote.

## Performance

- Investigar o custo residual de `MainRender` na cena de benchmark (GPU Skinning já descartado por A/B; nova
  hipótese começa por medição).
- Avaliar folhagem e LOD na cena real; impostor e bake de atlas já existem, o resto pode ser trabalho de asset.
- Vendorizar `Recast/`/`Detour/` a partir de `tools/recastnavigation-main` (a API de integração já usa
  `dtNavMesh`/`dtNavMeshQuery`; falta trazer a lib, com a varredura de bugs silenciosos).
- Navmesh dinâmica: hoje o navmesh é gerado uma vez (`mesh.navmesh_make`). Reagir a objetos móveis exige
  `DetourTileCache` e obstáculos temporários; escopo novo, não iniciado.

## Iluminação e gráficos

- **Resolução dinâmica**: opt-in em `Game Render Properties > Dynamic Resolution`. Falta validar numa cena
  GPU-bound, ligado/desligado, sem oscilação de escala nem artefatos nos efeitos.
- **CSM**: blend entre cascatas e debug tint já implementados; falta medir o custo de GPU dessas duas features.
- Avaliar antialiasing temporal somente com caso de uso e critérios de qualidade definidos.
- Aceitos como no-op no core profile (reabrir só com demanda concreta): motion blur legado, clipping de
  espelho/água e texto de debug via `BLF_draw`.

## Validações manuais pendentes

- **Sombras (Ketsji / Planos 1A e 5)**: validar no jogo real Play → Stop → Play e standalone, com múltiplas
  luzes/cenas, a transição do 9º para o 10º frame elegível de CSM, o cache de cascata e o split
  estático/dinâmico. Registrar separadamente os avisos de textura sem nível-base vistos em `-d gpu` (origem
  desconhecida). Ver [plano mestre](ketsji-engine-modernization-plan.md).
- **Migração de `shadowCulling`**: testar arquivo antigo com `maxphystep` gravado em 0/1/5/10 e confirmar que o
  comportamento de sombra é preservado.
- **Sol em `PostRenderScene`**: confirmar que Light Scattering/Lens Flare não piscam ao cruzar ângulos com
  `screenPos.w` nulo/negativo.
- **Profiler (Plano 2)**: opcionalmente conferir as categorias `CollisionDepth`/`TextureRenderers` como linhas
  separadas num relatório de benchmark.
- **Splash e About**: popup sobe em 1,2 s; painel inferior sem caixas cinzas; `Create Project`, recentes e
  links de rede interativos.
- **Outliner**: `View > Show Alternating Rows` ligado/desligado (cor de fundo do tema, rolagem, seleção,
  colunas de restrição).
- **Barra da 3D View**: Play, Standalone, Debug/Console, modos de sombreamento, atualização contínua (materiais
  animados e decals/projetores), Only Render, overlay, bloqueio de câmera/camadas, Edit Mode, redimensionamento.
- **Particles/UI**: aba Particles em objetos Empty e ordens ajustadas nos painéis Render Layers e Physics.
- **Gamepad no menu ImGui**: testar bindings com gamepad físico e ajustar áreas clicáveis.
- **Runtime Property Sensors/Actuators**: cena de regressão física (massa, velocidades, gravidade, referências
  a objetos removidos).
- **Captura de vídeo e OpenAL**: stress de start/stop de captura e múltiplos efeitos.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
