# Vehicle System — plano 2 (Chassis/Powertrain/Steering/Wheels)

## Contexto

O plano anterior (`vehicle-system-roadmap.md`, removido do repo — histórico
completo no git log) chegou até a Fase 5 (presets versionados). As Fases 6 (adaptador de assists
Python) e 7 (pneus/transmissão avançados) nunca foram iniciadas e ficaram
como texto aberto/especulativo, gateado em decisões de modelo de pneu
(Pacejka) que o usuário não quer mais perseguir agora.

O usuário trouxe uma especificação concreta de UI (Chassis, Powertrain,
Steering & Brakes, Wheel & Suspension — a seção de Telemetria da spec
original foi descartada por decisão do usuário) baseada em como editores de
veículo arcade tipicamente se estruturam, e pediu para:
1. apagar o que ainda falta do plano antigo (Fases 6/7, pendências obsoletas);
2. mapear essa especificação contra o que já existe (Vehicle Lab, DNA/RNA,
   painel Physics, preset v1) e reaproveitar;
3. planejar só o que realmente falta.

Este documento substitui as Fases 6 e 7 do roadmap antigo. Mantém o princípio
arquitetural já registrado: física/bridge Bullet em C++, feeling arcade
(torque, marchas, RPM, drive type, assists) em Python — evita reabrir a
decisão de modelo de pneu (Pacejka) que o roadmap antigo deixou
propositalmente fora de escopo.

## Inventário — o que já existe (reaproveitar, não recriar)

| Seção da spec do usuário | Já existe | Onde |
|---|---|---|
| Massa do chassi | Sim (campo genérico do Rigid Body, não específico de veículo) | painel Physics padrão |
| Roll Influence | Sim, mas **por roda**, não por chassi | `bWheelSettings.roll_influence`, `custom_pt_physics.py` |
| Raio/Suspensão (stiffness, comp damping, relax damping, travel) | Sim, completo | `bWheelSettings` (DNA) + RNA + `custom_pt_physics.py` |
| Has Steering por roda | Sim | `bWheelSettings.has_steering` |
| Brake Force (uniforme) | Sim (Python, um único valor para todas as rodas) | `vehicle_player_component.py` |
| Max Steering (escalar linear) | Sim, mas não em graus/ângulo | `vehicle_player_component.py` arg "Max Steering" |
| Debug Draw (raycasts, círculo de roda, contato) | Sim, completo (Fase 2 do roadmap antigo) | `KX_VehicleDebugUI.cpp` `RenderDebugDrawTab` |
| Telemetria numérica (tabela de suspensão, ring buffer) | Sim | `RenderSuspensionTab`, `RenderTelemetryTab` |
| Presets versionados + rebuild transacional | Sim (Fase 5) | `KX_VehiclePreset.*`, `vehicle.savePreset/loadPreset/rebuildPreset` |

**Faltam por completo:** Center of Mass offset, Drive Type (FWD/RWD/AWD),
Max Torque + RPM Máximo, Gearbox (tipo + lista de marchas), Speed-Sensitive
Steering, Handbrake Force distinto do freio normal, volante visual.

## Fases novas

### Fase A — Chassis Setup

- **Roll Influence:** manter por roda (é assim que o Bullet realmente aplica);
  não criar campo duplicado a nível de chassi. Documentar essa decisão no
  painel (tooltip) para não reabrir a dúvida depois.
- **Massa:** reaproveitar o campo de massa do Rigid Body existente; não criar
  campo "Vehicle Mass" separado (evita duas fontes de verdade da mesma
  propriedade Bullet).
