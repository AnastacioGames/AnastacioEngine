# Revisão da frente 8: dados, versioning e leitura/gravação

Data: 2026-10-26. Frente 8 do [levantamento](levantamento-modulos-criticos.md), analisada de baixo
para cima na lista. Objetivo: conferir, linha a linha, se a lógica está correta, se faz sentido e se
há otimização a fazer.

## Segunda revisão por Codex — 2026-10-26

Base: `40762df8`, incluindo os oito commits indicados pelo Claude (`5b07d10c`, `4435cb27`,
`d8b25164`, `1f902be8`, `b8ae30e6`, `2950af80`, `4d21baaa`, `40762df8`). Conferidos os diffs e
os caminhos adjacentes necessários; não é uma segunda leitura integral de todos os arquivos da
frente. Nenhuma correção de produto aplicada nesta revisão. Os registros originais abaixo foram
preservados como histórico da primeira análise.

### Achados por prioridade

| ID | Prioridade | Estado | Local | Resultado |
|---|---|---|---|---|
| CR-01 | P1 | Reproduzido em pasta descartável | `range_web/export.py` — limpeza antes do build | Pastas vizinhas `.tmp-export` e `.old-export` são apagadas sem proteção, inclusive contendo o projeto passado em `protected` |
| CR-02 | P2 | Reproduzido em pasta descartável | `range_web/export.py` — reconhecimento do pacote | Dois diretórios chamados `index.html` e `manifest.json` bastam para autorizar substituição de uma pasta comum |
| CR-03 | P2 | Reproduzido em background | `properties_scene.py` — seleção do Overview | Objeto com seleção bloqueada fica ativo sem ser selecionado; operador devolve sucesso |
| CR-04 | P2 | Confirmado por leitura; sem execução do jogo | `KX_SceneCutscene.cpp` — Player Anim | Além de esconder a exceção, descarta referências possuídas do proxy e do resultado de `Action` |

