# Plano: Tutoriais (dentro da engine + vídeo curto)

Data: 2026-11-13. Status: teste piloto, com 1 tutorial.

## Objetivo

Ensinar as frentes novas a quem nunca usou a engine. Cada tutorial é escrito **uma vez**, em um
roteiro, e esse roteiro gera:

1. o **tutorial interativo dentro da engine** (painel com passos que avança sozinho);
2. o **vídeo curto** (1 a 3 min) gravado automaticamente, para o YouTube e o site.

## Piloto

Tema: **"Seu primeiro menu de jogo com a UI Tree"**: menu pronto pelo template **+ Menu**, botão
Jogar renomeado para Start, Setup Game Logic e P. Pause e HUD ficam para outro tutorial.

Roteiro: `source/release/scripts/tutoriais/ui_tree_menu/roteiro.json` (7 passos, com falas).

## Formato do roteiro

`tutoriais/<nome>/roteiro.json`:

```json
{
  "titulo": "Seu primeiro menu com a UI Tree",
  "cena_inicial": "inicio.range",
  "passos": [
    {
      "texto": "Abra o Node Editor e escolha UI Tree.",
      "narracao": "Primeiro, vamos abrir o Node Editor e trocar o tipo para UI Tree.",
      "destaque": "NODE_EDITOR",
      "acao_video": [{"op": "..."}],
      "checagem": "node_editor_ui_tree"
    }
  ]
}
```

- `texto`: uma frase curta, em linguagem de iniciante (vai para o painel e para a legenda do vídeo).
- `acao_video`: o que o script faz para gravar o vídeo (via `tools/testes_engine/controle.py`).
- `checagem`: **nome** de uma checagem implementada no código do painel (não se executa Python vindo
  do JSON); `null` = passo só de explicação, o usuário clica em Next.
- `destaque`: no piloto é só a **área** (ex.: `NODE_EDITOR`), não um botão.

## Etapas

### 1. Roteiro e cena inicial
- Escrever o `roteiro.json` do piloto.
- Gerar `inicio.range` por script (skill cena-de-teste), para que tutorial e vídeo partam da mesma cena.
- **Aceite:** você lê o roteiro e aprova os textos.

### 2. Vídeo automático
- `tools/tutoriais/gravar_video.py`: abre o editor **visível**, liga o Screencast, executa
  `acao_video` passo a passo com o mouse em velocidade humana (pausa de ~1,5 s por passo) e para a gravação.
- Legendas `.srt` geradas a partir dos `texto`; capa e corte final pelo ffmpeg (igual ao trailer).
- **Narração por voz sintética (TTS)**: cada passo tem `narracao` (texto falado, pode ser um pouco
  mais longo que o `texto`). Gera-se um `.wav` por passo; a duração do áudio define quanto tempo o
  passo fica na tela. O ffmpeg mistura a narração por cima do som da engine (que fica baixo).
  Motor padrão: **Piper** (offline, gratuito, voz neural pt-BR); alternativa: voz do Windows (SAPI).
- **Vinheta**: todo vídeo abre com a vinheta do Rolima Racer (clipe fixo com um trecho da música),
  colada no início pelo ffmpeg. O arquivo da vinheta é fornecido pelo usuário.
- Antes do vídeo inteiro, uma **prova curta** (10 s): gravar com `--visivel` e conferir se o
  cursor e os cliques injetados pelo controle aparecem no Screencast.
- Saída: `artifacts/tutoriais/<nome>.mp4` (fora do git).
- **Aceite:** você assiste e aprova ritmo, legenda e duração.

### 3. Painel na engine
- Menu **Help › Tutorials** lista os tutoriais de `scripts/tutoriais/`.
- Painel lateral na 3D View: título, passo atual (n/total), texto e botões Back/Skip/Restart.
- Um timer confere a `checagem` e avança sozinho, com um ✓ verde.
- `destaque`: contorno piscando na região indicada.
- Python puro em `source/release/scripts`, sem C++ no piloto. Sincronizar com `build/bin/2.79/scripts`.
- **Aceite:** teste com janela, você faz o tutorial do zero.

### 4. Publicação
- Página no site (D:\AnastacioDocs) com o vídeo embutido e o texto dos passos.
- O upload no YouTube fica com você (título, descrição e tags eu escrevo).

## Estado (2026-11-13)

- **Vídeo: parado.** O piloto foi gravado (mouse real, tela cheia, UI 1.5, legenda queimada numa
  faixa), mas a voz sintética lê os nomes em inglês da interface como português. Reprovado pelo
  usuário. Se voltar: sem narração (só legenda) ou voz gravada por uma pessoa.
