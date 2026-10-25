# Range Trace

Log opcional de uma sessão de jogo: o que a engine carregou, quanto custou e o que foi de fato desenhado.
Serve para o pente fino de um jogo: achar o que carrega à toa e as cargas no meio do jogo que podem travar.
Código: `source/source/gameengine/Common/CM_Trace.h/.cpp`. Relatório: `tools/debug/relatorio_trace.py`.

## Como usar

Com janela: `tools\debug\Range Trace.lnk` ou
`tools\debug\abrir_trace_launcher.bat [jogo.range]`. A janela escolhe jogo, executável, pasta de saída e
módulos, lembra as escolhas em `%APPDATA%\AnastacioEngine\range_trace_launcher.json` (nada é gravado no
`.range`), roda o jogo e abre o relatório quando ele fecha.
Mostra o ícone do jogo (`icon.png` na pasta do jogo), lista os últimos relatórios (abrir, pasta, apagar)
e tem tema claro e escuro. Usa o Python do sistema (`pythonw`, com tkinter). É ferramenta de
desenvolvimento (padrões do RolimaRacer), por isso não fica no menu do editor.

Pela linha de comando:

```
tools\debug\abrir_trace.bat [jogo.range] [modulos]
```

Abre o jogo no `AnastacioRuntime.exe` (sem argumento abre o RolimaRacer). Jogue o trecho que quer examinar
e feche o jogo normalmente. O `.bat` gera e abre `debug-logs\trace-<data-hora>\relatorio.html`; ao lado fica
`resumo.md`, curto o bastante para colar numa IA.

Sem o `.bat`: `RANGE_TRACE=<pasta>` liga o trace (grava `<pasta>\trace.jsonl`) e
`RANGE_TRACE_MODULES=load,usage` escolhe os módulos (sem a variável, ou `all`, liga todos).
Depois: `python tools/debug/relatorio_trace.py <pasta> [--resumo]`. Funciona também no editor (Play),
cada partida termina com um evento `end` no mesmo arquivo.

Desligado, cada ponto instrumentado custa um `if`. Num jogo exportado nada muda se a variável não existir.

## Módulos

| Módulo | Grava | Peso |
|---|---|---|
| `load` | Por cena convertida (inicial, AddScene, LibLoad): tempo de conversão, texturas e shaders; cada objeto (tipo, camada ativa, malhas), cada malha (triângulos, materiais), cada material (imagens dos nós e slots), objetos deixados de fora pelo Load Mode; objetos On Demand convertidos no meio do jogo | Só no load |
| `usage` | Primeiro frame em que cada objeto passa no culling da câmera ou de uma sombra; cada imagem enviada para a GPU (tamanho, ms, frame) | Um teste de ponteiro por objeto visível por frame |
| `frames` | Uma linha por frame: tempo total e as categorias do profiler acima de 0,05 ms | Uma linha por frame (~60 KB por minuto) |
| `sector` | Câmera num trilho (ver abaixo): posição, progresso na curva e para onde a câmera olha, por frame | Só com `RANGE_TRACE_RAIL` |
| `scripts` | Por frame: ms e chamadas de cada componente Python (pela classe) e controlador Python (pelo script), acima de 0,02 ms | Uma linha por frame com script |
| `runtime` | Memória do processo a cada segundo, cada som iniciado (Sound actuator, Speaker, World Sound) e cada cena adicionada/removida (inclusive replace e async) | Pequeno |
| `work` | Por frame: draw calls, trocas de material e luz e os contadores de `CM_WorkCounters.h` acima de 0. O launcher liga junto `RANGE_AUDIT_TRANSFORMS` (`objetos.txt`: objetos que mais geram trabalho) | Uma linha por frame |
| `threads` | A cada segundo: tempo de parede, núcleos, nº de threads, ms de CPU do processo, da thread principal e das 16 outras threads mais ocupadas (Windows: `GetThreadTimes`; Linux: `/proc/self/task`). Mostra se o jogo está preso na thread principal ou esperando a GPU | Pequeno |

Só no launcher (variáveis próprias, gravadas na pasta do trace e resumidas no relatório): `shaders` liga o
`RANGE_SHADER_LOG` (`shaders.txt`: cada shader, textura e imagem, com frame e ms) e `profile` liga o
`RANGE_PROFILE` (`profile.txt`), o log de ragdoll do RolimaRacer e o log do runtime (`tmp/`). Ver
`docs/engine-profiling.md`.

O relatório mostra `scripts` numa seção própria (média por frame, pior frame, total) e `runtime` na seção
Runtime (memória no início/pico/fim, cenas e sons).

## Trilho de câmera (sector)

