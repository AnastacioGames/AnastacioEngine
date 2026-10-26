# Revisão da frente 8: dados, versioning e leitura/gravação

Data: 2026-10-26. Frente 8 do [levantamento](levantamento-modulos-criticos.md), analisada de baixo
para cima na lista. Objetivo: conferir, linha a linha, se a lógica está correta, se faz sentido e se
há otimização a fazer.

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
