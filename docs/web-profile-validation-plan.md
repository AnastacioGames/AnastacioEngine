# Range Engine — compatibilidade Web e validação de exportação

Data: 2026-09-12. Estado: **marcos A e B implementados (2026-09-18: `Scene.range_web`/painel Web e núcleo puro `range_web`, sem coleta nem UI de validação); marcos C–G pendentes**.
O runtime Web já existe e foi aceito manualmente (ver [web-deploy.md](web-deploy.md)); referências abaixo à "Etapa 6"/frente Claude são históricas.

Este documento define a criação de jogos na própria Range Engine com compatibilidade Web,
o catálogo inicial de regras e a sequência de implementação. Complementa a
[PoC Python](web-python-poc-plan.md) e a [auditoria de integração](web-integration-audit.md).
A PoC permanece independente. Ter CPython Wasm não significa ter um runtime da engine validado.

## 1. Resultado esperado

Manter **Range Engine** no seletor existente. O usuário cria o mesmo jogo, com as mesmas cenas,
materiais e lógica, e pode exportá-lo para desktop e Web. Dentro das opções de exportação da Range,
oferecer **Verificar compatibilidade Web (experimental)**: mostrar problemas durante a autoria e
oferecer **Validar Web**, **Testar no navegador** e **Exportar Web** conforme os marcos disponíveis.
Não criar outra entrada de engine, nem uma entrada virtual Web no seletor.

Priorizar APIs e recursos compartilhados entre desktop e Web. Quando uma operação precisar de
adaptação de plataforma, implementá-la no backend da engine preservando a API do jogo quando
viável. Diferenças de comportamento devem ser documentadas; lógica específica por plataforma é
último recurso, não a estrutura obrigatória de todo projeto.

Selecionar Web não converte materiais, apaga lógica, reduz texturas nem modifica configurações
desktop automaticamente. Adaptações devem ter descrição, prévia e ação explícita com Undo, ou ser
aplicadas somente à cópia de exportação. O projeto deve poder voltar para desktop sem perder dados.

O perfil inicial visa navegador em computador, WebGL 2 e um runtime único identificado por versão.
WebGL 2 é piso proposto, ainda dependente da integração gráfica. Navegador mobile será uma matriz
de validação posterior; selecionar Web não promete suporte a Android/iOS pelo navegador.
Threads continuam sendo decisão da integração, não um toggle livre que muda apenas o exportador.

## 2. Levantamento do código e consequências

| Área | Evidência local | Consequência para o plano |
|---|---|---|
| Seletor visível | `RENDER_PT_render.draw`, [properties_render.py](../source/release/scripts/startup/bl_ui/properties_render.py), desenha `scene.render.engine` | Preservar o seletor e a entrada Range Engine; compatibilidade Web pertence às opções de exportação. |
| Registro da engine | [external_engine.c](../source/source/blender/render/intern/source/external_engine.c) registra `BLENDER_GAME` com nome Range Engine e flag `RE_GAME` | Não basta acrescentar um nome para obter uma segunda engine funcional. |
| Identidade do jogo | [scene.c](../source/source/blender/blenkernel/intern/scene.c) compara diretamente com `RE_engine_id_BLENDER_GAME`; há comparações também em `view3d_draw.c` e `pipeline.c` | Um identificador novo exigiria auditoria de todos os consumidores C/C++. |
| Painéis | [properties_game.py](../source/release/scripts/startup/bl_ui/properties_game.py) e outros painéis usam `COMPAT_ENGINES = {'BLENDER_GAME'}` | Manter a identidade real evita perder painéis e comportamento de game engine. |
| Preferências export | `RangeArmorExportSettings` e `SCENE_PT_rangearmor_export`, [properties_scene.py](../source/release/scripts/startup/bl_ui/properties_scene.py); registro em [bl_ui/__init__.py](../source/release/scripts/startup/bl_ui/__init__.py) | Já existe precedente para PropertyGroup persistido na Scene sem alterar DNA. |
| Export desktop | Operadores em [wm.py](../source/release/scripts/startup/bl_operators/wm.py); [plano de export presets](export-presets-plan.md) | Reutilizar metadados de produto, mas não encaminhar Web ao pipeline de executáveis desktop. Conferir schema vigente antes de qualquer integração RangeArmor. |
| Build Web | [CMakePresets.json](../source/CMakePresets.json) e [platform_web.cmake](../source/build_files/cmake/platform/platform_web.cmake) | Preset exploratório não é manifesto de capacidades comprovadas. Áudio/vídeo e diversas libs estão desligados. |
| Python e APIs | [KX_PythonInit.cpp](../source/source/gameengine/Ketsji/KX_PythonInit.cpp) expõe `startGame`, `restartGame`, `endGame`, `LibLoad`, `saveGlobalDict`, `loadGlobalDict` | Validar também operações da própria Range, não somente imports da stdlib. |
| Loop, scheduler e renderer | Pontos e evidências na [auditoria](web-integration-audit.md) | São pré-requisitos do runtime. O validador de cena não corrige falta de backend, shaders base ou scheduler serial. |
| Capacidades do fork | [Relatório vigente](../relatorio-melhorias-anastacioengine.md) | Instancing, LOD, batching, GPU skinning, partículas, CSM, resolução dinâmica, veículos e cutscenes já existem; verificar cada um no port, sem reimplementar nem assumir suporte. |

