# Plano: medir antes de otimizar o processamento

Plano de 2026-11-04 que junta o [estudo do Codex](estudo-modernizacao-processamento.md), a
[pesquisa do Claude](pesquisa-processamento-claude.md) e a revisão cruzada das duas. **Só planejamento:**
nenhum código, nenhuma biblioteca nova e nenhuma dependência trocada até o resultado de cada medição
ser aprovado pelo usuário.

## Decisão

- **Prioridade:** medir a animação primeiro. É o maior custo medido fora do Python (400 personagens:
  `Animations` 8,6 ms, `Skinning` 11,5 ms, changelog de 2026-10-29).
- **Bibliotecas:** as trocas grandes ficam adiadas ou rejeitadas (Jolt, Flecs/ECS, ISPC no build,
  enkiTS/oneTBB, ozz como backend dos personagens atuais). O meshoptimizer só entra se a análise offline
  mostrar desperdício.
- **Nenhum candidato tem ganho demonstrado.** Cada etapa abaixo termina numa decisão: seguir para um
  protótipo, ou arquivar com o número que justificou.

## Regras para todas as etapas

- **Toda medição usa cena de teste controlada, nunca o jogo** (RolimaRacer, YoFrankie e outros projetos
  ficam fora). Cada cena é gerada por script em `tools/debug/cenas/` ou `tools/create_perf_*.py`, com o
  mínimo além do que se mede (materiais simples, sem sombra, sem lógica extra), carga fixa e
  determinística, e relatório pelo `tools/tests/perf/perf_probe.py`. Os contadores devem ter min = max entre
  quadros; se variarem, a cena não serve para A/B.
- O gerador recebe a carga por parâmetro (número de objetos, ossos, controladores, substeps), para que
  a mesma cena cubra os vários tamanhos. Cenas novas precisam de aprovação antes de serem criadas.
- Rodadas de ~10 s (`RANGE_PERF_SAMPLE_SEC`), pares alternados A/B na mesma sessão e no mesmo plano de
  energia, tempos em ms. Cada rodada abre o runtime e precisa de autorização do usuário.
- Reaproveitar o que existe: profiler por categoria, `CM_WorkCount` / Range Trace (`work`),
  `tools/debug/sampler/range_sampler.cpp`, `tools/tests/perf/perf_probe.py` e as cenas de
  `tools/create_perf_physics_anim_test.py`.
- Não usar benchmark de outra engine como previsão. Não somar ganhos de cenas diferentes.
- Cada hipótese é julgada pelo próprio custo medido; um resultado negativo numa não elimina outra.
- Instrumentação temporária fica fora do commit ou atrás de variável de ambiente, como `RANGE_ANIM_LOG`.

## Etapa 1: animação e skinning (primeira)

**Pergunta:** onde estão os 8,6 + 11,5 ms dos 400 personagens, e o GPU Skinning estava ativo?

1. Conferir na cena `anim_400c` o modo de deformação da armature e a opção "GPU Skinning" dos materiais.
   O gerador não liga GPU Skinning: o número medido é do skinning na CPU.
2. Rodar a cena como está, com o amostrador, e separar dentro de `Animations`:
   `RNA_path_resolve_property` / `animsys_store_rna_setting`, `evaluate_fcurve`, `GetPose`/`BlendInPose`,
   `BKE_pose_where_is`, preparo das tarefas (`m_animNeedsUpdateCache`, vetores, blocos) e espera no pool.
3. Repetir com GPU Skinning ligado nos materiais (a mesma cena com uma opção a mais). Compara `Skinning`
   e quadro.
4. Repetir o passo 2 numa variante controlada com mais ossos e canais. A cena atual tem 12 ossos, e o
   custo da resolução RNA cresce com o número de canais. Parâmetros novos no gerador: número de ossos
   (12 / 30 / 60, hierarquia em cadeia com ramos, parecida com um rig humano), canais animados por osso
   (só rotação / loc+rot+scale) e uma variante com IK e uma constraint, para separar o custo de
   `BKE_pose_where_is`. O personagem e a action são gerados pelo script, não copiados do jogo.

**Decisões que saem daqui:**