- **Center of Mass Offset (novo, C++):** Bullet não tem um "setter" simples de
  COM local — a técnica real é envolver a shape de colisão do chassi num
  `btCompoundShape` com um transform local deslocado. Isso toca a criação da
  shape em `CcdPhysicsController`/`CcdPhysicsEnvironment.cpp`, não é cosmético.
  Sub-tarefa própria dentro da Fase A:
  1. Adicionar `float vehicle_com_offset[3]` (vetor XYZ) no objeto, ao lado de
     `is_vehicle`, em DNA + RNA + UI.
  2. No converter (`BL_BlenderDataConversion.cpp`, junto do loop "Create
     native vehicles"), se o offset for não-zero, envolver a shape do chassi
     num compound shape deslocado antes de criar o rigid body.
  3. Testar em cena real: chassi não deve capotar tão facilmente com offset
     negativo em Z.

### Fase B — Steering & Brakes

- **Max Steering Angle em graus:** trocar o argumento "Max Steering" do
  `vehicle_player_component.py` de escalar linear para graus (0-50°),
  convertendo para o valor que `setSteeringValue` espera. Puro Python, sem
  mudança de engine.
- **Speed-Sensitive Steering (novo, Python):** toggle no componente; se
  ativado, reduz o ângulo máximo com base em `vehicle.getCurrentSpeedKmh()`.
  Sem mudança de C++.
- **Handbrake Force distinto (novo):** hoje só existe um freio uniforme em
  todas as rodas. Precisa de metadado por roda para saber quais rodas são
  traseiras (handbrake normalmente só trava traseira). Reaproveita o mesmo
  metadado `has_drive` da Fase C em vez de criar dois metadados separados.
- Freio normal (Brake Force): já existe, sem mudança.
- **Volante visual (novo, DNA/RNA/UI + Python):** objeto filho do chassi que
  gira no próprio eixo Z conforme o valor de esterço atual.
  - **Decidido: campo nativo, não argumento de component.** Novo ponteiro de
    objeto `steering_wheel` no painel Vehicle (DNA/RNA), ao lado de
    `is_vehicle`/`vehicle_wheels`, seguindo o mesmo padrão já usado para as
    rodas. Fica disponível como `object.game.steering_wheel` para qualquer
    script Python, não só para quem usa o `vehicle_player_component`
    específico — consistente com o resto do painel nativo.
  - A rotação em si continua em Python: `vehicle_player_component.py` lê
    `object.game.steering_wheel`, calcula o esterço atual (mesmo valor
    aplicado via `setSteeringValue`) e aplica no eixo Z local do objeto do
    volante (`applyRotation` com eixo local, ou `localOrientation` direto),
    com um fator de multiplicação configurável no componente (o volante gira
    mais que a roda, tipicamente 3x-6x o ângulo real das rodas dianteiras).
    Não precisa de nada novo em C++ além do campo de referência em si — a
    física de esterço não muda.

### Fase C — Powertrain (Python arcade, sem tocar modelo de pneu do Bullet)

Decisão de arquitetura chave: torque/RPM/marchas/drive-type são **feeling
arcade**, calculados em Python, e traduzidos para o `applyEngineForce` já
existente por roda — não se deve mexer no modelo de atrito do
`btRaycastVehicle` (isso é exatamente o que o roadmap antigo isolou como Fase
7, fora de escopo). Isso evita reabrir a decisão de Pacejka/slip.

- **Metadado "roda motriz" (novo, DNA/RNA/UI):** adicionar `has_drive` (bool)
  em `bWheelSettings`, ao lado de `has_steering`, exposto no painel Vehicle
  igual ao steering hoje.
- **Drive Type dropdown (novo, UI apenas):** `FWD` / `RWD` / `AWD` a nível de
  chassi, como atalho de UI que só liga/desliga `has_drive` nas rodas certas.
  Front/rear é inferido pela posição Y da roda relativa ao chassi (mesma
  convenção `forward=Y` já usada no projeto) — sem campo novo de DNA para
  isso.
- **Max Torque + RPM Máximo (novo, DNA/RNA/UI + Python):** decidido, sem
  curva — só dois campos numéricos simples (Torque Máximo, RPM Máximo). Sem
  editor de curva, sem gráfico. Fórmula de queda de torque com RPM (linear ou
  constante até corte) a decidir na implementação, puramente Python.
- **Gearbox (novo, DNA/RNA/UI + Python):**
  - Tipo: dropdown Automático/Manual.
  - Lista de marchas: `bGearRatio` (DNA, float `ratio`) + `ListBase` no
    Object, reaproveitando o mesmo padrão de UIList já usado para
    `vehicle_wheels` (Add/Remove) — inclui marcha à ré (ratio negativo).
  - Lógica em Python: manter RPM simulado, força = torque(RPM) × gearRatio ×
    finalDrive, aplicada via `applyEngineForce` só nas rodas com `has_drive`.
    Troca automática por limiar de RPM; manual por tecla.

### Fase D — Wheel & Suspension

- **Decidido: sem campo Width.** A malha da roda já vem pronta do `.blend`,
  não é procedural — descartado da spec.
- Radius, Stiffness, Comp/Relax Damping, Travel já existem por completo —
  Fase D fica fechada sem trabalho novo.

Telemetria (gráficos, RPM/marcha, barras de compressão) fica **fora deste
plano** — descartada por decisão do usuário. O que já existe no Vehicle Lab
(`RenderSuspensionTab`, `RenderTelemetryTab`, `RenderDebugDrawTab`) continua
como está, sem expansão.

## Ordem de execução sugerida (paradas obrigatórias, como no plano antigo)

1. Fase B (Steering & Brakes) — Python + metadado DNA `has_drive`
   (compartilhado com Fase C).
2. Fase C (Powertrain) — a maior fatia; sub-passos pequenos (`has_drive` →
   drive type UI por inferência Y → torque/RPM simples → gearbox), parando
   para teste em jogo real a cada sub-passo.
3. Fase A (Chassis: COM offset) — última, por ser a única que mexe em criação
   de shape Bullet (compound shape), isolando qualquer regressão de física a
   essa mudança específica.

(Fase D — Wheel & Suspension — está fechada, sem trabalho novo.)

Cada sub-passo C++ segue o processo já documentado em `AGENTS.md`: rebuild via
`vcvars64.bat` + `ninja`, teste na cena real (não screenshot automatizado), e
só então atualizar changelog/roadmap.

## Verificação

- Cada sub-fase: rebuild limpo (`RangeEngine`+`RangeRuntime`), teste manual no
  jogo real (dirigir o carro, alternar drive type, trocar marcha, puxar o
  freio de mão), sem depender de screenshot automatizado.
- Regressão: rodar `VehicleContractTestComponent` (32 PASS/0 SKIP hoje) depois
  de cada mudança em C++ que toque `PHY_IVehicle`/`WrapperVehicle`/converter.
