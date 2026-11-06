# Plano: Light Probe Volumes gerados pelo Track Tool

Status: P1, P2 e P3 feitas (2026-11-05); teste na Pista_4 em andamento: 60 fps, luz guardada com 23 de 119 volumes; P4 aberta. Base: [plano-track-tool.md](plano-track-tool.md),
[probe-volume-gi.md](probe-volume-gi.md), [plano-probe-volume-gi.md](plano-probe-volume-gi.md).

## Objetivo

Um operador do Track Tool, **Generate Light Probe Volumes**, cobre só a faixa da pista e das bordas com
uma cadeia de Empties `probe_volume`. Hoje a alternativa é uma caixa gigante: o espaçamento cresce até
caber no limite de sondas (64/128/256) e a luz fica borrada justamente na pista.

## O que o código já faz (conferido)

| Ponto | Estado | Onde |
|---|---|---|
| Vários volumes na cena | **Já aceita.** `m_volumes` é uma lista; cada Empty `probe_volume` vira um `KX_ProbeVolume`. | `KX_TextureRendererManager.h:79`, `.cpp:206` |
| Qual volume um objeto usa | Um só por objeto: o que contém a maior parte da caixa da malha (`FindProbeVolume`), sem mistura entre vizinhos. | `KX_TextureRendererManager.cpp:329` |
| Custo com N volumes | **Problema.** Cada volume acordado captura com o próprio orçamento de faces por quadro (`GetFaceBudget`, no aquecimento ≥ 24). N volumes = N vezes o custo, até todos assentarem. Mudar o sol ou o World acorda todos de uma vez. | `KX_TextureRendererManager.cpp:509-519`, `KX_ProbeVolume.cpp:192` |
| SSGI | Usa o menor peso entre os volumes onde a câmera está. Funciona com cadeia. | `.cpp:551` |
| Rotação do Empty | Ignorada; a grade segue os eixos do mundo. | guia |

Conclusão: **não é preciso escolher "o volume ativo"**. O que falta é um **orçamento de captura
compartilhado**, senão uma pista com 20 caixas custa 20× no início e a cada mudança de sol. A emenda
entre caixas também precisa de cuidado (próxima seção).

## Mínimo em C++ (proposta, a aprovar antes de mexer)

**C1. Orçamento global por distância à câmera.** Em `Render...Volumes`, ordenar os volumes acordados
pela distância da câmera à caixa (`BoxWeight`/distância ao AABB) e repartir um orçamento total de faces
por quadro (o de um volume da qualidade atual; no aquecimento, o mesmo `max(.,24)` total, não por
volume). O mais perto leva primeiro; os outros esperam a vez. Cerca de 30 linhas, sem shader novo, sem
DNA. Uma cena com um volume só fica idêntica (mesma conta).

**C2. Emenda entre caixas (sem mistura no shader).** As caixas geradas se sobrepõem em meio
espaçamento, e o gerador alinha as grades: a origem de cada caixa cai num múltiplo do espaçamento no
mundo. Assim, na faixa de sobreposição, as sondas das duas caixas ficam nos mesmos pontos e capturam
quase a mesma luz; a troca de volume de um bloco de estrada para o próximo não dá degrau visível. Não é
mudança em C++, só regra do gerador. Misturar dois volumes no shader (2º atlas por pixel) fica
**fora**: custa uma unidade de textura a mais, que já é disputada (CSM, sombra colorida, sondas).

**C3 (opcional, só se C2 não bastar no aceite).** Em `FindProbeVolume`, empate de cobertura decide
pelo volume cujo centro está mais perto do centro do objeto, para os blocos não alternarem entre
caixas de quadro a quadro.

## Gerador (Python, bpy 2.79)

Arquivos: núcleo puro em `source/release/scripts/modules/range_track/probes.py` (testável em
background) e operadores/painel em `startup/bl_operators/anastacio_track.py`, seção nova no painel
**Track**. Copiar para `build/bin/2.79/scripts` depois de editar.

