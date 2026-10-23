# Vehicle System — plano revisado: Smart Components e RolimaRacer

Revisão: 2026-10-22. Substitui o inventário e as fases A–D anteriores, preservando
o caminho dos links existentes. Auditoria das fontes e inspeção do arquivo do
RolimaRacer, seguida do primeiro lote V1 testado em cena controlada. O jogo
RolimaRacer não foi alterado nem migrado.

## Objetivo e direção proposta

Oferecer controle básico e arcade avançado sobre a física Bullet existente,
com autoria por Smart Components. Reaproveitar os algoritmos do RolimaRacer
antes de criar outro sistema. O básico mantém o caminho curto para montar e
dirigir; o avançado acrescenta assists configuráveis e pode integrar o powertrain
já disponível na engine, após definir sua compatibilidade.

Esses dois níveis são uma proposta, não dois produtos prontos. O RolimaRacer
já possui um controlador arcade avançado próprio. Isso não equivale a um
simulador de pneus/transmissão avançado. Pacejka, slip físico, diferencial e
embreagem só devem entrar após demonstrar uma limitação concreta do modelo atual.

## O que mudou desde o plano anterior

COM offset, rodas motrizes, torque/RPM, câmbio, direção em graus, freio de mão
e volante visual já estão no código. As antigas fases A/B/C deixam de ser
implementação pendente; a fase D já estava encerrada. A validação da sensação
de dirigir continua pendente nos casos sem confirmação específica em jogo real.
Testes pontuais recentes não encerram toda essa avaliação.

Smart Component mantém `Range.types.KX_PythonComponent`, acrescentando campos
`Range.args`, `requires` e classe interna `Editor`. Não exige trocar a base de
execução. O runtime continua independente de `bpy`; imports de editor ficam
nos métodos do `Editor`. O componente de veículo distribuído agora usa 42 campos tipados, preservando
nomes, padrões e cabeçalhos existentes; o `NativeVehicle` do RolimaRacer também
já usa campos tipados.

## Inventário conferido na engine

| Recurso | Estado encontrado |
|---|---|
| Chassi e rodas nativos | DNA/RNA, painel Physics > Vehicle, criação no conversor e `getVehicle()` |
| Chassi | Massa do corpo físico, `vehicle_com_offset` e referência de volante visual |
| Rodas | Raio, suspensão, atrito, roll influence, steering e `has_drive` por roda |
| Direção/freios | Graus, suavização, redução por velocidade e freio de mão distinto |
| Powertrain | Torque em Nm, RPM, câmbio automático/manual, relações e seleção FWD/RWD/AWD na UI |
| Exemplo jogável | Pedais, inércia/RPM, freio motor, joystick, som, balanceamento/empinar de moto |
| Ajuste live | Sincronização do editor no Play e setters Python de torque/RPM/relações, raio e comprimento de suspensão |
| Diagnóstico | Vehicle Lab, debug draw, telemetria e estado/contato por roda |
| Presets | Save/load, bloco opcional `engine` e rebuild explícito |
| Smart Components | Campos tipados, condições, dicas, requisitos, botões/avisos/desenho de editor |

Fontes de referência para a implementação:

- [`vehicle_player_component.py`](../source/release/demos/Vehicle/scripts/vehicle_player_component.py): comportamento do exemplo, incluindo torque/RPM/câmbio.
- [`custom_pt_physics.py`](../source/release/scripts/startup/flowmenu/custom_pt_physics.py): painéis e template embutido criado pelo botão Add Vehicle Component.
- [`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp): acesso ao veículo e getters/setters do motor.
- [`KX_VehicleWrapper.cpp`](../source/source/gameengine/Ketsji/KX_VehicleWrapper.cpp): rodas, estado, setters e presets.
- [`KX_VehiclePreset.cpp`](../source/source/gameengine/Ketsji/KX_VehiclePreset.cpp): contrato efetivo de serialização, incluindo `engine`.
- [`04_smart_component.py`](../source/release/scripts/templates_components/04_smart_component.py) e [`range_component_editor.py`](../source/release/scripts/modules/range_component_editor.py): contrato de campos/hooks de editor.

O changelog de 2026-10-22 registra testes específicos de contato, altura por
suspensão e restauração de torque por preset. São evidências pontuais.
A documentação `.rst` do veículo não cobre toda a superfície Python encontrada;
o contrato de presets também precisa de reconciliação com o código atual.

## Auditoria do RolimaRacer

Fontes externas lidas em `D:/ProjetoRolimaRacer`, sem alterar o jogo.
Os caminhos abaixo são relativos a esse projeto; não são componentes já
distribuídos pela engine. Consultados também `AGENTS.md` e `PROJECT_MAP.md` do jogo.

| Fonte | Implementação encontrada | Reaproveitamento e limite |
|---|---|---|
| `scripts/VehicleSystem/NativeVehicleComponent.py` | `NativeVehicle`: `Range.args`, `Editor.draw_ui`, botões de editor externo e cópia de JSON | Já é Smart Component; adaptar caminhos/regras do jogo |
| Mesmo arquivo | Direção/pedais suaves, LUTs por velocidade, drift automático, mini-turbo, nitro, burnout e contraesterço | Candidatos ao controle avançado; separar pontuação/HUD/teclas |
| Mesmo arquivo | Downforce, controle de tração por torque corretivo, estabilização aérea, inclinação e giro traseiro | Assists arcade opcionais; medir efeitos de escritas em velocidade/orientação |
| `scripts/VehicleSystem/vehicle_fields.py` | Padrões, limites, dicas, seções e condições compartilhados | Base para campos/presets, após generalização |
| `scripts/VehicleSystem/NativeRolimaComponent.py` | Herda `NativeVehicle`, especializa rodas/eixo dianteiro solidário | Preservar especialização; ainda declara `args` legados próprios |
| `scripts/VehicleSystem/VehiclePhysics_common.py` | Pausa, contagem, slow motion/substeps e damping/freio de repouso | Separar políticas de corrida e alterações globais de física |
| `scripts/VehicleSystem/controls.py` e `player_controller.py` | `SetThrottle`, `SetBrake`, `SetSteering`, `SetHandbrake`, input/jogador | Preservar interface ou fornecer adaptador explícito |
| `scripts/VehicleSystem/NetworkVehicleSync.py` | Ownership, replicação/interpolação e visuais remotos | Não executar controle local no veículo remoto |
| `Tools/VehicleConfigEditor.py` e `Vehicle_data/*_config.json` | Editor externo e configuração por grupo | Preservar originais; importação exige mapa de campos/unidades/geometria |

Diferenças e dependências verificadas diretamente:

- `NativeVehicle.start()` usa `getPhysicsId()` + `Range.constraints.createVehicle()`.
  `_setup_wheels()` descobre filhos pela propriedade `Wheel` e chama `addWheel`.
  O exemplo da engine consome `getVehicle()` do conversor. Migração precisa
  impedir criação dupla e preservar ordem/conexões/visuais das rodas.
- `NativeTransmission` guarda `CurrentGear` e `SetGear`; força usa LUT por
  velocidade e `Forca do Motor`. Isso não equivale ao powertrain por torque,
  RPM e relações da engine. Esses valores não podem virar Nm automaticamente.
- O `Editor` informa que JSON do grupo vence os campos da caixa; debug carrega
  configuração no início. Explicitar essa precedência evita campos sem efeito.
- Drift escreve pontuação e `HUD_STUNT_MSG`; pausa usa `PAUSED`, `CONTAGEM_321`
  e modo de jogo. Assists usam `ontheground`, `nitro`, `mini_turbo` e
  `queimar_pneu`. Esses contratos pertencem ao adaptador do jogo.
- Há leitura direta de Espaço no drift além da interface de comandos. O núcleo
  comum deve receber comandos; o adaptador preserva input por jogador.
- Há setters de roda por frame e alterações diretas de velocidades, orientação
  e visibilidade. Distinguir aplicação contínua de configuração que só precisa
  de envio ao mudar; medir antes de alegar ganho.

O sistema antigo 100% Python (`VehicleComponent`, `VehiclePhysics`, `VehicleWheel`,
`VehicleTransmission`) foi removido deliberadamente no jogo. Não o restaurar.

## Primeiro lote executado — V0/V1 (2026-10-22)

Branch: `feat/vehicle-smart-components`. A inspeção pelo editor em background,
sem salvar o jogo, encontrou cinco objetos com componentes de veículo:

| Objeto | Componente | Rodas marcadas | Massa no painel / args / JSON candidato (kg) |
|---|---|---|---|
| `Car.Collider` | NativeRolima | 4 | 100 / 150 / 120 |
| `Car.Collider.carrinho_de_mao` | NativeRolima | 3 | 100 / 150 / 120 |
| `Car.Collider.trampo` | NativeRolima | 4 | 100 / 100 / 110 |
| `Triciclo.Collider` | NativeRolima | 3 | 100 / 150 / 120 |
| `VehicleCollider` | NativeVehicle | 4 | 1700 / 800 / 1700 |

Todos têm `is_vehicle=False`, torque/RPM nativos zero e JSON candidato existente.
Os valores diferem entre painel, args e JSON: por exemplo, o carro tem força
2500 nos args e 7500 no JSON candidato de `Group_Vehicle_Car`. A escolha por grupo
é candidata de editor; confirmar a resolução da instância em runtime antes de
migrar. Nenhuma configuração foi normalizada ou sobrescrita.

Entregue no componente básico:

- 42 campos `Range.args` com dicas, limites e exibição condicional de moto,
  áudio e joystick; nomes/padrões/cabeçalhos legados mantidos para reload.
- `Editor` com diagnóstico de chassi, ativação nativa, rodas/referências,
  raio/comprimento, papéis de direção/tração e controladores conhecidos duplicados;
  avisos de limiares do câmbio e sinal de direção. São avisos, sem bloqueio no runtime.
- Gizmos de conexão/comprimento de suspensão, raio das rodas e COM em coordenadas
  do mundo. Prévia de repouso, não telemetria da suspensão em movimento.
- Demo e template do botão idênticos. A demo estava defasada: foi alinhada aos
  métodos mais completos do template, incluindo `update_args`, releitura das
  teclas e papéis Steering/Drive durante Play. Métodos de runtime do template
  anterior preservados por comparação AST.
- Instalação do painel sincronizada em `build/bin/2.79/scripts/`.

Validação automatizada: 25 checagens de editor, incluindo reload de código
legado com valores alterados, salvar/reabrir, campos condicionais, avisos sem
mutação e geometria de gizmos com chassi rotacionado/COM deslocado. Player
`--server`: quatro rodas em contato, tipos comuns em `args`, import sem `bpy`,
ajuste live de tecla, aceleração, frenagem e telemetria; PASS em modo força
legada e em modo torque 175 Nm com câmbio. Não mede paridade de dirigibilidade.
Detector existente em cena parada com render: os cinco contadores de atualização
ficaram em zero nos segundos 4–6, após estabilizar a suspensão; log com `# fim`.
Verificador estático manteve quatro suspeitos preexistentes em C++; selftest PASS.

Reprodução: `tools/debug/cenas/inspecionar_veiculos.py` e
`tools/debug/cenas/validar_vehicle_smart_component.py`; saídas desta rodada em
`artifacts/vehicle-smart-v1/` (artefatos locais, fora do commit). Para comparar
os métodos com a versão anterior, o validador aceita o arquivo antigo após a
pasta de saída; sem esse argumento, executa as demais verificações.

V0 segue aberta para baseline no jogo real, contrato e confirmação das instâncias.
V1 segue aberta para preparação explícita com Undo/Redo e avaliação com janela.
A extração avançada começou pela curva de direção; drift, boost e demais assists continuam pendentes.

## Segundo lote — início V2 (2026-10-22)

`anastacio_vehicle_arcade.AnastacioVehicleArcade`, distribuído ao lado do básico,
herda seu motor/freios/câmbio e usa o mesmo veículo nativo. O botão **Add Arcade
Component** em Physics > Vehicle cria os dois scripts quando ausentes; arquivos
existentes são preservados. Remova explicitamente o controlador anterior antes
de adicionar outro. O botão recusa controladores conhecidos já presentes.

Primeira extração: LUT de direção do RolimaRacer, 250 entradas inteiras em km/h,
redução zero até 20 km/h e máxima a partir de 120 km/h. Ré usa velocidade absoluta.
`Arcade Steering Reduction` é tipado; `Speed-Sensitive Steering` desliga a curva.
LUT recalculada só quando o parâmetro muda, sem recriação por frame. A suavização
continua sendo a do básico; isso não reproduz toda a direção do jogo original.

Interface externa `set_commands(throttle, steering, brake, handbrake)`:
acelerador/direção entre -1 e 1, freio entre 0 e 1; direção positiva vira à esquerda,
acelerador negativo pede ré. Valores são limitados; NaN/infinito são recusados
sem trocar o comando anterior. Comandos persistem; `clear_commands()` devolve
controle ao teclado/gamepad. Pausa, ownership e atualização desses comandos
pertencem ao adaptador do jogo. Não há novo sistema de input nem migração automática.

Validador `tools/debug/cenas/validar_vehicle_arcade.py`: confere igualdade dos
templates, 43 campos, preservação dos valores, salvar/reabrir e botão real.
Player PASS em força e torque/câmbio: contato das quatro rodas, curva e mudança
live, cache preservado quando outro campo muda, comandos limitados/NaN,
aceleração/frenagem e telemetria. Artefatos em `artifacts/vehicle-arcade-v2/`.
Sem compilação C++ e sem alteração do RolimaRacer. Roll por velocidade, drift,
mini-turbo/nitro, downforce e estabilização ainda não foram extraídos; V2 permanece
aberta, assim como a validação de dirigibilidade pelo usuário.

## Contrato proposto de integração

1. **Um controlador ativo por chassi:** básico ou avançado escolhe um único
   caminho de motor/freio/direção. Assists não podem duplicar as forças.
2. **Física e geometria:** manter Bullet. Em veículos novos, preferir painel
   nativo e `getVehicle()`. Preservar montagem por script nos carros existentes
   até conversão explícita e validada em cópia da cena.
3. **Configuração:** geometria/parâmetros físicos nos dados nativos; assists
   no Smart Component. Importação de JSON é explícita. Adaptador legado mantém
   precedência atual até migrar; não sobrescrever arquivos/valores automaticamente.
4. **Entradas:** acelerador, freio, direção, freio de mão e boost recebidos pelo
   núcleo. Adaptadores para teclado/gamepad, Range Input System por jogador e IA.
5. **Estado/eventos:** contato pode usar `getWheelState(i)["isInContact"]`.
   HUD, pontuação, ragdoll, áudio específico e corrida ficam no jogo; definir
   eventos/estado na V0. Reutilizar telemetria existente quando compatível.
6. **Editor:** `Range.args` e `Editor` para limites, referências, avisos, botões
   e gizmos de rodas/suspensão/COM. Preparação/migração preserva dados e permite
   Undo/Redo; avaliar `requires` antes de alterar física de objeto existente.
7. **Compatibilidade:** preservar `.range`, `Range`, `bge`, nomes de args,
   módulos/classes referenciados e scripts existentes. Novos módulos/classes
   usam `anastacio`/`Anastacio`. Não substituir componentes já gerados em projetos.

## Etapas e critérios de saída

### V0 — Baseline e contrato antes de portar algoritmos

- Selecionar com o usuário carro, rolimã e, se usada, moto/triciclo. Identificar
  componentes realmente anexados e valores efetivos em JSON/args/painel.
  Leitura de scripts não comprova o conteúdo salvo nos `.range`.
- Registrar massa, eixos, escala, ordem/conexões/contato das rodas, input,
  curvas/LUTs, precedência e comportamento de pausa/rede.
- Definir perfis básico/avançado e contrato de comandos/estado/eventos;
  classificar cada assist como reutilizar, adaptar ou manter no jogo.
- Comparar motor por torque da engine e força/LUT do jogo; preservar modo
  legado na transição e evitar dois caminhos de força simultâneos.

Saída: matriz de compatibilidade e baseline em cópia do jogo aprovado pelo
usuário. Esta auditoria inicia V0; V0 ainda não está concluída.

### V1 — Controle básico como Smart Component

- Modernizar exemplo existente preservando nomes/valores de args e comportamento;
  reutilizar o veículo do painel nativo.
- Avisar veículo/rodas ausentes, raios inválidos, referências e controladores
  conflitantes; preparação explícita com Undo/Redo.
- Sincronizar demo e template do botão. Runtime/export sem dependência de
  Tkinter, subprocesso ou `bpy`.

Saída: criar, salvar/reabrir, recarregar e dirigir no editor/player; usuário
confirma paridade com baseline e carros legados permanecem funcionais.

### V2 — Núcleo avançado reutilizável em peças pequenas

- Extrair do RolimaRacer direção/roll por velocidade; depois drift/atrito;
  depois boost; depois downforce/tração/estabilização, uma peça por vez.
- Manter assists opcionais, parâmetros visíveis e integração de pontuação,
  HUD, teclas e estado da corrida por adaptador.
- Integrar powertrain definido na V0 sem duplicar força por roda; recalcular
  LUTs apenas ao mudar parâmetros. Usar APIs atuais antes de propor C++ novo;
  lacunas exigem reprodução pequena que demonstre a necessidade.

Saída por peça: comparação no jogo real, custo por componente medido e cena
parada sem atualizações desnecessárias. Validar antes de avançar para outra
mudança grande/arriscada.

### V3 — Presets e autoria integrada

- Separar preset físico e preset de assists. Reconciliar
  [contrato v1](vehicle-preset-v1.md) com parser/serializer atual, incluindo
  `engine` e o que save/load/rebuild preservam.
- Importar JSONs sobre geometria conhecida com relatório de campos aplicados,
  sem equivalências inventadas, mantendo o original.
- Smart Component edita assists; Vehicle Lab serve à física/diagnóstico.
  Definir quem grava cada valor. Migração do editor externo é decisão posterior
  à paridade, não pré-requisito. Atualizar API `.rst` e exemplos.

Saída: ida/volta sem perda dos campos suportados; arquivo/estrutura inválidos
mantêm veículo e configuração anteriores.

### V4 — Adaptador e validação no RolimaRacer

- Migrar um carro em cópia do projeto, preservando PlayerController, IA, input
  por jogador, replay/fantasma, roda/eixo visual e regras da corrida.
- Validar ownership, pausa online, ausência de forças duplicadas e interpolação.
  Predição de veículo segue fora: depende de trabalho específico de replay
  completo do Bullet, não resolvido por este plano.
- Substituir caminho legado só após confirmação do usuário no jogo real;
  avaliar rolimã e moto/triciclo separadamente e permitir retorno ao anterior.
- Desktop primeiro; Web/APK exigem testes próprios de input, arquivos e export.
  Smart Component sozinho não comprova compatibilidade nessas plataformas.

Saída: dirigibilidade e integrações confirmadas no jogo real pelo usuário.

## Validação e limites desta revisão

Futuras implementações: testes automáticos de contratos/dados/logs e avaliação
manual no jogo real. Cobrir spawn inclinado, COM deslocado, rodas sem colisão,
freio/ré/drift/boost, pausa/retomada, respawn/remoção, IA, tela dividida e ownership.
Ao tocar atualizações/transformações, executar verificador de trabalho repetido,
selftest e medições parado/em movimento. C++ segue build e critérios do `AGENTS.md`.

A revisão inicial do plano foi documental. O primeiro lote posterior alterou
Python e executou editor/player instalados; não exigiu recompilação de C++.
Não houve teste de dirigibilidade no RolimaRacer nem avaliação visual com janela.
O Ollama local estava indisponível; análise feita diretamente nas fontes e índices.