Consulta auxiliar `tools/ask_local.sh` feita para `properties_scene.py`: o modelo pediu o conteúdo
apesar do redirecionamento, sem análise útil. As decisões acima vieram da leitura direta.
O roadmap ainda contém descrições antigas de Web/export presets; usar os documentos específicos
e o código para esta proposta. Não foi feita uma varredura exaustiva de cada símbolo C++.

## 3. Contrato da autoria e dos destinos de exportação

O identificador permanece `BLENDER_GAME`, sem menu intermediário ou substituição do enum.
Windows, Linux e Web são destinos que podem coexistir no mesmo projeto. Ativar a verificação Web
não desmarca os destinos desktop. O botão Exportar Web seleciona o pipeline Web explicitamente;
exportações desktop continuam disponíveis mesmo quando o relatório contém incompatibilidades Web.

Durante a autoria, apresentar aviso junto ao recurso incompatível e no relatório central.
Permitir editar e salvar o projeto; erros Web bloqueiam somente teste/export Web correspondente.
Oferecer configurações iniciais compatíveis como preset explícito, sem reduzir automaticamente
recursos de projetos existentes. Desligar os avisos durante a edição não desliga o preflight do export.

Propriedade proposta: `Scene.range_web`, PropertyGroup separado de `rangearmor_export`:

| Campo | Contrato |
|---|---|
| `schema_version` | Versão das configurações do perfil; migração idempotente. |
| `check_compatibility` | Habilita avisos Web durante autoria; false por padrão em arquivos antigos. Export Web sempre valida. |
| `runtime_id` | Runtime escolhido; sua disponibilidade é verificada no export. |
| `entry_scene`, arquivos adicionais | Entrada e raízes explícitas do pacote, com resolução de referências. |
| `output_directory` | Diretório de destino; nunca usado como raiz de busca de assets. |
| `budgets` | Limiares de aviso de download/memória/frame, configuráveis. |
| `feature_overrides` | Somente adaptações implementadas; diferença em relação ao conteúdo original. |
| `acknowledgements` | ID da regra, alvo, motivo e hash do conteúdo reconhecido; nunca autorizam ignorar erro. |

O perfil Web da cena de entrada governa todo o pacote Web. Cenas secundárias e bibliotecas são
analisadas com esse perfil, mesmo que seus avisos de autoria estejam desligados. Divergências de
runtime/configuração geram aviso; não exportar metade do projeto sob outro runtime.
Bibliotecas vinculadas permanecem somente leitura.

Salvar/reabrir, duplicar cena, trocar engine, Undo/Redo e arquivos sem propriedades devem ser
testados. O teste local pela tecla P continua sendo desktop e deve aparecer como **Prévia desktop**;
somente executar o pacote em navegador constitui **Teste Web**.