Entrada: `frames.sample()` e `layout.band_edges()` (contrato do Track Tool). Largura coberta =
`Edges.outer(i, side, upto)` com `upto` configurável (padrão `BORDER`), mais a margem.

Algoritmo:
1. Percorrer as amostras em `s` e montar o contorno 3D da faixa (borda esquerda e direita, z de cada
   uma).
2. **Trechos**: começa um trecho e vai estendendo enquanto (a) a curvatura acumulada (`turn_deg`)
   fica abaixo de um limite (padrão 15°) e (b) o "desperdício" da caixa alinhada ao mundo (volume da
   caixa ÷ volume da faixa) fica abaixo de um limite (padrão 2,5). Reta ao longo de X ou Y vira uma
   caixa longa; reta diagonal e curva viram caixas menores, porque a caixa não gira.
3. Caixa do trecho = AABB dos pontos das bordas, mais margem lateral, de `z_min - piso` até
   `z_max + altura`. Alinhar a origem e o tamanho a múltiplos do espaçamento e somar meia sonda de
   sobreposição com o vizinho (C2).
4. Contar sondas por caixa como a engine conta (mesma regra de `KX_ProbeVolume`, inclusive o limite da
   qualidade, que aumenta o espaçamento). Se uma caixa passa do limite, ela é partida ao meio em `s`.
5. Somar o total e comparar com o **limite total** configurado.

Configurações (propriedades do traçado, `range_track_probe_*`): espaçamento (m, padrão 6, meio-termo escolhido em 2026-11-05), altura
acima da pista (padrão 4 m), piso abaixo (1 m), margem lateral (2 m), cobrir até a faixa
(`ASPHALT`/`BORDER`/última), qualidade, limite total de sondas (padrão 15000; Pista_4 dá ~13,9 mil em 119 caixas), ângulo e desperdício do
item 2, bounce e freeze repassados aos Empties.

Operadores:
- **Preview Light Probe Volumes**: só calcula e mostra no painel "N caixas, M sondas (limite L)" e
  desenha as caixas no overlay (bgl) sem criar nada. Acima do limite, a conta fica vermelha e o botão
  de gerar sugere o espaçamento que cabe.
- **Generate Light Probe Volumes**: confirma com a conta (`invoke_props_dialog`), apaga os anteriores
  e cria os Empties (Display Cube, `probe_volume` = espaçamento, demais propriedades) num grupo próprio
  `<pista>_ProbeVolumes` e com `range_track_owner` = nome do traçado e `range_track_part` = `PROBES`
  (mesmo padrão de `generate.py`, para regerar sem tocar no que é autoral). Nomes `PV_<pista>_000`.
- **Clear Light Probe Volumes**: apaga só os do grupo/dono.

Volumes feitos à mão continuam valendo e não são apagados. `generate()` ganha a parte `'PROBES'`, fora
do padrão (só quando pedida).

## Etapas

| Etapa | Entrega | Aceite |
|---|---|---|
| **P1** | `probes.py` + Preview (conta e overlay), teste headless em `tools/debug/track_tool/` | Pista_4: caixas cobrem 100% das amostras da faixa (teste por ponto), total abaixo do limite, retas em X/Y viram 1 caixa |
| **P2** | Generate/Clear, grupo, propriedades | Regerar 2× dá os mesmos Empties; volume manual intocado; Scene Doctor sem aviso de limite |
| **P3** | C1 (orçamento global) em C++ | Cena de teste gerada por script (pista reta + curva, 20 volumes): ms de CPU/GPU por quadro com 20 volumes ≈ 1 volume (`RANGE_PROBE_VOLUME_LOG`, rodadas ~10 s); 1 volume igual a hoje |
| **P4** | Aceite visual com janela na Pista_4 | Sem degrau de luz entre blocos (C2); se houver, C3 |

