# Plano: destruição nativa (pré-fraturada) e explosões

Estado: **v1 pronta (F0 a F5)**, falta o usuário jogar a demo e ajustar a sensação (2026-09-29).
Demo: [source/release/demos/Destruction/](../source/release/demos/Destruction/README.txt).

Decisões do usuário (2026-09-29):

- as opções ficam na **aba Physics**;
- **dois painéis separados**, **Destruction** (quebra em pedaços) e **Explosive** (explode), como no protótipo;
- o **logic brick de explosão fica para depois da v1**; a v1 tem os painéis e a API Python.

## Objetivo

Levar para C++ o protótipo Python validado em `tools/ADD na engine anastacioEngine/`
(`destruction.py` + `First_Person_destruction.range`, pasta fora do git):

- objeto **destrutível** que, ao receber impacto forte, é trocado por pedaços pré-fraturados (Cell Fracture);
- **explosão** como impulso radial com queda pela distância, oclusão por geometria estática e quebra dos
  destrutíveis dentro do raio;
- objeto **explosivo** (barril, granada) com pavio, impacto e reação em cadeia;
- limite global e tempo de vida dos detritos.

Fora do escopo desta versão: corte em tempo real por plano (nível 3), fratura Voronoi em tempo de jogo, logic
brick próprio (a API Python e o painel cobrem a v1) e variações de fratura sorteadas (fica para depois da F4).

## O que o protótipo já ensinou

- **O `appliedImpulse` dos pontos de contato é a medida certa para quebrar**: ele independe do frame e já vem
  somado pelo Bullet (`CcdCollData::GetAppliedImpulse`,
  [CcdPhysicsEnvironment.cpp](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp)).