- **Painel na engine: feito, falta aceite com janela.** `startup/range_tutorials.py`, menu
  **About › Tutorials**. Cartão na 3D View (passo n/total, uma frase, Fechar/Voltar/Pular), contorno
  laranja na área alvo, avanço automático pela `checagem`. Roteiro encurtado para 6 passos (saiu o
  passo só de explicação). Testado com o controle invisível: avanço automático e cliques no cartão.
- Revisão do Codex do painel: **aceito** remover o timer na hora, encerrar o modal ao fechar e
  desenhar só na janela do tutorial; **recusado** checagens mais rígidas (sensor, tela Menu, estado
  inicial), que deixariam o tutorial frágil para iniciante.
- **Quadro piscando no local da ação** (pedido do usuário): o passo ganhou `alvo` no roteiro
  (botão pelo texto, `op:`, `prop:` ou `tip:`; ou um nó da UI Tree). Quem sabe onde o botão está é
  a engine: `WindowManager.ui_highlight_button(space_type, region_type, name)` (C, em
  `interface.c`, desenhado no fim de `ED_region_do_draw`). O nó é desenhado pelo Python. Roteiro
  passou a 8 passos, uma ação por passo. Conferido por screenshot em todos os alvos.
- Revisão do Codex do quadro: **aceito** pular botão fora da região, limpar o quadro ao trocar de
  passo, não acelerar com timers de outros operadores (pelo relógio; o 2.79 não expõe
  `event.timer`) e usar `fdrawbox`; **recusado** identificar janela/área do alvo (o tutorial supõe
  um editor de cada tipo).
- Textos só em português; versão em inglês fica para decidir.

## Depois do piloto
Se o piloto for aprovado, entram 4 tutoriais seguindo o mesmo molde: Smart Wizard, Logic Tree,
Text Boxes (diálogos sem código) e World Sound.

## Revisão do Codex (2026-11-13)
- **Aceito:** identificador certo é `RangeUITree`; checagens por nome em vez de Python no JSON;
  piloto reduzido a menu + Start; operador modal com timer para avançar os passos; destaque só da
  área (não há API para achar o retângulo de um botão no 2.79); prova curta de gravação antes do vídeo.
- **Parcial:** vídeo totalmente automático continua sendo a meta, mas depende da prova curta.

## Riscos
- Os cliques do vídeo dependem de coordenadas: dar preferência a `op`/`py` do controle, com clique real só onde for visual.
- `checagem` frágil: para cada passo, testar com o controle que a expressão muda de falso para verdadeiro.
- Tema/escala da UI diferente no PC do usuário: o destaque precisa ser por região, não por pixel.

## Ferramentas para criar tutoriais (2026-11-13, sem commit)

- **Cartão por cima da janela:** `bpy.types.WindowManager.draw_handler_add(func, args)` (C: `WM_draw_overlay_cb_*` em `wm_draw.c`) desenha depois de todas as áreas, em pixels da janela. Funciona sem 3D View e em qualquer layout. O cartão fica embaixo, ou em cima quando o passo acontece na metade de baixo.
- **Contorno de área:** em qualquer editor (`"destaque": "LOGIC_EDITOR"`, `"BAIXO"`).
- **Quadro em qualquer nó:** `"alvo": {"no": ...}` aceita o texto do Button da UI Tree, o nome ou o label.
- **Checagens no JSON:** `{"area"|"modo"|"objeto"|"ativo"|"expr"}`. Ver o docstring de `range_tutorials.py`.
- **Gravar:** Help › Tutorials › Record Tutorial. Cada clique vira um passo com o alvo preenchido, e o menu escolhido vai junto. Stop Recording salva `tutoriais/gravado_<data>/roteiro.json`; depois é só reescrever os textos e pôr as checagens.
  - Do lado do C: anel de 16 cliques (`UI_last_click_*`), lido por `WindowManager.ui_click_count()` e `ui_last_click(index)`.
- **Revisão do Codex:** aceitos a remoção adiada no laço de overlay, o estado GL restaurado e o consumo dos cliques no Stop; parcial o `eval` (vale a confiança de um script); recusadas as refs Python na saída.

## Rodada 3 (2026-11-13, sem commit)

- **Organização:** `"categoria"` no roteiro gera os submenus. A gravação preenche com o editor que mais recebeu cliques. Um tutorial se apaga, recomeça, edita ou exporta pelo clique direito.
- **Cena inicial:** a gravação salva `inicio.range`. Ao começar do passo 0, o tutorial abre uma cópia temporária dela (pergunta antes, se há mudanças não salvas) e começa sozinho no `load_post`.
- **Editor de passos:** 3D View › Tool Shelf › aba Tutorial. Edita título, categoria, texto e dica; move e apaga passos; ▶ toca a partir de um passo.
- **Progresso:** fica em CONFIG/`range_tutorials.json`. O menu mostra ✓ nos concluídos e (n/total) nos começados, e continua de onde o usuário parou.
- **Dica:** depois de 20 s parado no passo, mostra `"dica"` em amarelo, e o quadro pisca mais rápido.
- **Busca:** Search Tutorials… no topo do menu.
- **Idiomas:** `titulo`, `texto` e `dica` aceitam `{"pt":..,"en":..,"es":..}`, conforme o idioma da interface (sem o idioma, vale `en`).
- **Exportar e importar .zip:** a importação recusa caminhos absolutos, `.`, `..` e nomes repetidos, e nunca sobrescreve tutorial existente.
- **Revisão do Codex:** cinco pontos, todos aceitos (enum da busca estável, zip duplicado, `_pendente` limpo, Restart sem zerar antes da confirmação, salvar fecha a reprodução).