**CR-01 — proteção não cobre os caminhos que a limpeza remove.**
[export.py](../source/release/scripts/modules/range_web/export.py#L53) valida apenas `dest`, mas
as linhas 56–59 removem recursivamente `dest + '.tmp-export'` e `dest + '.old-export'`.
Reprodução: criar `saida.tmp-export/projeto.range`, escolher `saida` como destino e passar o
projeto em `protected`. A exportação termina e o arquivo protegido desaparece. O mesmo ocorre
com `saida.old-export/projeto.range`. Nos dois testes, o destino inicialmente não existia.
A limpeza já existia antes de `1f902be8`; a nova proteção não fecha esse caminho. Portanto, EXP-02
não pode ser considerado integralmente resolvido. Usar temporários exclusivos e não apagar
pastas preexistentes de identidade desconhecida; conferir todos os caminhos afetados antes de
qualquer remoção. Não remover dados antigos automaticamente para resolver colisões de nome.

**CR-02 — presença dos nomes não comprova um pacote anterior.**
Em [check_destination](../source/release/scripts/modules/range_web/export.py#L35), a condição
consulta nomes em `os.listdir`, sem verificar se são arquivos. Uma pasta com dois subdiretórios
`index.html`/`manifest.json` e `importante.txt` passa; depois da exportação, `importante.txt`
desaparece. É uma lacuna da validação acrescentada em `1f902be8`. Conferir o tipo e a identidade
dos marcadores; o tratamento de links deve ser explícito. Mesmo dois arquivos homônimos são
apenas uma heurística, não prova de que todo o conteúdo pertence ao exportador.

**CR-03 — verificar possibilidade de selecionar antes de limpar a seleção atual.**
[SCENE_OT_overview_select](../source/release/scripts/startup/bl_ui/properties_scene.py#L791)
encontra objetos de toda a cena e primeiro desmarca a seleção atual. Com `ob.hide_select = True`,
o RNA ignora `ob.select = True`, mas a atribuição de objeto ativo continua e o operador retorna
`FINISHED`. Resultado observado: `selected=false`, `active=true`. O painel lista esse objeto sem
indicar restrição. Tratar o caso antes de desmarcar os demais e informar a restrição; não retirar
o bloqueio de seleção silenciosamente. Esse comportamento pertence ao novo commit `40762df8`.

**CR-04 — Player Anim precisa tratar posse além de exceções.**
Em [DispatchCutsceneEvents](../source/source/gameengine/Ketsji/KX_SceneCutscene.cpp#L799),
`GetProxy()` entrega uma referência incrementada; o ramo não a libera. `PyObject_CallMethod`
também entrega uma nova referência quando tem sucesso, e seu retorno é descartado. Uma chamada
que devolve `None` ainda exige decrementar a referência nessa versão de Python. Quando falha,
o erro é apagado em seguida sem diagnóstico. `PyErr_Clear()` não libera esses retornos.
É problema anterior aos commits revisados, relacionado à observação já registrada sobre Player
Anim. Corrigir com posse explícita e diagnóstico da falha; repetir teste de referências por
evento antes de considerar resolvido. Não foi executado o jogo para reproduzir crescimento nesta
rodada; não se afirmou crash nem crescimento de RSS.

### Correções dos achados (Claude, 2026-10-26)

- **CR-01:** temporário e reserva do export anterior agora têm nome exclusivo (`tempfile.mkdtemp`
  ao lado do destino); nenhuma pasta preexistente é apagada. Repetido o teste com
  `saida.tmp-export/projeto.range` e `saida.old-export/projeto.range`: arquivo preservado e
  nenhuma pasta temporária sobrando após dois exports seguidos.
- **CR-02:** marcadores precisam ser arquivos comuns, não diretório nem link. A pasta com
  subdiretórios `index.html`/`manifest.json` agora é recusada.
- **CR-03:** objeto com `hide_select` cancela antes de mexer na seleção e avisa "selection
  disabled"; seleção e ativo atuais ficam intactos (testado em background).
- **CR-04:** libera o proxy e o retorno de `Action()`; em falha, `CM_Error` + `PyErr_Print`.
  Compilado; sem teste de jogo com contagem de referências.
- Suíte Web 136/136 depois das mudanças.

### Mudanças e contratos que passaram na segunda conferência

- **Versioning:** a guarda de `cutscene_settings` preservou a sequência/evento já existentes em
  uma cópia marcada como 1.6.108. O ripple de 0,73 permaneceu em 1.6.111/112/118/119; em 1.6.108 e
  nas cópias 1.6.1001/1002 passou ao padrão 0,4. O remapeamento de `read_global` para 101 foi
  conferido no código. Mover 119/120 não muda dependências dos blocos intermediários: nenhum
  deles escreve `weather_expand_flag`. Não apareceu regressão dessas mudanças nos casos testados.
- **Limite dessa evidência:** as sete cópias usam o DNA atual com metadados de versão alterados
  por offsets obtidos do SDNA, reaproveitando o leitor `io_blend_utils/blend/blendfile.py`.
  Isso testa as condições e a preservação dos dados presentes; não substitui arquivos autênticos
  com layouts antigos, nem comprova compatibilidade integral com toda versão histórica.
- **Cutscene e usuários:** atribuir os três ponteiros do evento acrescentou três usuários;
  duplicar/remover sequência acrescentou/retirou três. `scene.copy()` acrescentou quatro no
  objeto testado (uma base e três referências de evento), e remover a cópia restaurou a contagem.
  Editar o evento copiado não mudou o original. Salvar/reabrir preservou os três ponteiros, uma
  sequência e um evento. O ajuste de `const` em `4435cb27` não muda a semântica da cópia.
- **Export nativo:** `dirs_exist_ok=True` permite atualizar árvores existentes e é compatível
  com o Python embarcado. Não foi identificado novo problema no diff de `d8b25164`; não se
  repetiu aqui a exportação nativa completa testada pelo Claude.
- **Caminhos Web:** `bpy.path.abspath('//')` resolve para a pasta do projeto e foi recusado;
  `//web` foi aceito. Uma junction Windows apontando para a pasta com o projeto também foi
  recusada pelo `realpath`. Isso não valida todas as combinações de symlink, junction e corrida
  de arquivos. Nenhum motivo demonstrado para afrouxar a recusa de pastas comuns não vazias.
- **RNA/UI:** Blend negativo resultou em zero. Add Variation, partindo de Thunder 1 e 3, criou
  2 e depois 4 sem duplicar. Ambos os operadores de componente recusaram índice -1 em background.
- **Joystick:** conferidos merge por maior módulo de eixo, OR de botões, limites do virtual,
  ID inicial -1, transição virtual/físico e sincronização do estado ao vivo. O fluxo básico descrito
  é coerente por leitura; não houve teste com controle físico, hotplug ou navegador nesta rodada.
- **Encerramento:** `StopEngine` chama `m_imgui->Stop()` antes de `DEV_Joystick::Close` e os
  destrutores consultados não exigem Python depois de `exitGamePython`. Zerar `m_eventConsumer`
  após apagar é correto. Isso não torna `ExitEngine` idempotente: o início ainda usa membros
  obrigatórios sem guarda. Não foi executado o player nem validado encerramento gráfico aqui.

### Segunda opinião sobre itens observados sem mudança

- **DAT-05/06/07:** manter a migração histórica nesta rodada. Alterar esses padrões retroativamente
  precisa de exemplos antigos e decisão de compatibilidade; não há justificativa para mudança cega.
- **DAT-08:** referência por nome exige documentar o efeito de rename; trocar para ponteiro de ID
  requer plano de migração e revisão de cópia/link, não apenas mudar um setter.
- **EXP-03:** merece correção funcional: `overwrite_lib` é exposto mas não governa a cópia atual.
  Definir o comportamento do toggle e testar as duas opções; não manter uma promessa inoperante na UI.
- **EXP-04:** não copiar automaticamente um `.cooked` da origem depois de preparar assets é prudente;
  reaproveitamento precisa comprovar validade dos dados/cache transformados.
- **EXP-05:** decidir explicitamente se o relatório é artefato de diagnóstico ou parte do pacote.
  Não foi demonstrada falha de execução por sua presença; menor prioridade que CR-01/02.
- **EXP-06:** leitura integral do player é anterior e sem custo problemático medido; não otimizar
  durante esta revisão de correção.
- **Player Anim:** promover a observação a correção de posse/diagnóstico conforme CR-04.
- **World Sound filtrado:** merece ajuste de usabilidade ou indicação clara da ordem global;
  não foi demonstrado dano aos sons e não exige alterar o formato persistido.
- **NOKEY e Cook/Restart:** não são regressões do diff de plataformas. Conferir o contrato do
  cancelamento do Cook separadamente antes de mudar a precedência da tecla de saída.

### Evidências desta segunda revisão

`artifacts/revisao-cruzada-frente8-20261026/` contém `export_probe.json`, `prepare.json`, os sete
JSONs `v*.json`, `ui_probe.json`, scripts de background, logs e `verification.json` com HEAD/hash.
Suíte Web: 136/136 em subprocesso, saída zero. As aberturas do editor usaram `-b --factory-startup`;
nenhum player, jogo, navegador ou janela foi aberto. Nenhum arquivo do usuário foi salvo ou removido.
Apenas documentação foi alterada por esta revisão; mudanças concorrentes de código foram preservadas.

## Escopo desta rodada

- `blenloader/intern/versioning_range.c`: leitura integral (759 linhas).
- `blenloader/intern/readfile.c`: trechos da engine em `read_global` (versão do arquivo),
  `direct_link_world`/`lib_link_world`, `direct_link_object` (propriedades, logic bricks,
  componentes, partículas GPU), `direct_link_scene`/`lib_link_scene` (cutscene).
- `blenloader/intern/writefile.c`: gravação de World, componentes e cutscene, para comparar com a leitura.
- Elos consultados: `bpath.c` e `world.c` (World Sound), `library_query.c`, `rna_world.c`,
  `rna_scene.c`, `scene.c` e `object_cutscene.c` (contagem de usuários da cutscene), conversor.

Fora desta rodada: o restante do `readfile.c`/`writefile.c` herdado do Blender, o RNA completo, a UI
Python, o exportador e as plataformas. São as próximas etapas da frente.

## Corrigido

| ID | Arquivo | Problema | Correção |
|---|---|---|---|
| DAT-01 | versioning_range.c | Bloco 1.6.112 gravava `rain_ripple = 0.4` de novo, apagando o valor escolhido em arquivos salvos na 1.6.111 | Bloco removido; a 1.6.111 já dá o mesmo padrão |
| DAT-02 | versioning_range.c | 1.6.109 criava `cutscene_settings` sem conferir se já existia (vazamento/perda se existisse) | Só cria quando é nulo |
| DAT-03 | versioning_range.c | Blocos 1.6.119/1.6.120 antes do 1.6.109 | Movidos para depois do 1.6.118 (sem efeito no resultado) |
| DAT-04 | scene.c | `BKE_cutscene_settings_copy` escrevia por um ponteiro declarado `const` | Ponteiro de destino sem `const` |

Validação de DAT-01 a DAT-03: build de editor e player; 12 arquivos de `projects-teste` e
`tools/debug/cenas` abertos em background, todos com `cutscene_settings` presente, exceto
`WEB_TESTE_2D.range`, que já é de versão nova (a migração não roda nele) e é aceito pelo conversor
(`BL_ConvertCutscene` testa nulo).

## Conferido e correto

- **Arquivos da Range original (1.6.1001/1002):** `read_global` reclassifica para 1.6.101, então toda
  a migração da 1.6.102 em diante roda neles. Cobre o caso antigo de `shadowCulling` zerado.
- **Blocos por existência de campo** (`DNA_struct_elem_find`, linhas finais do versioning): forma mais
  segura, funciona para arquivos salvos entre duas versões.
- **Migração do UPBGE:** eventos do mouse, bits do céu e filtro de sombra remapeados corretamente.
- **Sentinelas em `direct_link_world`** (nuvens, sky layers, nuvens volumétricas, névoa, morning boost,
  detail): todos os campos usados como "zero = arquivo antigo" têm mínimo maior que zero no RNA.
- **World Sound:** guarda caminhos, não ponteiros; `bpath.c` e o exportador percorrem esses caminhos;
  cópia, localização e liberação do World duplicam e liberam a lista corretamente; gravação e leitura batem.
- **Componentes:** gravação e leitura batem (propriedades e enum). Campos Object/Scene guardam o nome.
- **Cutscene:** leitura com `newlibadr_us`, `library_query` com `IDWALK_CB_USER`, RNA com
  `PROP_ID_REFCOUNT` e operadores com incremento/decremento ao duplicar/apagar: contagem coerente.

## Observado, sem mudança

| ID | Onde | Observação | Por que ficou |
|---|---|---|---|
| DAT-05 | versioning 1.5.100 / 1.6.100 | Todo material com `ref == 0.8` vira 1.0; IOR 4.0 vira 1.5 | Suposição antiga; mudar agora altera arquivos já migrados |
| DAT-06 | versioning 1.6.100 | Renomeia fonte "Bfont" para "Roboto-Medium" sem checar nome repetido | Risco baixo, só arquivos muito antigos |
| DAT-07 | versioning 1.6.100 | Cor do sensor vem do tema do usuário; sem tema (player) fica preta | Só aparência no editor |
| DAT-08 | componentes | Campos Object/Scene guardam o nome: renomear o objeto quebra a referência | Decisão de design; trocar por ponteiro exige DNA novo |

## Otimização

Nada relevante. O versioning roda uma vez por arquivo aberto e percorre listas pequenas; as ~13
consultas `DNA_struct_elem_find` são baratas perto do resto da leitura.

## Exportador (2ª rodada)

Leitura integral de `addons/game_engine_save_as_runtime.py` (392), `bl_operators/anastacio_export_assets.py`
(234) e `range_web/export.py` (52); chamada do export Web em `properties_web.py`; limpeza do Android.

### Corrigido

| ID | Arquivo | Problema | Resultado |
|---|---|---|---|
| EXP-01 | game_engine_save_as_runtime.py | Exportar de novo na mesma pasta: `copytree` de datafiles (ligado por padrão) e scripts sem `dirs_exist_ok` dava `FileExistsError` depois de já regravar o executável | Reproduzido em background (2ª rodada falhava); corrigido e repetido OK (d8b25164) |
| EXP-02 | range_web/export.py | O export Web troca a pasta de destino inteira. Com destino `//`, raiz da unidade ou pasta com outros arquivos, apagaria tudo, inclusive o projeto | Agora só substitui pasta vazia ou export anterior (`index.html` + `manifest.json`), nunca raiz nem pasta que contenha o `.range`; mensagem traduzida; 3 testes novos, suíte Web 136/136 (1f902be8) |

### Conferido e correto

- `anastacio_export_assets`: cada arquivo do projeto é processado num processo separado, o projeto de
  origem nunca é salvo, bibliotecas fora da pasta são recusadas, handlers de save ficam desligados no
  snapshot e caminhos do World Sound são reescritos para a cópia.
- Export Web: gera numa pasta temporária e só troca no fim; falha preserva o export anterior.
- Android: só grava na pasta de saída; limpa apenas a própria pasta de trabalho no temp.

### Observado, sem mudança

| ID | Observação |
|---|---|
| EXP-03 | Opção "Overwrite 'lib' folder" não faz nada: `CopyPythonLibs` não é chamada por ninguém |
| EXP-04 | Com assets preparados (DDS/áudio), o `.cooked` não vai para o jogo exportado; a primeira carga fica mais lenta. Pode ser intencional, já que os dados mudam |
| EXP-05 | Com assets preparados, `anastacio-export-report.json` vai para a pasta do jogo publicado |
| EXP-06 | O player inteiro é lido para a memória antes de gravar; dezenas de MB, sem impacto prático |

## RNA (3ª rodada)

Varredura de `rna_world.c` e da parte da engine em `rna_scene.c` (rede, cutscene): faixas invertidas,
faixa de UI fora do limite, atualização ausente ou duplicada; leitura das structs de rede e cutscene.

| ID | Onde | Resultado |
|---|---|---|
| RNA-01 | `CutsceneEvent.player_anim_blend` | Aceitava tempo negativo, repassado ao `Action` do script do jogador. Agora mínimo 0, como os outros tempos da cutscene |

Conferido e correto: nenhuma faixa invertida ou fora do limite; no World, só sons e ponteiros ficam
sem atualização (não mudam a imagem); campos da cutscene que dividem o mesmo membro (`template_object`,
`param_int`, `param_float`) pertencem a tipos de evento diferentes; índices ativos fora da lista são
ignorados pelos operadores (`BLI_findlink` devolve nulo).

Observado: o evento Player Anim chama o script com `PyErr_Clear()`, então um erro no `Action` some
sem aviso no console.

## Interface Python (4ª rodada)

Leitura de `properties_cutscene.py`, `properties_world_sound.py`, `properties_game.py` e dos operadores de
componentes em `properties_game_object.py`. Checagem automática no editor: todo campo e operador citado
em `prop`/`operator` nesses painéis (e em `properties_scene.py`, `properties_web.py`,
`properties_video_player.py`) existe de fato.

| ID | Onde | Resultado |
|---|---|---|
| UI-01 | World Sound, Add Variation | Numerava pela contagem: com Thunder 1 e 3, criava outro "Thunder 3", e Use Engine Sounds punha o mesmo arquivo nos dois. Agora usa o primeiro número livre; testado em background (Thunder 1-4 sem repetir) |
| UI-02 | Componentes, Field Tool e Component Button | Só conferiam o limite de cima do índice; negativo pegava o componente do fim. Agora `0 <= index < len` |

Conferido e correto: botões da cutscene e do World Sound validam índice antes de agir; o som automático de
chuva/trovão roda em `save_pre`, `save_post` e `game_pre`, e só altera caminhos, nunca no desenho do painel.

Observado: no World Sound filtrado (Music/Ambient/Effects), subir/descer um módulo troca com o vizinho na
lista inteira, que pode ser de outro tipo e estar escondido; o clique parece não fazer nada.

## Plataformas: entrada, janela e encerramento (5ª rodada)

Leitura de `Device/` (`DEV_EventConsumer`, `DEV_InputDevice`, `DEV_Joystick`, `DEV_JoystickEvents`,
`DEV_JoystickPrivate.h`), do laço e do encerramento em `Launcher/LA_Launcher.cpp` e do ciclo de janela
em `GamePlayer/GPG_Ghost.cpp`.

| ID | Onde | Resultado |
|---|---|---|
| PLT-01 | `LA_Launcher::ExitEngine` | `m_eventConsumer` era apagado sem zerar o ponteiro (todos os outros são zerados). Hoje o Launcher é recriado a cada Restart, então não havia uso; zerado para não virar bug |

Conferido e correto:
- Teclado/mouse: o controle na tela da Web e a tecla física se somam (soltar uma não solta a outra);
  o filtro de foco do Play embutido descarta só os "apertos" com o cursor fora, nunca os "soltos".
- Joystick: o controle virtual ocupa o índice 0 e recebe os limites de eixos e botões; um controle físico
  que chega se junta a ele; ao desconectar, a busca pelo ID não acerta o virtual (ID inicial -1); o estado
  ao vivo corrige eventos perdidos na fila única do SDL na Web.
- Encerramento: `StopEngine` antes de `DEV_Joystick::Close` (ImGui fecha o próprio controle), Python
  por último; SIGTERM do `--server` vira saída limpa; na Web o laço do navegador não executa o código de
  saída do player; janela aberta uma vez e reaproveitada no Restart; GPU e ícones só liberados se criados.

Observado: teclas fora da tabela (F20+, teclas de mídia) entram como `NOKEY` no `std::map`, sem efeito;
no quadro do Cook, a tecla de saída sobrepõe o pedido de Restart do aquecimento de shaders.