`RANGE_TRACE_RAIL=cena;curva;objeto;segundos[;reverse|forward[;início[;esperar]]]`, com o módulo `sector` (o launcher liga `frames`
junto; a opção Velocidade do launcher — Normal, 1,5×, 2× ou 3× — divide os segundos da volta). Quando a cena é convertida, o objeto (normalmente uma câmera) passa a seguir a primeira spline da
curva com velocidade constante em tempo real e vira a câmera ativa. Olha para a média das direções de 4 a
16 m à frente, suavizada (constante de 0,15 s), com o horizonte nivelado. No fim da curva o jogo fecha
sozinho. `reverse` percorre ao contrário. Início, numa curva fechada: `auto` (padrão) começa no ponto mais
perto do objeto com componente `CheckPoint` e `Finish Line` ligado; um nome de objeto começa perto dele;
`none` usa o primeiro ponto da curva. O início é resolvido no primeiro frame do trilho, porque os
CheckPoints costumam vir de instâncias de grupo. Durante o trilho as viewports das outras câmeras são
desligadas (tela dividida).
Esperar: a câmera fica parada no início até `range.logic.globalDict[CHAVE]` ficar verdadeiro e mais N
segundos (`CHAVE`, `N` ou `CHAVE+N`); os frames da espera não entram no mapa (evento `rail_go` marca a
partida). No RolimaRacer, `CONTAGEM_321` (fica True no GO da largada) pula as travadas do load e da contagem.
VSync é desligado durante o trilho para medir o custo real de cada trecho.
Usa a amostragem de curva e o cálculo de caminho do evento Camera Path da Cutscene
(`BL_SampleCutscenePath`, `EvaluateCutscenePath`); o trilho roda em `KX_Scene::UpdateTraceRail`, depois da
física, para valer sobre câmeras do gameplay. No RolimaRacer: `Pista_1;Pista1.009;Camera_debug_track;120;reverse;auto;CONTAGEM_321` (a curva foi desenhada no
sentido contrário ao da corrida; o início `auto` acha a `LinhadeChegada`).
A lógica do jogo continua rodando; para chegar na cena é preciso passar pelo menu normalmente (ou usar o Modo IA).

## Modo IA (RolimaRacer)

O cartão Modo IA do launcher passa `ROLIMA_MODO_IA=<pista>` (padrão `Pista_1`). O `BrainCore` do jogo pula o
menu e monta a corrida como o botão Go Race (SINGLE_PLAYER, 10 pilotos), e o `ia_car.py` larga o Player 1 no
piloto automático; a tecla I continua alternando. Combina com o trilho ou serve para trace sem jogar.

## Formato

Uma linha JSON por evento: `{"t":segundos,"f":frame,"ev":"tipo",...}`. Tipos: `session`, `gpu` (vendor, renderer e versão do OpenGL), `scene_load`,
`load_shaders`, `object`, `mesh`, `material`, `object_left_out`, `convert_object`, `visible`, `image`, `frame`,
`rail_start`, `rail_origin`, `rail_go`, `rail`, `rail_end`, `work`, `scripts`, `memory`, `threads`, `sound`, `scene_add`,
`scene_remove`, `end`.
Objetos são casados por nome entre cenas, porque réplicas e objetos On Demand entram na cena de destino com
o nome do original (os On Demand aparecem primeiro na cena temporária `..ConvertSceneObject..`).

## Como ler o relatório

- **Carregados e nunca desenhados:** objetos com malha que não apareceram nem na câmera nem em sombra.
  Em camada inativa são modelos de Add Object: só contam se o jogo nunca os adicionou na sessão.
  O resultado vale para o que você jogou: um objeto de um trecho que você não visitou aparece aqui.
- **Invisíveis por design:** navmesh e objetos com Visible desligado (colisores, gatilhos) ficam numa lista
  própria, fora do desperdício. Objetos com Static Batch levam a marca `static batch` na coluna camada.
- **Só em sombra:** fora da câmera o tempo todo, mas projetando sombra.
- **Malhas, materiais e imagens à toa:** usados só pelos objetos nunca desenhados.
- **Frames lentos:** acima de 2x a mediana e de 33 ms, sem a espera ociosa (Sleeping), com as três
  categorias que mais pesaram e o que carregou no mesmo frame ou no anterior.
- **Trilho de câmera:** a curva dividida em 40 trechos; faixa e mapa visto de cima coloridos de verde a
  vermelho pelo custo médio. Trecho quente = acima de 125% da mediana dos trechos e 1 ms a mais. Os primeiros
  10 frames do trilho ficam de fora (fim do load). A coluna de categorias diz o que pesa: MainRender e
  Shadows apontam para o que está à vista; Physics e Logic, para o que acontece ali.
- **Cargas durante o jogo:** On Demand, LibLoad/AddScene e imagens enviadas depois dos primeiros 5 frames,
  por ms. As maiores são candidatas a pré-carregar.