## 4. Gravidade, certeza e aplicação

Cada resultado tem dois eixos independentes: gravidade (`ERROR`, `WARNING`, `INFO`) e evidência
(`CONFIRMED`, `POTENTIAL`, `UNVALIDATED`). Nunca transformar uma hipótese de scanner em certeza.

| Situação | Tratamento |
|---|---|
| Incompatibilidade comprovada e necessária no conteúdo exportado | Erro; bloquear Testar/Exportar até corrigir ou selecionar alternativa compatível. |
| Uso possível que análise não consegue resolver | Aviso com caminho e limite da análise; pedir validação prática, sem afirmar falha certa. |
| Capacidade não validada no runtime | Resultado não validado; permite pacote de diagnóstico quando houver runtime executável, mas impede selo de compatibilidade. |
| Recurso desabilitado explicitamente no runtime | Erro se necessário no pacote; não confundir com impossibilidade permanente da plataforma. |
| Orçamento estimado excedido | Aviso; não é limite universal do navegador. |
| Adaptação opcional implementada | Aviso até aceitar adaptação; registrar diferença no relatório do pacote. |

Enquanto não existir runtime integrado validado, **Exportar Web** fica indisponível com motivo
único e direto; **Validar Web** pode produzir relatório provisório. Não gerar dezenas de erros
derivados da mesma falta de runtime. Um pacote de diagnóstico deve ser claramente identificado,
sem permitir ignorar erros confirmados de entrada, empacotamento ou ABI.

Mesmo com zero erros, mostrar “Nenhuma incompatibilidade detectada”, nunca “Jogo garantido”.
Reconhecer aviso não altera sua evidência. Mudança de conteúdo/runtime/regra invalida o reconhecimento.
Durante edição, agrupar e atualizar resultados sem popups repetitivos. No export, rodar análise
completa sobre o snapshot que será efetivamente empacotado; validação em cache não autoriza export.

## 5. Manifesto e arquitetura do validador

Três entradas distintas: **conteúdo do projeto**, **manifesto do runtime** e **sondagem do navegador**.

O manifesto deve acompanhar o runtime e ser gerado a partir do build, complementado por resultados
de testes identificados. Campos mínimos: versão do schema, ID/hash do runtime e artefatos, revisão
da engine, CPython/ABI e revisão, SDK, flags de threads/memória, módulos Python incluídos, codecs,
capacidades por recurso (`disabled`, `unvalidated`, `validated`), requisitos WebGL/extensões,
layout virtual, adapters de save/rede, formato de conteúdo e evidências de testes.
Existência de biblioteca ou flag ON não preenche `validated`. Manifesto ausente, incompatível ou
artefatos divergentes impedem exportar com esse runtime. Mudança no build invalida seus testes.

Organização proposta em módulos novos, nomes finais a ajustar na implementação:

- `bl_ui/properties_web.py`: propriedades e apresentação; sem I/O ou análise no `draw()`.
- `bl_operators/web_export.py`: validar, localizar problema, gerar diagnóstico, testar e exportar.
- `release/scripts/modules/range_web/`: catálogo, coletores `bpy`, resolução de arquivos, análise
  Python, leitura de manifesto, relatório e empacotamento; separar núcleo puro dos adaptadores `bpy`.
- Dados de capacidades junto ao runtime distribuído; não escrever uma lista fixa de suporte na UI.

Cada regra registra ID estável, versão, condição, evidência, fase, dependências, localização,
mensagem, correção e teste positivo/negativo. Resultado inclui cena/objeto/datablock, caminho RNA
ou script/linha, arquivo de origem, capacidade exigida e hash do snapshot. Relatório JSON é a fonte
estruturada; UI e relatório legível usam os mesmos resultados.

Coleta percorre cena de entrada, cenas adicionais, objetos inativos que podem ser ativados/spawnados,
grupos, bibliotecas, materiais, fontes, sons, imagens, Text datablocks, controllers e components.
Não excluir conteúdo só por estar invisível no frame inicial. Resolver dependências transitivas
com conjunto de visitados para ciclos; referências dinâmicas exigem inclusão explícita ou aviso.
Scripts de ferramentas exclusivamente do editor ficam fora quando não há referência do runtime.
O scanner nunca importa nem executa scripts do projeto para descobrir dependências.