- **Não usar a instância de Dupli Group para criar os pedaços.** Encerrar o Empty encerra os membros
  (`DelayedRemoveObject` chama `RemoveDupliGroup`,
  [KX_Scene.cpp:1312](../source/source/gameengine/Ketsji/KX_Scene.cpp#L1312)), e membros fora da layer do grupo
  são ignorados ([KX_Scene.cpp:1057](../source/source/gameengine/Ketsji/KX_Scene.cpp#L1057)). A versão nativa
  replica cada objeto do grupo diretamente, com a transformação calculada por ela.
- **Faça a quebra fora do callback de colisão**: registre o impacto e quebre no passo seguinte.
- **Detone a reação em cadeia no frame seguinte**, e não recursivamente dentro da mesma explosão.
- Valores que funcionaram: quebra da caixa com 12, parede com 20, barril com 12; explosão com raio 5 e força 30–35.

## Onde ficam as opções (editor)

### Aba Physics > painéis "Destruction" e "Explosive"

Os dois ficam abaixo de "Create Obstacle" (`PHYSICS_PT_game_destruction` e `PHYSICS_PT_game_explosive` em
[properties_game.py](../source/release/scripts/startup/bl_ui/properties_game.py)), com "Enabled" na primeira
linha, como o de obstáculo. Destruction aparece para Static, Dynamic e Rigid Body; Explosive também para
No Collision (só pavio).

```
Destruction                                  Explosive
[x] Enabled                                  [x] Enabled
Fragments: [Crate_fragments ▼] (Group)       Radius: 5.0        Up Bias: 0.3
[ Generate Fragments... ]      (F1)          Force: 30.0        [x] Occlusion
Break Impulse: 10.0  Burst Speed: 2.0        Fuse: 0.0 s  (0 = sem pavio)
[x] Break on Collision [x] Inherit Velocity  [x] Explode on Impact   Impact Impulse: 12.0
Debris Lifetime: 10.0 s (0 = permanente)     [x] Chain Reaction
                                             Effect: [Explosion_fx ▼]  Life: 0.25 s
```

- O painel Destruction avisa quando o grupo está vazio, quando os pedaços não estão na cena ou estão numa
  layer visível, e quando o próprio objeto está no grupo. O Explosive avisa se o Effect está numa layer visível.
- **Generate Fragments...** (F1, `object.destruction_fragments_generate` em `bl_operators/object.py`):
  - o diálogo pede o número de pedaços, a semente, o material interno e a layer (padrão 20);
  - roda o Cell Fracture sobre a malha do objeto, com os modificadores aplicados, no espaço local e sem a
    transformação do objeto;
  - sorteia os pontos de corte dentro da malha, para que barris e esferas também deem o número pedido de
    pedaços, e a mesma semente dá os mesmos pedaços;
  - põe os pedaços do grupo `<nome>_fragments` na layer escolhida, com `dupli_offset` 0, para o runtime usar
    `obj.world * piece.world`;
  - dá aos pedaços Rigid Body e Convex Hull, a massa do objeto dividida pelo volume de cada um e o collision
    group e mask do objeto;
  - liga a Destruction e preenche `Fragments`;
  - gerar de novo apaga os pedaços antigos do grupo e reaproveita o grupo.
- **Os dois juntos:** quebrar dispara a explosão e explodir dispara a quebra. Os pedaços nascem e já recebem o
  impulso da explosão, e o objeto é removido uma vez só. Um barril é só Explosive (some e explode); com
  Destruction também, ele deixa pedaços.
- **Fuse** conta a partir do momento em que o objeto entra no jogo, então funciona para uma granada criada com
  Add Object.

### Aba Scene > painel de física do jogo

- **Max Debris** (padrão 150): quantos pedaços podem existir ao mesmo tempo. Ao passar do limite, os mais
  antigos somem primeiro. Isso importa principalmente para Web e Android.

## Dados (DNA / RNA)

O padrão segue o da Reverb Area (`RangeReverbAreaSettings` + bit em `gameflag2`):

- `DNA_object_types.h`, as duas structs embutidas no fim de `Object`:
  - `RangeDestructionSettings { Group *fragments; float break_impulse, burst_speed, debris_lifetime; int flags; }`
    (24 bytes), com `flags` `DESTRUCTION_BREAK_ON_COLLISION` e `DESTRUCTION_INHERIT_VELOCITY`;
  - `RangeExplosiveSettings { Object *effect; float radius, force, up_bias, fuse, impact_impulse, effect_life;
    int flags, pad; }` (40 bytes), com `flags` `EXPLOSIVE_OCCLUSION`, `EXPLOSIVE_ON_IMPACT` e
    `EXPLOSIVE_CHAIN_REACTION`;
  - `gameflag2`: `OB_DESTRUCTIBLE = 1 << 14` e `OB_EXPLOSIVE = 1 << 15`.
- `DNA_scene_types.h` (`GameData`): `short max_debris` no lugar do `pad2` livre. Cena nova recebe 150
  (`scene.c`); arquivo antigo recebe 150 pelo `DNA_struct_elem_find` em `versioning_range.c`.
- **Valores padrão** no primeiro enable, pelas funções `set` da RNA (`rna_GameObjectSettings_use_destruction_set`
  e `..._use_explosive_set`), no mesmo esquema do `is_vehicle`. Funciona também quando o Python liga a opção.
  Arquivos antigos têm as structs zeradas, e não é preciso versioning.
- RNA: `ob.game.use_destruction`, `ob.game.destruction.*`, `ob.game.use_explosive`, `ob.game.explosive.*` e
  `scene.game_settings.max_debris`.
- Ponteiros de ID (`fragments` e `effect`), contados como usuários pela RNA, como o `dup_group`:
  - `lib_link` (`newlibadr_us`) e `expand_doit` em `readfile.c`, perto de `vehicle_steering_wheel`;
  - `BKE_library_foreach_ID_link` em `library_query.c` com `IDWALK_CB_USER`, o que também cobre a cópia do
    objeto e a remoção do Group ou Object apontado. O `vehicle_steering_wheel` e o `vehicle_wheels` **não**
    aparecem lá: é um bug separado, a tratar à parte.
- "Copy Game Physics" (`object_edit.c`) copia as duas structs, ajustando a contagem de usuários.

## Runtime (C++)

### Arquivos novos

`Ketsji/KX_DestructionManager.{h,cpp}`, um por `KX_Scene`. Ele cuida de:

- **Registro:** o conversor ([BL_BlenderDataConversion.cpp:1358](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp#L1358),
  onde a reverb area é registrada) e o `AddReplicaObject` ([KX_Scene.cpp:881](../source/source/gameengine/Ketsji/KX_Scene.cpp#L881))
  registram objetos com `OB_DESTRUCTIBLE` ou `OB_EXPLOSIVE` e chamam `RequestCollisionCallback` no controlador
  físico (quando Break on Collision ou Explode on Impact está ligado), para que as colisões dele cheguem ao
  gerenciador. O pavio conta a partir do registro.
- **Impacto:** em `KX_CollisionEventManager::NextFrame` ([KX_CollisionEventManager.cpp:213](../source/source/gameengine/Ketsji/KX_CollisionEventManager.cpp#L213)),
  ao lado dos callbacks Python, se o objeto é destrutível, o impulso do par é somado com
  `colldata->GetAppliedImpulse` e reportado. Se passar de `break_impulse`, entra na fila, com o ponto de contato como origem.
- **`Shatter(obj, origin, burst)`:**
  - para cada objeto do grupo (convertido como inativo), `AddReplicaObject(piece, obj, lifespan)`, com o
    lifespan convertido de segundos para frames lógicos;
  - transformação do pedaço: `obj.world * (piece.world - group.dupli_offset)`;
  - velocidade herdada, impulso de burst, explosão (se o objeto também é Explosive), callbacks `onBreak`;
  - por último, `DelayedRemoveObject(obj)`.
- **`Explode(center, radius, force, upBias, occlusion, mask, source)`:**
  - consulta de esfera nova na física (ver abaixo), filtrada pela distância real;
  - oclusão com `RayTest`: só geometria estática bloqueia;
  - destrutíveis acima do limite quebram, e os pedaços recebem o mesmo campo de impulso;
  - explosivos com Chain Reaction acima de `impact_impulse` vão para a fila do frame seguinte;
  - cria o Effect com o `effect_life` convertido para frames lógicos.
- **Detritos:** fila FIFO com o limite `max_debris`; passando dele, os pedaços mais antigos são removidos na
  hora. Pedaços removidos por outro caminho (tempo de vida, `endObject()`) saem da fila no
  `UnregisterObject`. O tempo de vida usa o lifespan que o `AddReplicaObject` já suporta, sem timer próprio.
- **Impulso nos pedaços:** o impulso da explosão no ponto de cada pedaço é multiplicado pela fração de massa
  dele (massa do pedaço / soma das massas dos pedaços). Assim os pedaços saem com a velocidade que o objeto
  inteiro teria.
- **Ordem no frame:** a fila de quebras é processada depois da lógica e antes da remoção dos objetos
  (`RemoveEuthanasyObjects`).

### Física

- `PHY_IPhysicsEnvironment::SphereQuery(center, radius, std::vector<PHY_IPhysicsController *> &out)`. O
  `mask` de `scene.explode()` é aplicado depois, no `KX_DestructionManager`, contra o collision group.
- Na implementação Bullet, `CcdPhysicsEnvironment` usa `broadphase->aabbTest` com a AABB da esfera e filtra
  pela distância até a caixa de cada objeto (sensores ficam de fora). É barato e funciona igual no build Web
  (Emscripten).

### API Python

| API | Descrição |
|---|---|
| `KX_GameObject.shatter(origin=None, burst=None)` | Quebra agora. Devolve a lista de pedaços |
| `KX_GameObject.detonate()` | Explode agora. Devolve `False` se não for explosivo ou já tiver explodido |
| `KX_GameObject.isDestructible`, `isExplosive` | Somente leitura. Refletem o painel, também em objetos da layer inativa |
| `KX_GameObject.breakImpulse` | Leitura e escrita |
| `KX_GameObject.fuse` | Tempo restante do pavio. Leitura e escrita |
| `KX_GameObject.onBreak` | Lista de callbacks `f(obj, fragments)`, para som e partículas. Roda logo depois de os pedaços entrarem na cena, antes do empurrão da explosão |
| `KX_GameObject.onExplode` | Lista de callbacks `f(obj, position)`. Num objeto destrutível e explosivo, roda depois do `onBreak` |
| `KX_Scene.explode(position, radius=5.0, force=20.0, upBias=0.3, occlusion=True, mask=0xFFFF, ignore=None)` | Devolve os objetos atingidos (não os pedaços novos). `ignore` aceita um objeto ou uma lista |
| `KX_Scene.maxDebris` | Leitura e escrita. Começa com o Max Debris da cena; 0 = sem limite (só pelo Python) |

Documentadas também em `source/doc/python_api/rst/bge_types/` (`bge.types.KX_GameObject.rst` e
`bge.types.KX_Scene.rst`).

## Fases (uma por vez, com parada para confirmação)

| Fase | Entrega | Como validar |
|---|---|---|
| **F0** | DNA, RNA, painéis Destruction e Explosive, Max Debris, ponteiros de ID (readfile, expand, library_query, copy physics) | Editor headless: ligar, salvar e reabrir preserva os valores; apagar o grupo ou o Effect não deixa ponteiro pendurado; arquivo antigo abre com as opções desligadas. Build limpo (`ninja -t clean`), porque a DNA mudou |
| **F1** | Operador Generate Fragments | Headless: gera o grupo, os pedaços na layer 20, a física e o material interno; o usuário confere o diálogo na janela |
| **F2** | `KX_DestructionManager`: quebra por colisão e `shatter()` | Teste automático no runtime (como o do protótipo): quebra, contagem e posição dos pedaços, objeto removido |
| **F3** | `SphereQuery`, `scene.explode()`, Explosive (pavio, impacto, cadeia, Effect), `detonate()` | Teste automático: caixas, parede, barris em cadeia, granada; oclusão por parede |
| **F4** | Detritos (lifespan e Max Debris), `onBreak` e `onExplode`, conferência no build Web | Teste automático do limite; cena rodando no navegador |
| **F5** | Cena demo (porte do `First_Person_destruction`), docs, changelog e roadmap | O usuário joga e ajusta a sensação |

Depois da v1, se houver interesse: variações de fratura sorteadas (lista de grupos), fade-out dos detritos
em vez de sumir de uma vez, actuator "Explosion" e o nível 3 (corte em tempo real).

## Riscos e cuidados

- **Mudar a DNA exige rebuild limpo**, porque o Ninja não rastreia headers de DNA (ver AGENTS.md), e todo
  build roda com `VSLANG=1033`.
- **Os objetos do grupo precisam estar na cena**, numa layer inativa, para serem convertidos. O operador garante
  isso; se alguém montar à mão, o painel mostra um aviso.
- **Desempenho no Web e no Android**: muitos convex hulls ao mesmo tempo. Por isso o `max_debris` e o tempo de
  vida vêm desde a F4, e o padrão é conservador.
- **Um objeto Static destrutível com Triangle Mesh** é removido e substituído pelos pedaços; o Bullet já lida
  com isso. Conferir na F2 se não fica um contato "fantasma" por um frame.

## O que a F2 mostrou

- **O impulso lido é baixo para quedas.** O `appliedImpulse` é lido no frame lógico seguinte e reflete o
  último passo da física, não o pico do choque: uma caixa de 5 kg caindo de 6 m mede cerca de 3,6 no primeiro
  contato. É a mesma medida do protótipo (e do `collisionCallbacks` em Python), então os valores ajustados lá
  continuam valendo; o padrão 10 pede um golpe forte. Ajustar o Break Impulse por cena.
- **Os pedaços nascem encostados nas costuras** e a margem de colisão do Bullet os afasta um pouco no primeiro
  passo. A velocidade herdada é exata no nascimento e varia até uns 0,6 m/s depois do primeiro passo.
- **`AddReplicaObject` devolve uma referência a mais**: quem chama precisa de `Release()`, como o `addObject`
  do Python. Sem isso, o pedaço sobrevive à remoção e o `UpdateParents` cai no nó já liberado.
- O tempo de vida dos detritos já entrou na F2 (lifespan em ticks de 1/50 s); o Max Debris continua na F4.
- Teste automático: cena com quatro caixas (queda que quebra, queda que não quebra, `shatter()` com rotação e
  escala não uniforme, `shatter()` com velocidade herdada), log em arquivo, `RESULT F2 PASS 0`.

## O que a F3 mostrou

- **Uma reação em cadeia avança um elo por frame.** Um explosivo armado por outra explosão detona no frame
  lógico seguinte; o armado por impacto ou pelo fim do pavio detona no fim do mesmo frame. Com
  `detonate()` no frame 60, os barris somem nos frames 61, 62 e 63.
- **Objeto destrutível e explosivo** detona quando quebra (colisão ou `shatter()`) e quebra quando detona.
  Uma explosão que o alcança só o arma, então ele detona no frame seguinte, sem recursão.
- **Os pedaços voavam muito rápido.** Cada pedaço recebia o impulso inteiro do campo no seu ponto, como no
  protótipo, e com 1/8 da massa da caixa chegava a uns 40 m/s. Resolvido na F4 com a divisão pela fração de massa.
- **`ApplyImpulse` num corpo estático liga a flag kinematic no Bullet.** Por isso a explosão só empurra
  corpos dinâmicos que não estejam com a dinâmica suspensa.
- Teste automático: cena com sete áreas cobrindo empurrão, oclusão, `ignore`, `mask`, cadeia de barris
  com Effect, granada com pavio, pavio escrito pelo Python, impacto, caixa quebrada pela explosão,
  destrutível e explosivo, e `breakImpulse` por instância. Log em arquivo, `RESULT F3 PASS 0`. A F2 continua
  passando.

## O que a F4 mostrou

- **As listas de callbacks são copiadas na replicação.** Um callback posto no objeto da layer inativa vale
  para todas as cópias do `addObject`, e um posto numa cópia não passa para as irmãs. O `collisionCallbacks`
  compartilha a mesma lista entre as cópias; aqui preferimos cópias independentes.
- **Um callback que levanta exceção** mostra o erro no console e não interrompe o jogo nem os outros callbacks.
- **Diminuir `scene.maxDebris`** remove na hora os pedaços que passam do novo limite.
- Com o impulso dividido por massa, uma caixa de 5 kg quebrada por `explode(force=30)` a 2 m solta os
  pedaços a uns 3,6 m/s em média (a F3 mediu 4,4 m/s na CrateLow e 4,1 m/s na BombCrate).
- Teste automático: tempo de vida de 1 s, Max Debris 20 com três caixas, `maxDebris = 10` e `0`,
  `onBreak` no `shatter()`, `onExplode` no `detonate()` e no pavio, ordem dos dois num objeto destrutível e
  explosivo, callbacks do template nas cópias, erros de tipo, impulso por massa. `RESULT F4 PASS 0`, e a F2 e
  a F3 continuam passando.
- **Web:** o `build-web-release` compila, e a mesma cena empacotada com `package-web.py` e aberta no Chrome
  (headless, com o `verify-package.cjs` esperando mais tempo) dá `RESULT F4 PASS 0`, com os mesmos números do desktop.

## O que a F5 mostrou

- **Demo** em `source/release/demos/Destruction/Destruction.range`, instalada com o editor junto das outras.
  Ela é o `First_Person.range` com as caixas, a parede, os barris e a granada do protótipo, agora nos painéis
  Destruction e Explosive. As três caixas usam o mesmo grupo de pedaços, gerado pelo Generate Fragments. No
  Player, um componente (texto interno `destruction_demo.py`) só cuida das teclas E e G e do tremor da câmera
  pelo `onExplode`.
- **`isExplosive` e `isDestructible` davam falso nos moldes da layer inativa**, que não são registrados no
  gerenciador. Com isso, o componente não achava a granada para pôr o callback. Agora os dois leem só o flag do
  painel.
- **O Sphere Bounds usa o Radius do painel de física, não a malha.** A granada do protótipo colidia como uma
  bola de 1 m, então flutuava e rolava para longe da parede. A demo usa Radius 0,12.
- **O tempo do `addObject` conta em frames de 1/50 s**, não pelo tic rate da lógica.
- Teste automático sobre uma cópia da demo com um objeto de teste: painéis ligados, as três caixas quebradas
  por `explode()`, cadeia de dois barris com o terceiro longe, granada criada com `addObject` que respeita os
  2 s do pavio e quebra a parede, `onExplode` do molde nas cópias, e o caminho da tecla E detonando o último
  barril. `RESULT F5 PASS 0`, e a F2, a F3 e a F4 continuam passando.