## Tutorial da barra do Mind Map (2026-11-14, falta aceite com janela)

- `tutoriais/mind_map_barra/`: 11 passos, um por botão da barra (Map, Idea, Look, Marks, Link, Find), pt e en.
- Alvos `op:MINDMAP_OT_*` na região `WINDOW`; checagens `expr` sobre o texto `.mm` do mapa aberto. Sem `inicio.range`.

## Tutorial dos nós de HUD (2026-11-14, falta aceite com janela)

- `tutoriais/ui_tree_hud/`: 16 passos a partir do template + HUD (Progress Bar, Label, Gauge, Button A, Dialogue
  Box), um Label novo com `{pontos}`, Setup Game Logic e P. Supõe uma UI Tree nova, pelos nomes dos nós.

## Tutoriais básicos (2026-11-14, falta aceite com janela)

- Basics: `basico_interface`, `basico_transformar`, `basico_primeiro_jogo` (primeiro jogo e física juntos).
- Logic Bricks: `logica_andar`. Export: `exportar_desktop` (aba Export Game › Export), `exportar_web`.
- Intermediários: ver as seções seguintes.

## Tutoriais 7 a 10 (2026-11-14, falta aceite com janela)

- `smart_wizard_girador` (Components), `texto_caixa_dialogo` (Text), `som_world_sound` (Sound),
  `logica_arvore_andar` (Logic Tree).
- Pause na UI Tree não virou tutorial próprio: é o botão II do template + HUD, já no tutorial do HUD.
- Pontos para o aceite: o painel Component Manager começa fechado (o quadro só aparece depois de aberto); o
  World Sound supõe que a cena tem World; o passo do texto pede sair da edição com Tab antes de conferir.

## Tutoriais 11 a 14 (2026-11-14, falta aceite com janela)

- `cutscene_abertura` (Cutscene), `minimap_radar` (Node Editor/UI Tree), `material_atlas_paleta` e
  `performance_medir` (Optimization).
- Pontos para o aceite: o destaque dentro do popover Performance; o + de eventos do Cutscene criando
  SPAWN_OBJECT antes da troca de Type; o Minimap pede o .range salvo para tirar a foto do mapa.
- Rec Play, Track Tool e Vehicle Lab viraram os tutoriais 15 a 17 (seção seguinte). Camera FX não foi achado
  nos scripts com esse nome; fica para quando o usuário apontar o recurso.

## Tutoriais 15 a 17 (2026-11-14, falta aceite com janela)

- `rec_play_gravar` (Animation): aba Render › System, painel Motion Recording, Record "Cube", Max Duration,
  Rec Play, Watch, Add to Cutscene, P.
- `track_pista` (Track): Add › Curve › Track, aba Track do painel N, Road, Live, editar a curva, Generate All.
- `veiculo_carro` (Vehicle): chão, chassi Rigid Body, aba Vehicle (Enabled), 4 cilindros No Collision nos
  cantos, Add Wheel ×4, objetos das rodas, Steering na frente, AWD, Add Vehicle Component, P, Debug Mode e a
  caixa Vehicle Lab na janela Options do jogo.
- Pontos para o aceite: o painel Motion Recording fica no meio dos painéis de System (rolar); o Live do Track é
  conferido pelo estado do módulo `bl_operators.anastacio_track`; o carro com as medidas do tutorial (rodas
  em X ±1,2, Y ±1, Z -0,8, chão em Z -2) precisa andar sem capotar; a vista não segue o carro.

## Três idiomas (2026-11-14)

- Os tutoriais têm pt, en e es em `titulo`, `resumo`, `abertura`, `encerramento`, `texto` e `dica`.
- Regra de escrita: nomes de botões, abas, menus, campos e teclas ficam como na engine (inglês), em todos os
  idiomas: "clique em Next", "Enter, Space". Rótulos que a engine mostra em português (Jogar, Girador,
  Velocidade) ficam como estão.
- O cartão do tutorial usa Close, Back, Next, Skip e Finish; o rótulo "Dica:"/"Tip:"/"Consejo:" e o
  "feito!" seguem o idioma da interface.