## 6. Catálogo inicial de regras

As condições abaixo especificam comportamento futuro. Não são detectores já implementados.
`E` = erro confirmado; `A` = aviso; `N` = não validado, com tratamento da seção 4.
Uma condição em script só recebe E quando sua aplicação ao alvo Web é demonstrável; caso contrário A.

### Conteúdo, arquivos e empacotamento

| ID | Condição e detecção | Resultado / solução |
|---|---|---|
| WEB-PKG-001 | Runtime/manifesto ausente, schema incompatível ou hashes divergentes | E; instalar runtime compatível, sem reutilizar binário desktop. |
| WEB-PKG-002 | Cena de entrada, câmera necessária ou arquivo de jogo ausentes | E; indicar a referência faltante. |
| WEB-PKG-003 | Dependência referenciada ausente, ilegível ou excluída do pacote | E; incluir/substituir asset; mostrar cadeia de referências. |
| WEB-PKG-004 | Caminho Windows/host usado no runtime sem remapeamento | E quando confirmado; remapear para FS virtual. Caminho absoluto usado apenas pelo exportador é permitido. |
| WEB-PKG-005 | Destinos virtuais colidem, escape por `..`, symlink sai das raízes declaradas | E; normalizar e resolver caminhos reais antes de copiar. Não coletar diretórios inteiros por padrão. |
| WEB-PKG-006 | Case de referência não coincide com arquivo; nomes ambíguos entre plataformas | E para referência inválida; padronizar nome/mapa antes do pacote. |
| WEB-PKG-007 | Assets, imports ou `LibLoad` formados dinamicamente | A; declarar conjunto adicional, validar presença e uso no navegador. |
| WEB-PKG-008 | `.pyc` de outra versão/ABI ou extensão `.pyd`/`.dll`/`.so` nativa requerida | E; usar fonte compatível ou módulo Wasm construído para o runtime. Extensão do nome sozinha não prova formato binário. |
| WEB-PKG-009 | `.rasec`/launcher RangeArmor exigido sem leitor correspondente validado no runtime | E; usar formato de conteúdo suportado pelo perfil. Proteção desktop não migra automaticamente. |
| WEB-PKG-010 | Cena externa ou biblioteca usa recurso fora do perfil | Aplicar mesmas regras e apontar arquivo de origem; não alterar biblioteca vinculada. |

### Python, lógica e ciclo de vida

| ID | Condição e detecção | Resultado / solução |
|---|---|---|
| WEB-PY-001 | Import obrigatório não resolvido em scripts/stdlib/módulos do manifesto | E se obrigatório demonstrado; A para import condicional/dinâmico. |
| WEB-PY-002 | Execução de processo (`subprocess`, `os.system`, `fork`, `exec*`) necessária | E; remover do caminho Web ou mover operação para serviço externo. Import isolado gera no máximo A. |
| WEB-PY-003 | Carregamento de DLL/SO do host por `ctypes` ou equivalente | E quando concreto; não banir indiscriminadamente um nome de módulo. |
| WEB-PY-004 | Criação de threads/processos num perfil sem esse suporte | E quando concreto; trabalho por frames/adaptador. Não considerar import de `threading` prova de criação de thread. |
| WEB-PY-005 | Main loop Python personalizado configurado | E enquanto não houver adaptador validado; usar controllers/components por frame. |
| WEB-PY-006 | `sleep`, espera ocupada, I/O bloqueante ou loop suspeito em callback | A na análise estática; medir execução. Chamada confirmada incompatível recebe E. Não proibir todo `while`. |
| WEB-PY-007 | Uso de `bpy`/API exclusiva do editor no jogo standalone | E quando dependência necessária; separar ferramenta de autoria de lógica de jogo. |
| WEB-PY-008 | SyntaxError com a gramática Python do alvo | E; compilar/analisar sem executar usando versão compatível com o runtime. |
| WEB-PY-009 | `eval`, `exec`, importlib dinâmico, alias/rebinding não resolvido | A de cobertura parcial; nunca alegar análise completa desses caminhos. |
| WEB-LIFE-001 | `startGame`, `restartGame`, Game Actuator correspondente | E se recurso desabilitado; N se em validação; habilitar só após teste de limpeza/recriação. |
| WEB-LIFE-002 | `endGame`/quit pressupõe fechar janela do sistema | Exigir adapter que encerre sessão e apresente estado na página; testar cancelamento de callbacks. |
| WEB-LIFE-003 | `LibLoad`, streaming ou troca de cenas | Verificar recurso, arquivos e modo assíncrono no manifesto; E para modo indisponível, N para não validado. |
| WEB-LIFE-004 | Console Python ou debug que depende de scripts externos | Validar pacote e suporte; E no perfil mínimo se ativado e não disponível. |