| Se o perfil mostrar | Próximo passo (para aprovar) |
|---|---|
| Resolução RNA ≥ ~20% de `Animations` | Protótipo de amarração das fcurves: guardar o destino resolvido por (action, armature) e escrever direto no canal do osso |
| `evaluate_fcurve` (busca de keyframe) dominante | Cursor de keyframe por fcurve (ideia do `SamplingJob::Context` do ozz), sem biblioteca |
| Preparo das tarefas (mapa, vetores) visível no perfil | Vetores paralelos reaproveitados no lugar do `unordered_map` |
| `BKE_pose_where_is` dominante | Nada de curvas; estudar à parte constraints/IK e o pulo de armatures paradas |
| GPU Skinning derruba `Skinning` | Melhorar a descoberta da opção (aviso no Scene Doctor ou padrão), antes de qualquer SIMD |
| Skinning na CPU continua necessário e pesado | Usar as 4 influências compactas que a conversão já monta para a GPU |

**Contratos de qualquer protótipo:** pose idêntica em quadros fixos (critério de 2026-10-29: 0 pixels
diferentes), deduplicação antes dos workers, `GetDoAnimations()` uma vez por objeto, eventos Python na
thread principal, deformação pendente preservada no catch-up, remoção de objetos durante callbacks,
invalidação ao trocar action, pose ou armature (LibLoad, `replaceMesh`), e curvas mudas reavaliadas a cada
quadro.

## Etapa 2: Web com `-msimd128`

**Pergunta:** a autovetorização do WebAssembly melhora física, animação e quadro, sem COOP/COEP?

1. Gerar dois `.wasm` do mesmo código: com e sem `-msimd128`. `-msse2` para o Bullet fica para depois, porque
   exige mexer em `btScalar.h`.
2. Medir as mesmas cenas controladas `physics_*` e `anim_*` (e as variantes das etapas 1 e 3) exportadas
   para a Web, no Chrome; se possível, também no Safari 16.4+ e no WebView do APK. Seguir o protocolo de
   [web-profile-validation-plan.md](web-profile-validation-plan.md), sem cena de jogo.
3. Anotar o tamanho do `.wasm` e o tempo de abertura fria.

**Decisão:** sem ganho mensurável, arquivar. Com ganho, decidir entre exigir navegador com SIMD ou publicar
dois `.wasm` com detecção. É uma decisão de distribuição, não de código.

**Fora desta etapa:** threads na Web (pthreads, SharedArrayBuffer, COOP/COEP na hospedagem, WebView com
cabeçalhos). Isso vira um projeto próprio, se um dia for pedido.

## Etapa 3: laços da física por controlador

**Pergunta:** quanto custam, por quadro, os laços que visitam todos os controladores ou objetos?

1. Contadores e tempos separados (temporários) para:
   - `SimulationSubtickCallback`: `std::set` inteiro em todo substep;
   - os dois laços de `ProceedDeltaTimeCar` (Use Frame Rate);
   - `SynchronizeActiveMotionStates`: visitados × elegíveis;
   - criação do `TaskPool` da colisão paralela (`BLI_task_parallel_range`, uma vez por substep quando há
     8 pares ou mais).
2. Cenas controladas, geradas por parâmetro (precisam de aprovação; a `physics_<N>o` atual mantém todos
   os corpos acordados e não exercita a hipótese):
   - **mista:** poucos corpos ativos (ex.: 20) e 0 / 1.000 / 5.000 estáticos ou adormecidos, para separar o
     custo que cresce com os objetos parados;
   - **substeps:** a mesma cena com 1 / 5 / 11 substeps (o número visto no jogo foi 11);
   - **veículos:** N veículos raycast sobre chão estático, para cobrir rodas e o caminho Car;
   - cada uma com e sem Use Frame Rate (`ProceedDeltaTime` x `ProceedDeltaTimeCar`).

**Decisão:** se a soma passar de ~0,2 ms por quadro, propor as correções locais:

- percorrer `m_nonStaticRigidBodies` do Bullet (já existe; inclui adormecidos e cinemáticos, então o filtro
  `isActive()` fica);
- manter um vetor só dos controladores com limite de velocidade, atualizado onde o controlador entra e sai
  do mundo;
- no caminho Car, não ressincronizar estáticos.

