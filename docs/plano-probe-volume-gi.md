# Plano: Probe Volume GI (luz indireta por grade de sondas)

Status: F1a medida e commitada (6903b915). F1b escrita em 2026-11-03: SH9 trilinear por objeto, peso do SSGI no volume, prioridade para objeto movido; falta aceite visual com janela. Próximo: F2.

## Contexto
A ideia é ter luz indireta dinâmica, que acompanhe dia/noite, lanternas e portas e funcione fora da tela, onde o SSGI não chega. O caminho é uma grade automática de sondas atualizada aos poucos (no estilo DDGI, mas capturando por rasterização), que se liga e desliga. O rascunho anterior (docs/plano-probe-volume-gi.md) não foi gravado. Esta revisão confere cada ponto dele contra o código atual. Nada será executado hoje: o único entregável é o plano, que depois vai para `docs/plano-probe-volume-gi.md`.

## O que a revisão encontrou (conferido no código)

| # | Ponto do rascunho | Veredito | Motivo no código |
|---|---|---|---|
| 1 | "Várias rebatidas de graça" | **Errado como estava** | `KX_TextureRendererManager::Render` liga `m_capturing = true` e `FindProbe` retorna `false` durante a captura ([KX_TextureRendererManager.cpp:212](../source/source/gameengine/Ketsji/KX_TextureRendererManager.cpp#L212)). Ou seja, durante a captura as superfícies não recebem a luz das sondas. Para ter rebatidas, a grade precisa ser lida durante a captura, a partir de um buffer da rodada anterior (dois buffers, alternando), com um ganho menor que 1 para a luz não ir somando até estourar. |
| 2 | "N faces por quadro" | **Falta suporte** | `RenderRenderer` desenha todas as faces de uma vez (laço em `GetNumFaces`, [linha 338](../source/source/gameengine/Ketsji/KX_TextureRendererManager.cpp#L338)). É preciso um intervalo de faces por chamada, e o SH9 só pode ser pedido depois da 6ª face. |
| 3 | "Cubo de 8–16 px é barato" | **Parcial** | Cada face roda `CalculateVisibleMeshes`, `UpdateObjectLods` e `RenderBuckets` ([linhas 364-376](../source/source/gameengine/Ketsji/KX_TextureRendererManager.cpp#L364)). O custo é de CPU e draw calls, não de pixels. Por isso entram: `clip_end` curto, máscara de camadas (`GetIgnoreLayers` já existe), apenas objetos estáticos e medição de draw calls na F1. |
| 4 | SH9 por leitura na CPU | **Trocar na grade** | Hoje o SH9 vai por PBO + `glReadPixels` + projeção na CPU (`GPU_cube_sh9_reader_*`, [gpu_texture.c:757](../source/source/blender/gpu/intern/gpu_texture.c#L757)). Serve para poucas sondas, não para centenas. Para a grade: projetar o SH9 na GPU com um passe de fragment shader, escrevendo direto num atlas 2D ou 3D RGBA16F. Isso roda em WebGL2 sem compute e sem ida e volta para a CPU. A leitura atual continua para as sondas manuais. |
| 5 | Grade substitui as sondas | **Faltava** | Cada sonda serve também de reflexo (cubo com mips em `env_probe_mirror`). Um cubo de 8–16 px não serve para reflexo. Regra: a grade dá só o difuso; o reflexo continua vindo das sondas manuais ou do World probe. |
| 6 | 8 vizinhas por pixel (F2) | **OK, com risco** | Hoje são 2 slots por objeto, em uniforms (`GPU_material_bind_probe`, [gpu_material.c:6235](../source/source/blender/gpu/intern/gpu_material.c#L6235)). A F2 exige um sampler novo, e as unidades de textura já são disputadas (CSM, sombra colorida, sondas). Também é uma variante nova de shader, o que pesa no cache de shaders do .cooked e no aquecimento da 1ª abertura. A variante só pode existir quando o volume estiver ligado. |
| 7 | Anti-vazamento por Chebyshev (F3) | **Pesado para iGPU** | Seriam 8 leituras extras de profundidade por pixel. Ordem melhor: (a) deslocar a amostra pela normal; (b) classificar sondas (desligar as que estão dentro de parede, empurrar as que estão perto); (c) Chebyshev só no High. |
| 8 | Liga/desliga no DNA desde o início | **Simplificar** | As sondas atuais usam propriedades no Empty (`probe_radius`, `probe_realtime`…, [BL_BlenderDataConversion.cpp:3931](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp#L3931)). Seguir o mesmo padrão (Empty com `probe_volume`) mais um interruptor em Python evita DNA e do_versions na F1–F2. Campo no World só na F4, com zero valendo desligado (por causa da compatibilidade com a Range upstream). |
| 9 | Prioridade por "mudança de luz" | **Reaproveitar** | `CheckWorldChanged` já calcula uma assinatura de sol e céu e força a captura do World ([linha 265](../source/source/gameengine/Ketsji/KX_TextureRendererManager.cpp#L265)). Usar a mesma assinatura para marcar a grade inteira como suja. |
| 10 | Objetos dinâmicos | **Faltava** | Carros e personagens capturados nas sondas causam manchas e piscadas. Regra em "Objetos móveis" abaixo (portas entram). |
| 11 | Soma com o SSGI | **Confirmado: soma** | O composite do SSGI faz `scene.rgb + (result - base)` ([RAS_SSGIImage2DFilter.glsl:97](../source/source/gameengine/Rasterizer/RAS_OpenGLFilters/RAS_SSGIImage2DFilter.glsl#L97)). Regra em "Composição da luz indireta" abaixo. |

## Revisão do Codex (2026-11-03), conferida no código

| # | Ponto | Veredito | Conferência |
|---|---|---|---|
| C1 | Espaço de cor | **Aceito** | O display transform é compilado no fim de todo material (`game_view_transform` em `gpu_material_link_display_transform`, [gpu_material.c:1845](../source/source/blender/gpu/intern/gpu_material.c#L1845)). A captura sai em cor de exibição, com exposição e contraste, e `env_probe_mirror` volta para linear só de forma aproximada, depois de somar o SH9. Com rebatidas o erro acumula. |
| C2 | "Só estático" x portas | **Aceito** | Filtrar só por física não pega objeto movido por script, parent ou Action. |
| C3 | Orçamento de latência | **Aceito** | 256 sondas × 6 faces ÷ 4 faces/quadro = 384 quadros = 6,4 s por volta a 60 FPS. |
| C4 | F1 contraditória | **Aceito** | O resumo da F1 falava em SH9 na GPU e as notas adiavam para a F2. Corrigido: PBO na F1, com medição. |
| C5 | Contrato da captura parcial | **Aceito** | `NeedUpdate()` zera `m_forceUpdate` ao ser consultado ([KX_TextureRenderer.cpp](../source/source/gameengine/Ketsji/KX_TextureRenderer.cpp)). O estado tem de morar no volume. |
| C6 | Composição da GI | **Aceito, parcial no "baked"** | O SSGI soma (ver #11). Não há GI baked como sistema na engine (só textura pintada ou AO no material); vira aviso, não regra de código. |
| C7 | F1 grande demais | **Aceito** | F1 dividida em F1a (captura e medição) e F1b (difuso por objeto). |

## Regras novas (da revisão do Codex)

**Espaço de cor (C1).** A grade guarda luz **linear**. Durante a captura da grade, o display transform
fica desligado por um uniform (`game_view_transform` devolve a cor sem mexer), sem variante nova de
shader. O cubo é RGBA16F (no Web, sem `EXT_color_buffer_float`, o volume não liga: RGBA8 corta a luz).
O SH9 da grade é usado no material **sem** o `srgb_to_linearrgb` do fim de `env_probe_mirror`: a
conversão passa a valer só para os cubos das sondas manuais e do World. Medir na F1a o custo do uniform
novo e conferir que o cache de shaders do .cooked não muda de chave.

**Objetos móveis (C2).** Entram na captura todos os objetos visíveis nas camadas do volume, menos:
- física dinâmica, rigid body ou veículo;
- malha deformada (armature ou GPU Skinning);
- propriedade `probe_volume_skip` (o usuário marca o que não deve sujar a GI);
- camadas em `probe_volume_ignore_layers` (mesma regra de `GetIgnoreLayers`).

Porta animada, elevador ou objeto movido por script **entra**: quando ela se move, a luz muda com a
latência do rodízio. Na F1b, um objeto incluído que se moveu mais de 0,25 m desde a última volta
marca como prioridade as sondas a até `clip_end` dele.

**Orçamento de latência (C3).** Limite de sondas e tempo de volta por qualidade (60 FPS):

| Qualidade | Faces/quadro | Sondas máx. | Volta completa |
|---|---|---|---|
| Low | 2 | 64 | 3,2 s |
| Med | 4 | 128 | 3,2 s |
| High | 8 | 256 | 3,2 s |

Se a grade passar do limite, o espaçamento cresce até caber (aviso no console e no Scene Doctor).
Prioridade = distância à câmera + idade: cada sonda tem um prazo de 2 voltas; quem passa do prazo vai
para o começo da fila, então sonda longe não fica parada. Mudança de World marca a grade inteira
(assinatura de `CheckWorldChanged`); a mistura temporal soma no máximo 1 volta de atraso.

**Contrato da captura parcial (C5).** O estado fica no `KX_ProbeVolume`, não em `NeedUpdate()`:
- `m_current` (índice da sonda em captura, -1 = nenhuma), `m_nextFace` (0-5) e a posição da sonda
  fixada ao começar (o Empty pode se mover no meio);
- a cada quadro o agendador renderiza `[m_nextFace, min(6, m_nextFace + orçamento))`; se o orçamento
  sobra e a sonda terminou, começa a próxima no mesmo quadro (High chega a 1,33 sonda/quadro);
- **concluída** = 6 faces feitas e `GPU_cube_sh9_reader_request` aceito. Só então a sonda sai da fila.
  O SH9 vale quando o `poll` devolve o resultado; até lá a sonda mantém o valor antigo;
- pool de 4 leitores; se todos estão ocupados, o agendador espera (não renderiza face nova) e conta o
  quadro como "espera de leitura" no Performance Report;
- **Congelar** desliga o agendador só depois de uma volta completa com todos os SH9 lidos.

**Composição da luz indireta (C6).**
- Dentro do volume, o SH9 da grade **substitui** o difuso do ambiente (World ou sonda manual); não soma.
  O reflexo continua vindo dos cubos.
- O SSGI soma por cima, como hoje. Para não contar duas vezes perto da câmera, na F1b o SSGI ganha um
  peso menor dentro do volume (padrão 0,5, ajustável); medir com a cena de teste.
- Textura com luz pintada ou AO baked no material: aviso no Scene Doctor quando um material desses está
  dentro de um volume. Não há regra de código.

## Plano corrigido

**Ligar/desligar:** fica desligado por padrão. Só age se houver um Empty `probe_volume`. Interruptor e qualidade pelo Python (nome a definir). Tem modo Congelar (captura no load e para). As sondas manuais continuam como estão e cuidam do reflexo.

- **F1a — Captura parcial e medição (nada muda na imagem).** Empty-caixa gera a grade (espaçamento padrão de 4 m, limite por qualidade). `KX_ProbeVolume` com o contrato da captura parcial, intervalo de faces em `RenderRenderer`, cubo de captura compartilhado 16 px RGBA16F em luz linear, filtro de objetos móveis, `clip_end` curto e LOD baixo. SH9 pela leitura PBO atual com pool de 4 leitores. Mistura temporal. Saída só de depuração: `RANGE_PROBE_VOLUME_LOG` imprime tempo de volta, ms de CPU e GPU por quadro, draw calls por face e quadros em espera de leitura. Aceite: com o volume ligado, nenhuma travada acima de 1 ms atribuída à leitura (rodadas de ~10 s em Low/Med/High, desktop e iGPU); com volume desligado, custo igual ao de hoje.
- **F1b — Difuso por objeto.** `FindProbe` troca o SH9 dos 2 slots pelo SH9 trilinear das 8 sondas (centro do objeto), com fade na borda; sem o `srgb_to_linearrgb` para o SH9 da grade; peso do SSGI no volume; prioridade para objeto móvel que se mexeu. Aceite visual com a cena de teste.
- **F2 — Leitura das 8 vizinhas por pixel.** Projeção SH9 na GPU para um atlas (passe de fragment shader, sem compute), sampler do atlas e interpolação trilinear no shader, como variante condicional. Conferir as unidades de textura livres e o efeito no cache .cooked. Testar o caminho WebGL2 (`__EMSCRIPTEN__`).
- **F3 — Rebatidas e anti-vazamento.** Atlas com dois buffers, lido durante a captura com ganho abaixo de 1. Deslocamento pela normal e classificação das sondas; Chebyshev só no High.
- **F4 — Acabamento.** Campo no World (zero = desligado) e regra do Auto (iGPU em Low ou desligado). Entra no RANGE_WEAK_GPU, no Scene Doctor (volume grande ou sondas demais), no Performance Report (custo de GPU da etapa), na documentação rst e no site.

## Medição da F1a (2026-11-03, desktop)

Cena `tools/debug/cenas/criar_cena_probe_volume.py` (sala 20×20×4 m, 150 caixas, 1 caixa dinâmica, volume 6×6×2 no Med/High, 54 no Low), rodadas de 10 s, `RANGE_PROBE_VOLUME_LOG=1`:

| Qualidade | CPU da grade | Leitura (pico) | Volta | Esperas de leitor |
|---|---|---|---|---|
| Low | 0,34 ms/quadro | 0,15 ms | 2,5 s | 0 |
| Med | 0,54 ms/quadro | 0,18 ms | 1,8 s | 0 |
| High | 0,88 ms/quadro | 0,36 ms | 0,9 s | 0 |

O pedido de leitura com `glGetTexImage` custava ~0,55 ms de CPU por sonda (driver convertendo half
float). Trocado por FBO + `glReadPixels` no desktop também (caminho que já era o do Web): 0,03 ms.
Isso vale para as sondas manuais. Aceite da F1a (nenhuma travada acima de 1 ms pela leitura): OK no
desktop. Falta: iGPU e custo de GPU (o log mede só CPU).

## Arquivos principais
- [KX_TextureRendererManager.cpp](../source/source/gameengine/Ketsji/KX_TextureRendererManager.cpp) e o .h: grade, agendador, faces parciais, `m_capturing`.
- [KX_LightProbe.cpp](../source/source/gameengine/Ketsji/KX_LightProbe.cpp): base de uma `KX_ProbeVolume` nova.
- [BL_BlenderDataConversion.cpp](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp): leitura do Empty `probe_volume`.
- [gpu_material.c](../source/source/blender/gpu/intern/gpu_material.c) e [gpu_shader_material.glsl](../source/source/blender/gpu/shaders/gpu_shader_material.glsl): bind e leitura do atlas.
- [gpu_texture.c](../source/source/blender/gpu/intern/gpu_texture.c): passe de projeção SH9 na GPU.

## Verificação (por fase)
- Cena de teste com sala fechada, janela, sol girando e porta animada (skill cena-de-teste).
- Rodadas de ~10 s comparando Off, Low, Med e High no desktop e na iGPU, olhando ms de GPU e draw calls no Performance Report.
- Com o volume desligado, a cena tem de sair idêntica e com o mesmo custo de hoje: comparar captura e FPS antes e depois.
- Build Web com teste do atlas RGBA16F (com e sem EXT_color_buffer_float).
- Aceite visual com janela, só quando o usuário pedir.

## Notas da leitura do código para a F1 (2026-11-03)

Conferido em `KX_TextureRendererManager`, `KX_LightProbe`, `BL_BlenderShader::Update` e
`env_probe_mirror`, antes de escrever a F1. Pontos para a revisão:

1. **SH9 na F1 pela leitura assíncrona atual, não pelo atlas na GPU.** Na F1 o material ainda lê os 2
   slots, e o SH9 de cada slot é um uniform vindo da CPU (`GPU_material_bind_probe` → `unfprobesh`).
   Um atlas na GPU não tem leitor até a F2. Com o rodízio, terminam 2/3 de sonda por quadro no Med e
   1,33 no High, então a leitura PBO + fence (`GPU_cube_sh9_reader_*`) é de 1-2 cubos de 16 px por
   quadro. Que isso não trava ainda precisa ser **medido** na F1a (Codex C4). O passe de projeção na
   GPU fica para a F2, junto com o sampler do atlas.
2. **Um cubo de captura compartilhado** pela grade inteira (16 px, RGBA16F). A grade captura uma sonda
   por vez; `GPU_cube_sh9_reader_request` copia o cubo para o PBO na ordem da GPU, então o cubo pode
   ser reusado pela próxima sonda logo depois. Memória por sonda: só 27 floats (+ 27 da mistura
   temporal). Pool pequeno de leitores (ex.: 4), cada um marcado com o índice da sonda.
3. **Classe `KX_ProbeVolume : KX_CubeMap`** com o Empty-caixa como viewpoint. `SetupCamera` põe a
   câmera na posição da sonda atual (escolhida pelo agendador), então `RenderRenderer` serve quase
   como está; muda só o intervalo de faces (`firstFace`, `numFaces`) e o SH9 é pedido só depois da 6ª
   face. Fica fora do laço normal de `NeedUpdate` e é chamada pelo agendador.
4. **Como o volume entra nos 2 slots sem mudar shader na F1.** `FindProbe` continua escolhendo os cubos
   de reflexo (sondas manuais ou World). Se a posição do objeto está dentro de um volume, o SH9 dos dois
   slots é trocado pelo SH9 trilinear das 8 sondas vizinhas (calculado na CPU, no centro do objeto), com
   fade na borda do volume. Para isso `ProbeSlot` ganha um buffer `float shData[9][3]` próprio (o slot
   é local em `BL_BlenderShader::Update`, o ponteiro não escapa). Sem cubo de reflexo não há slot: com
   um volume na cena, a captura do World (`AddWorldProbe`) é criada sempre.
   Limite conhecido: na F1 o difuso é por objeto (centro), não por pixel; objetos grandes (chão, prédio)
   ficam com uma cor só. Isso é o que a F2 resolve.
5. **Só estático na captura**: filtrar em `CalculateVisibleMeshes` objetos com física dinâmica e
   malhas deformadas (armature/skinning). Conferir no código qual é o teste certo antes de escrever.
6. **Sondas ainda sem SH9 válido** (primeira volta do rodízio) ficam fora da interpolação (peso 0,
   renormalizado); se as 8 estão inválidas, vale o SH9 do slot como hoje.
7. **Mistura temporal**: `sh = mix(sh_antigo, sh_novo, a)` com `a` = 1 na primeira captura e ~0,5 depois,
   para não piscar quando o sol muda aos poucos.
8. **Propriedades no Empty** (padrão das sondas): `probe_volume` (espaçamento em m, 0 = 4),
   `probe_volume_quality` (Low/Med/High), `probe_volume_clip_end`, `probe_volume_freeze`. Tamanho do
   volume = Empty desenhado como Cube (meia extensão = display size × escala), como o parallax em caixa.

## F1b (2026-11-03)

- `KX_ProbeVolume::SampleSH`: SH9 trilinear das 8 sondas em volta do centro do objeto (só as já lidas, renormalizado). Peso 1 dentro da caixa, cai a 0 meio espaçamento fora dela, e menor enquanto as 8 não foram lidas.
- Material: uniforms `unfprobegridsh[9]` e `unfprobegrid` (sem variante); no fim de `env_probe_mirror`, depois do `srgb_to_linearrgb` das sondas, o SH9 da grade substitui o difuso pelo peso. O reflexo continua dos cubos. O texto do shader mudou, então o cache de shaders do .cooked recompila uma vez.
- SSGI: força × `probe_volume_ssgi` (padrão 0,5) com a câmera dentro do volume, com transição na borda (`RAS_2DFilter::SetSSGIStrengthScale`).
- Objetos movidos: a cada 30 quadros, objeto capturado que andou mais de 0,25 m marca como prioridade as sondas a até `clip_end` dele (abaixo das sondas atrasadas, para não travar as longe).
- Cena de teste agora usa Principled (Shading Nodes), World, paredes vermelha e verde, e salva `shot_<cena>.png` em 8 s. Medium: CPU da grade 0,61-0,66 ms/quadro, sem erro de shader. O teto e os lados das caixas, antes quase pretos, recebem a luz rebatida.