Análise Python deve usar AST: imports, aliases simples, chamadas e constantes. Tratar guards de
plataforma apenas quando resolvíveis com segurança; não inventar análise de alcance completa.
Um import pode funcionar e uma operação do módulo falhar. A documentação do CPython 3.11 distingue
explicitamente essas situações para processos e sockets. [Disponibilidade no WebAssembly](https://docs.python.org/3.11/library/intro.html#webassembly-platforms).

### Renderização e recursos da engine

| ID | Recurso / verificação | Política inicial |
|---|---|---|
| WEB-GFX-001 | Contexto WebGL exigido e extensões obrigatórias | Sondagem no navegador; E de ambiente se indisponível. Não inferir da GPU desktop. |
| WEB-GFX-002 | Material/shader/filtro e variantes efetivamente geradas | N até teste ES no navegador; falha comprovada de compilação/link é E com log e material. |
| WEB-GFX-003 | Formato de textura/render target, attachments, samples, completude de framebuffer | Comparar com contrato do runtime e limites medidos; E se obrigatório incompatível. |
| WEB-GFX-004 | Textura maior que limite do perfil/dispositivo | E contra limite verificado; oferecer resize explícito na cópia. Tamanho apenas elevado gera aviso de orçamento. |
| WEB-GFX-005 | Wireframe, readback e chamadas GL diretas por `bgl`/shaders Python | Verificar operações suportadas, A se dinâmico; E só para incompatibilidade conhecida requerida. |
| WEB-GFX-006 | CSM, sombras, PBR, transparência, filtros 2D e efeitos multipass | Capacidades independentes N inicialmente; sem desligamento silencioso de sombras ou alteração visual. |
| WEB-GFX-007 | GPU skinning, instancing, batching, LOD, impostores | Validar caminhos separadamente; WebGL 2 não implica incompatibilidade automática. CPU fallback só se implementado/testado. |
| WEB-GFX-008 | Partículas GPU e transform feedback | N, não proibição permanente; validar shader, buffers e limites. |
| WEB-GFX-009 | Resolução dinâmica e queries de tempo GPU | Condicionar à capacidade real; não usar medição CPU como se fosse GPU. Escala fixa é alternativa explícita. |
| WEB-GFX-010 | ImGui, texto/BLF, fontes e menus | Verificar inicialização, shader, fonte e input, inclusive quando menu começa oculto. |
| WEB-SIM-001 | Física Bullet, veículos, constraints, navmesh e cutscenes | N por recurso até testes; não bloquear pela quantidade de objetos. Validar transições/spawn e dependências Python. |
| WEB-SIM-002 | Simulação/modificador depende de componente excluído do build | E se requerido em runtime; bake já convertido em dados suportados pode ser aceito e testado. |

O caminho de OpenGL desktop não se torna WebGL apenas por trocar o seletor; o subset e a emulação
têm limites. A validação de materiais depende da adaptação do renderer descrita na auditoria.
[OpenGL no Emscripten](https://emscripten.org/docs/porting/multimedia_and_graphics/OpenGL-support.html).

### Áudio, vídeo, input, rede e persistência

| ID | Condição | Resultado / solução |
|---|---|---|
| WEB-MEDIA-001 | Sound Actuator/`aud`/áudio necessário com backend desligado | E; habilitar runtime validado ou aceitar export sem esse conteúdo explicitamente. |
| WEB-MEDIA-002 | Codec ou vídeo/VideoTexture/captura indisponível | E se requerido; converter offline para formato suportado ou usar adapter validado. |
| WEB-INPUT-001 | Áudio, fullscreen ou captura do ponteiro exigidos antes de interação | Exigir fluxo de início; teste de permissão/recusa e recuperação no navegador. |
| WEB-INPUT-002 | Teclas reservadas, mouse relativo, gamepad, foco/resize | A e teste; limpar teclas ao perder foco, não depender de prender o usuário no canvas. |
| WEB-INPUT-003 | Perfil mobile futuro sem alternativa touch | A de cobertura de controles; não certificar mobile a partir de teste desktop. |
| WEB-NET-001 | TCP/UDP ou sockets do host presumidos disponíveis | E para operação sem adapter; A para referência incerta. Rede exige API/proxy validado no runtime. |
| WEB-NET-002 | URL/recurso externo e políticas do servidor | Sondar no Testar Web; falha requerida é erro de ambiente, endpoint opcional usa fallback declarado. |
| WEB-SAVE-001 | `saveGlobalDict`/escrita pressupõe persistência em disco local | E se save persistente requerido e adapter ausente; memória temporária não satisfaz persistência. |
| WEB-SAVE-002 | Adapter de save presente | Testar restauração inicial, sincronização assíncrona, recarga, erro/quota e isolamento por jogo; falha não pode ser reportada como save bem-sucedido. |
| WEB-SAVE-003 | Acesso arbitrário a arquivos do usuário | E para pressuposto de acesso direto; importar/exportar arquivos por ação de usuário quando adapter existir. |
| WEB-DEPLOY-001 | Build pthreads sem ambiente de isolamento necessário | E no pré-voo do navegador; explicar configuração de hospedagem. Não ativar fallback serial no mesmo binário. |
| WEB-DEPLOY-002 | `.wasm`/dados ausentes, URL incorreta, MIME ou cache de versões misturadas | E de carregamento; mostrar arquivo e falha, sem spinner infinito. |
| WEB-DEPLOY-003 | Contexto perdido, aba oculta e retomada | Pausa/recuperação ou erro explícito; evitar salto de simulação e callbacks duplicados. |

MEMFS é volátil; IDBFS exige sincronização para persistir. Isso deve ser incorporado ao contrato
de save, não apenas ao nome do diretório. [Filesystem API](https://emscripten.org/docs/api_reference/Filesystem-API.html).
Pthreads requer flags coerentes e hospedagem com isolamento; variantes serial e com threads são
builds separados. [Pthreads](https://emscripten.org/docs/porting/pthreads.html).

### Orçamentos de desempenho

Não fixar “máximo de polígonos”, luzes ou scripts como lei da Web. Registrar tamanho transferido,
tamanho descompactado, heap Wasm, estimativa de texturas/offscreen e medições de frame separadamente.
Heap não representa toda a memória do navegador ou GPU. Estimativas devem informar cobertura.

Defaults propostos apenas para iniciar medições em computador: aviso acima de 50 MiB de download
inicial, 256 MiB de pico de heap medido e alvo de 16,7 ms/frame (60 FPS). Não são garantias nem limites
do navegador. Ajustar com jogos reais; orçamento ainda não medido fica “sem medição”, nunca zero.
Erros duros só decorrem de limite efetivo do runtime/dispositivo ou alocação falha.
Medir CPU/GPU separadamente quando houver suporte; exibir p50/p95, dispositivo e duração do ensaio.

## 7. Fluxo do export e interface de diagnóstico

1. Na Range Engine, ativar verificação Web nas opções de exportação: exibir estado do runtime e compatibilidade.
2. Validar: coletar snapshot, resolver dependências, rodar regras e gerar relatório cancelável.
3. Corrigir: localizar objeto/datablock/script; aplicar correção explícita e invalidar resultados.
4. Testar no navegador: empacotar snapshot em diretório de teste separado, servir por HTTP local,
   executar pré-voo e capturar logs. O servidor pertence à sessão; não encerrar servidores de outras ferramentas.
5. Exportar: validar novamente, gerar pacote em diretório temporário, conferir hashes e concluir
   por substituição controlada do destino. Falha/cancelamento preserva export anterior.

Relatório visível: contagem por gravidade, filtros por cena/recurso, botão Localizar, motivo e
correção. Exemplo: `WEB-PKG-003 — Porta / Controller Abrir: door_logic.py não foi encontrado.
Referência: fase.range → Porta → Abrir. Inclua o arquivo ou corrija o módulo do controller.`

Não escanear tudo a cada redraw/tecla. Primeiro implementar validação manual; depois invalidação
por mudança e processamento incremental no mecanismo suportado pelo editor embarcado. Não acessar
`bpy` em worker arbitrário. Cache usa hashes de conteúdo, runtime e regras, não apenas timestamps.

Saída proposta: página de carregamento, runtime `.js/.wasm`, dados do jogo e stdlib, manifesto do
pacote, relatório JSON e instruções de hospedagem. Layout exato deve consumir o contrato final da
PoC/integração, sem mover os artefatos do Claude agora. Falhas técnicas detalhadas ficam nos logs;
o jogador recebe mensagem simples e opção de tentar novamente quando aplicável.

## 8. Sequência de implementação e critérios de aceite

| Marco | Entrega pequena | Aceite e dependência |
|---|---|---|
| A — Autoria (**feito**; painel conferido pelo usuário: pendente) | PropertyGroup + opção de verificar compatibilidade Web + painel de estado | Salvar/reabrir, Undo/Redo, troca de cena e export desktop preservados; seletor continua Range Engine. Export Web indisponível com motivo. Não exige runtime Web. |
| B — Núcleo (**feito**, núcleo puro; integração `bpy` é do marco C) | Schema do manifesto, resultados e regras de arquivos/Python | Testes puros com casos positivos/negativos e integração `bpy`; nenhuma execução de scripts analisados. |
| C — Coleta (**feito**, sem UI) | Cenas, bibliotecas, controllers/components, assets e referências | Fixtures de dependências transitivas, ciclos e referências dinâmicas; Localizar aponta origem correta. |
| D — Convergência (**aceite manual feito em 2026-09-18**: cubo com material, textura difusa, normal map, Sun e Point, sensor de teclado e atuador Motion rodando no navegador; teste automatizado no navegador feito em 2026-09-20: `verify-capabilities.cjs` modo `keys`, controller Python + teclado no `web-smoke`) | Consumir runtime da Etapa 6, manifesto e pacote mínimo | Cubo da engine + Python controller + A/D no navegador. PoC C→Python isolada não fecha este marco. |
| E — Validação Web (**parcial**: leitura do pré-voo em `preflight.py` e página `?preflight=1` do pacote, exercitada no Chrome com `web-smoke`; calibrada com import inexistente, ValueError e GLSL inválido; o relatório entra no editor pelo botão "Importar pré-voo Web" (JSON manual, preservado ao revalidar) e roda sozinho após o Exportar e no botão "Testar pacote no navegador" via `preflight_run.py` (servidor local + Chrome/Edge headless, página com `&post=1`; testado com navegador falso e com o Chrome real; o fluxo dentro do editor ainda precisa de teste manual)) | Pré-voo, logs, testes de shader e execução | Falhas de contexto/arquivo/import chegam ao relatório; desktop Play identificado como desktop. |
| F — Export (**verificado por testes em 2026-09-20**: 75 testes puros e os 4 testes de integração no motor (`engine_web_export`, `engine_web_cli`, `engine_web_ui`, `engine_collect_bpy`) passam; falta só o teste manual no editor; histórico: botão e núcleo de export; comando de linha feito; módulos e assets do projeto incluídos (subpastas no FS virtual confirmadas no navegador); WEB-PKG-004 também no scanner Python; `import bge` vira WEB-PY-001 com correção para `import Range`; components de template precisam estar na pasta do projeto, senão WEB-PKG-003) | Pacote reproduzível e regras obrigatórias em todo entry point | Export via UI e comando usam mesmo validador; snapshot sem alterações ocultas; falha preserva export anterior. |
| G — Expansão | Áudio, saves, render avançado, transições e dispositivos | Cada capacidade sai de N somente com teste específico no runtime e navegadores declarados.
|  |  | Estado (2026-09-19): áudio com prova por sonda Web Audio (WAV, Audaspace+SDL, `tools/create_web_audio_scene.py`); saves, transições e simulação com `verify-capabilities.cjs`/`verify-save.cjs`; render avançado (`create_web_render_scene.py`) e dispositivos (`create_web_devices_scene.py`) têm pacote de teste manual, aguardando aceite visual. |

A/B/C podem ser desenvolvidos antes do port final, em arquivos próprios, após coordenar ownership.
D depende diretamente da frente Claude e da integração. Não modificar agora o preset, CPython,
renderer, scheduler, build-web ou plano da PoC para implementar UI.
Mudanças C++ posteriores seguem peças pequenas e verificadas e a regra anti-loop do `AGENTS.md`.

## 9. Matriz mínima de testes

- Arquivo desktop antigo sem perfil: abre sem avisos Web ativos; salvar/reabrir mantém comportamento.
- Ativar/desativar verificação Web mantendo Range Engine; painéis corretos, Undo consistente e destinos desktop preservados.
- Erro Web bloqueia export Web e permite continuar editando, salvar, executar e exportar desktop.
- Duas cenas com perfis diferentes; export usa entrada explícita e valida dependências de ambas.
- Controller com script externo ausente e Text interno válido; module controller e component.
- `import subprocess` em ferramenta de editor excluída, guard desktop resolvível, uso Web efetivo
  e import dinâmico: respectivamente fora do pacote, sem erro indevido, erro e aviso de cobertura.
- Caminhos Windows válidos no host remapeados, case incorreto, colisões, ciclos e `../` fora da raiz.
- Módulo nativo de ABI errada; manifesto desatualizado; mudança de asset após validação.
- Recurso desabilitado, não validado e validado: três resultados distintos, sem remoção silenciosa.
- Cena mínima desktop e Web; foco, tecla liberada, resize, aba oculta, encerramento e recarga.
- Shader incompatível: identificar material e log; falha de import: traceback legível.
- Save: recarga restaura estado; erro de sincronização é visível; jogo diferente não lê save alheio.
- Cancelamento/erro de export mantém última saída íntegra; aviso reconhecido invalida ao editar.
- Ensaios reais em Chromium e Firefox de computador; Safari antes de alegar suporte nesse navegador.
  Registrar versões, sistema, GPU, runtime, conteúdo e resultado. Mobile fica em matriz separada.

Testes de UI/save/load precisam ocorrer no editor distribuído, não só em Python externo. Testes
gráficos usam jogo real e confirmação visual conforme `AGENTS.md`; logs automáticos complementam.

## 10. Decisões abertas e limites do levantamento

As regras de classificação e preservação de conteúdo ficam definidas por este plano. Dependem de
provas futuras: escolha final de threads, capacidades gráficas, codecs, formato protegido RangeArmor,
contratos assíncronos de save/rede, orçamento calibrado e lista de navegadores suportados.
Não declarar impossível um recurso apenas porque o preset mínimo o desligou.

Antes de implementar cada família, completar sua tabela com caminhos RNA/API exatos e fixtures.
Este levantamento cobre as famílias de funcionalidade e os pontos de integração encontrados; não
promete detectar todos os comportamentos de Python dinâmico nem todas as variantes de shader.
As fontes oficiais consultadas descrevem a plataforma; o suporte deste fork depende do runtime
fixado e dos seus testes. Nenhum build ou teste de funcionalidade foi executado para este documento.