Medições só em cena controlada gerada por script, nunca no jogo. Docs: seção nova em
[probe-volume-gi.md](probe-volume-gi.md) e na interface do [plano-track-tool.md](plano-track-tool.md);
registro no changelog ao fim.

## Medição da P3 (2026-11-05)

Cena `tools/debug/cenas/criar_cena_probe_volume_cadeia.py`, RX 6800M, 60 fps, rodadas de 10 s pelo Performance
Report, 2 rodadas de cada; o World muda aos 5 s. "Sem" = `RANGE_PROBE_VOLUME_OWN_BUDGET=1` (orçamento por volume).

| Medida | 1 vol. sem | 1 vol. com | 20 vol. sem | 20 vol. com |
|---|---|---|---|---|
| Quadros em 10 s | 602 / 596 | 602 / 602 | 458 / 430 | 601 / 601 |
| Quadros acima de 16,7 ms de trabalho | - | - | 63 / 63 | 0 / 0 |
| Trabalho por quadro nos primeiros 3 s | - | - | ~53 ms (~18 fps) | ~2 ms (60 fps) |
| Trabalho por quadro após mudar o World | - | - | ~4,3 ms | ~1,7 ms |

Custo: a luz completa demora mais. Sem o orçamento compartilhado, os 20 volumes terminam o aquecimento em ~4 s; com ele,
seguem capturando 24 faces por quadro depois dos 10 s. O timer de GPU de `render.probes` não serviu nesta GPU: dá 6-10 ms com
1 volume e não acompanha as faces (clock baixo com pouca carga é a hipótese). `RANGE_PROBE_VOLUME_LOG` com 20 volumes
causa um pico de ~25 ms por segundo; não usar o log ao medir tempo de quadro.

## Teste na Pista_4 (2026-11-05)

Corrida real com janela, 119 volumes, RX 6800M, pelo Performance Report. As rodadas não são idênticas, a comparação é aproximada.

| Rodada | Quadro típico | Captura | Picos |
|---|---|---|---|
| Orçamento compartilhado (24 faces) | 25,6 ms | 13,1 ms | 114 |
| + checagem de objetos em uma passada | 21,6 ms | 8,5 ms | 8 |
| + limite de 6 faces e raio de 120 m | 15,0 ms | 2,6 ms | 10 |
| + luz guardada, 10 volumes prontos no início | 9,75 ms | 1,6 ms | 16 |

- A medição da cena de 20 volumes não mostrou dois custos: a checagem de objetos por volume (~140 ms a cada segundo com 119) e o
  aquecimento, que dura a corrida inteira (~83 mil faces por passada). A estimativa de 1 minuto por ciclo estava baixa.
- Captura ao vivo não serve para PC fraco: o relatório estima 46 ms numa GPU 16x mais lenta. Por isso a luz guardada.
- Luz guardada: `RANGE_PROBE_VOLUME_BAKE=1` no editor e corridas normais pelo menu; ~4 a 5 volumes por minuto. Começar direto
  na Pista_4 não funciona para este jogo. Uma sessão única e lenta também foi descartada.

Pendente: encher os outros 96 volumes, correr sem captura, testar `RANGE_WEAK_GPU` (GPU integrada não captura ao vivo; ainda sem
teste), aceite do degrau de luz, incluir o `.probes` no pacote exportado e decidir o clima (a luz guardada é fixa; começar pelo dia claro).

## Riscos

- Curva fechada em diagonal gera muitas caixas pequenas: o limite total e o "desperdício" controlam;
  o Preview mostra antes.
- Pista com desnível grande (rampa) num trecho: a caixa cresce em Z; o critério de desperdício já
  conta a altura.
- Malha de estrada longa (bloco maior que a caixa) usa um volume só: `chunk_length` do sweep deve ser
  menor que o trecho; o Preview avisa quando não for.
- Web: luz por objeto (centro); muitas caixas pequenas não pioram, mas a sobreposição pode trocar o
  volume de um bloco. Conferir na P4.