Se a criação do pool aparecer, avaliar usar o agendador da engine na colisão, o que também reduz de três
para dois os pools de threads. Validação obrigatória: `tools/debug/cenas/criar_cena_determinismo_fisica.py`
com resultado idêntico, veículos e rodas (correção de substeps de `SynchronizeActiveMotionStates`),
Suspend/Restore Dynamics, LibLoad e troca de cena.

## Etapa 4: malhas, análise offline com meshoptimizer

**Pergunta:** os índices atuais desperdiçam trabalho de vértice a ponto de justificar a biblioteca?

1. Gerar por script malhas controladas que representem os casos da engine e exportar os arrays
   convertidos para uma ferramenta de linha de comando fora da engine: low poly chapado com UV por face
   (pintura por paleta), malha suave com poucas costuras, grade regular (referência do ótimo), malha com
   material de Shadow Casting Alpha, e uma com Decimate (ordem de triângulos embaralhada).
2. Medir ACMR/ATVR e overfetch antes e depois de `meshopt_optimizeVertexCache`.
3. Medir quantos vértices o *shadow index buffer* economizaria em dois casos: malhas opacas sem deformação
   (chave só pela posição) e chave com UV, para materiais com Shadow Casting Alpha ou recorte.

**Decisão:** só propor a integração no conversor se houver ganho claro **e** a medida de GPU (RX 6800M e
iGPU) confirmar. Na iGPU, o gargalo medido em 2026-10-25 foi o MSAA.

**Restrições já conhecidas:**

- reordenar na conversão (não só no cooking), versionar a chave do `.cooked` e lembrar que índices de
  desenho diferentes dos de triângulo dobram os índices gravados (`sameIndices`);
- só triângulos inteiros, só malhas estáticas opacas; fora: Wireframe (`gl_VertexID % 3`), transparência,
  soft body, deformadores, malhas lidas pelo `KX_MeshBuilder`;
- vertex fetch remap rejeitado: muda índices vistos pelo Python e por shape keys;
- índice de sombra com chave que cubra o que a passada lê (UV para alpha, ossos para GPU Skinning,
  deslocamento por vento).

## Fila depois das quatro etapas (só com dados)

| Item | Condição para entrar |
|---|---|
| Bullet com `BT_USE_SSE` no Linux | Física relevante no Linux; conferir antes a versão do GCC e o `-O2` do contêiner; chave do BVH cozido precisa incluir o modo SIMD; cena de determinismo |
| Culling de sombras em blocos (dados quentes separados, 4 por vez) | O trecho medido passar de ~0,3 ms; sem ISPC |
| Compressão de malhas para a Web (codec do meshoptimizer) | O tamanho baixado pesar na abertura fria da Web, medida decomposta |
| Atualização TBB 2020 → oneTBB | Só por manutenção das dependências (OpenVDB, OIDN, Embree), não por desempenho do jogo |
| Custo dos scripts Python | Maior custo visto no jogo (~7 ms no RolimaRacer); fora das bibliotecas estudadas, merece plano próprio, também medido em cena controlada (N objetos com scripts típicos) |

## Outras fontes

O mapa das empresas e repositórios de referência, com candidatos fora da CPU (texturas comprimidas na
Web/Android, FSR 1/CAS, normal maps BC5, XeGTAO), está em
[fontes-referencia-tecnologia.md](fontes-referencia-tecnologia.md). Seguem as mesmas regras de medição.

## Rejeitado nesta rodada

Jolt no lugar do Bullet; Flecs/ECS; ISPC no build; troca do agendador por enkiTS/oneTBB; ozz como
backend dos personagens atuais; vertex fetch remap. Motivos na seção 9 da
[pesquisa do Claude](pesquisa-processamento-claude.md) e nas seções 1, 2 e 5 do
[estudo do Codex](estudo-modernizacao-processamento.md).

## Situação

| Etapa | Estado |
|---|---|
| 1. Animação e skinning | Aguardando autorização; variante com mais ossos/IK precisa de aprovação |
| 2. Web `-msimd128` | Aguardando etapa 1 ou autorização em paralelo (não depende dela) |
| 3. Laços da física | Aguardando aprovação das cenas mista, substeps e veículos |
| 4. meshoptimizer offline | Aguardando aprovação das malhas controladas e do download da biblioteca para uma ferramenta à parte; não abre o runtime |
