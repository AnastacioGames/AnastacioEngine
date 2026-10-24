# Ragdoll — plano de evolução

Iniciado em 2026-10-14. Guias de uso: [autoria](ragdoll-authoring.md) e [execução](ragdoll-runtime.md).
Pendências resumidas também em [roadmap.md](roadmap.md) (seção "Vehicle System / Vehicle Lab").

## Feito (2026-10-14)

Detalhes em [changelog.md](changelog.md) (entradas "Ragdoll" de 2026-10-14 e 2026-10-15).

- **Scripts do RolimaRacer corrigidos:** inicialização completa, transição idempotente, só constraints próprias,
  retorno com confirmação, sem setters de amortecimento por quadro. 100 ciclos nos quatro rigs reais
  (20/20/22/23 corpos); usuário validou no jogo. Geradores `tools/debug/cenas/validar_correcao_ragdoll.py` e
  `validar_rigs_rolima.py`.
- **Addon de autoria** `source/release/scripts/addons/anastacio_ragdoll.py`: prévia por osso, caixas, geração
  transacional, Undo/Redo, collection por armature. Prévia validada pelo usuário em rig próprio.
- **Núcleo comum** `source/release/scripts/modules/anastacio_ragdoll_runtime.py`: FREE, ANCHOR e NPC, recuperação
  automática ou manual, presets Duro/Equilibrado/Leve, massa e juntas por osso, herança linear e angular.
  Evidências em `debug-logs/ragdoll-runtime-final-20261014/`.
- Addon legado `easy_ragdoll_RangeEngine.py` removido a pedido do usuário (backup em
  `debug-logs/ragdoll-legacy-removed-20261014/`). Scripts do jogo e `tools/ADD na engine anastacioEngine/easy_ragdoll.py`
  preservados.
- Sem C++ novo.

**Baseline** (componente legado corrigido, não é benchmark do núcleo novo): rodada
`perfil-rolima-20261014-192125`, ativação 0,436–0,538 ms e desativação 0,233–0,295 ms para 20 corpos, retorno do
controlador até 1,076 ms, nenhum SPIKE nas janelas das quedas. Pausas longas entre quedas dominadas por
`endframe.swap`, sem causa atribuída. Ver [profiler](engine-profiling.md#eventos-de-ragdoll-do-rolimaracer).

## Decisões

- Autoria como addon; execução por componente Python; C++ só por limitação demonstrada.
- NPCs usam o mesmo núcleo, sem dependência de input.
- `auto_recover` independe do modo livre/âncora; o temporizador não confirma retorno inválido.
- Uma única implementação de runtime, distribuída como módulo da engine.

## Pendências

- Avaliação visual dos presets e do personagem real pelo usuário (presets são passivos, sem músculos).
- Migração do adaptador RolimaRacer para o núcleo novo (o jogo ainda usa
  `scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll`).
- Colisões configuráveis: separar cenário, veículo, outros personagens, membros adjacentes e não adjacentes;
  conferir grupos/máscaras e `use_linked_collision` na conversão.
- Cápsulas e Character.
- Volume de retorno em cenários complexos: hoje FREE foi validado com controlador Rigid Body/Dynamic BOX e chão
  plano; a checagem AABB não substitui query Bullet.
- Blend/animação de levantar (de costas ou de bruços).
- Instanciação dinâmica de grupos.
- Exportadores e Web/Android: validar distribuição do módulo no player, export Windows/Linux e Web.
- Prévia: ainda faltam eixos, limites e sobreposições desenhados. Manipulação direta na viewport é evolução futura.
- API pública ainda proposta: `activate(...)`, `request_recovery(...)`, `reset(...)`, consulta de estado e
  notificações. Estados `ANIMATED → ENTERING → SIMULATING → RECOVERING → ANIMATED`, com falha explícita.

## Contornos do RolimaRacer a revisar na migração

Não confirmados; medir no build atual antes de remover.

- `_ensure_deps()` bloqueia até a ativação por impacto sem input.
- Retorno após 0,5 s e cooldown de 2 s são regras do jogo: expor configuração.
- `_set_collider_state()` desmonta/remonta filhos compound e estaciona colisores em Z=-1000. Investigar compound
  no C++ antes de remover.
- `orig_local_pos/ori` são reaplicados sem garantir o mesmo pai: usar âncora explícita de assento.
- `check_culling_anomaly()` presume que carro visível implica piloto visível (falso positivo possível).
- O refresh desloca armature e filhos em 1 mm e força visibilidade; sequência interrompida pode deixar offset e
  interfere em primeira pessoa e LOD.
- ~800 ms no swap ao voltar do ragdoll (roadmap): não atribuir só ao Python.

## Quando entrar C++

Só se um protótipo demonstrar: reset de vários corpos em fase segura do frame, atualização de pose/bounds, filtros
por par, sleep por corpo ou parâmetros do solver ausentes na API. Uma peça por vez, com evidência. Active ragdoll
(motores seguindo animação) é frente posterior.

## Roteiro de validação

Cobrir: 1 e 10 pilotos, vários ragdolls simultâneos, 100 ciclos de entrada/saída, exclusão de alvo, troca de cena,
reinício, rig sem parent, parent empty, colisor do carro como root, escalas diferentes, constraints adicionais,
pausa/time scale, primeira pessoa, câmeras, LOD e skinning CPU/GPU. Medir CPU Python/física/animação, corpos
acordados, p95/p99 e pior quadro da transição, separando swap/GPU. Aparência da queda e do retorno exige teste no
jogo real pelo usuário. Cenas controladas: skill `cena-de-teste`.
