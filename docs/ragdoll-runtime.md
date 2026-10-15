# Anastacio Ragdoll — componente comum

Versão inicial 0.3, Python distribuído com a engine, sem alteração C++ nesta entrega.
Autoria: [guia do painel](ragdoll-authoring.md). Não migra nem substitui automaticamente
o componente legado do RolimaRacer: sua integração de input, assento e colisores continua
nos scripts externos corrigidos. Teste o novo sistema em cópia/cena isolada.

## Preparar a execução

1. Configure e confira os cubos na pose de repouso. Para executar, escolha **Pose Position**
   no painel; Rest Position impede a avaliação de pose e é recusado ao preparar execução.
2. Em **Física e execução**, escolha o preset e clique **Aplicar preset aos ossos incluídos**.
   Ajuste campos individuais se necessário; o preset não altera a geometria nem a massa total.
3. Defina **Massa total**, **Recuperação** e a referência de âncora/controlador.
4. Configure **Recuperar automaticamente**, tempo em segundos de simulação e herança de velocidades.
5. Clique **Preparar física + componente**. O addon gera rigid bodies, cone-twist e anexa
   `anastacio_ragdoll_runtime.AnastacioRagdoll` uma única vez à armature. O módulo vem de
   `2.79/scripts/modules/`; não cria cópia embutida em cada projeto.
6. Depois de preparado, **Gerar / atualizar corpos** também preserva/prepara a execução
   e sincroniza as opções do painel com o componente. **Remover corpos gerados** remove
   os corpos, pivôs, constraints e este componente; preserva o controlador do jogo.

O campo **Active** no componente inicia o personagem caído. O padrão é desligado:
o componente suspende os corpos na inicialização. Apenas dar Play não dispara queda
quando Active está desligado. Pode-se ativar por script ou propriedade durante o jogo.
As alterações nos argumentos do componente valem ao iniciar o jogo; atualizar os corpos
reescreve as opções correspondentes a partir do painel de autoria.

## Presets

| Preset | Limites XYZ | Amortecimento linear | Amortecimento angular |
|---|---|---|---|
| Duro | 15° / 10° / 15° | 0,15 | 0,80 |
| Equilibrado | 45° / 25° / 45° | 0,08 | 0,45 |
| Leve | 80° / 50° / 80° | 0,03 | 0,15 |

São amplitudes e amortecimento passivo, não músculos ou motores que tentam sustentar
uma pose. A massa total é independente; distribui-se por volume das caixas multiplicado
pelo peso relativo de cada osso. Cada junta, peso e amortecimento pode ser ajustado por
osso. A junta conecta ao ancestral incluído mais próximo, inclusive se um controle intermediário
foi excluído. Os eixos acompanham o osso mesmo quando a caixa recebe rotação local.

Colisões usam o **grupo 16** (bit 15) reservado para os corpos: colidem com outros grupos,
não entre si ou com corpos de outro ragdoll neste grupo. Juntas também desabilitam colisão
entre os pares ligados. Grupos/máscaras configuráveis e colisão seletiva entre membros
ainda são evolução pendente; não use este grupo para o chão/cenário.

## Recuperação e NPCs

- **Livre / NPC:** configure um Rigid Body/Dynamic separado com malha e bounds BOX, na raiz
  da cena. A armature deve ser No Collision, vinculada diretamente a esse controlador
  ou sem pai. O controlador fica suspenso durante a queda. O retorno busca chão abaixo
  do corpo raiz, põe o controlador vertical preservando o yaw inicial e o restaura.
- **Âncora / veículo:** configure um empty/assento/objeto externo. A armature é destacada
  ao cair e retorna à transformação relativa capturada na ativação, acompanhando a âncora
  em movimento. O componente não suspende, vira ou desloca o veículo. Colisores auxiliares
  do piloto e animações específicas pertencem ao adaptador do jogo.
- **Recuperar automaticamente** desligado: NPC/personagem permanece em ragdoll até comando
  explícito. Não cria outro sistema físico, não exige teclado e não impede reviver por script.
  A AI deve respeitar `active`/`active_ragdoll` para não continuar controlando o personagem caído.

Âncora/controlador devem ter escala mundial uniforme positiva, sem cisalhamento. Aplique
escala em uma cópia apropriada antes de preparar; o addon não altera a malha do controlador.
Não mude a escala da hierarquia durante o ragdoll. O tempo de retorno usa `getFrameTime`:
slow motion alonga esse tempo no relógio real. Retorno recusado tenta novamente após um
segundo de simulação, mantendo o estado caído.

O retorno livre desta primeira versão é validado em chão plano com controlador BOX e
bounds das malhas coerentes com os colisores. A checagem usa AABBs mundiais com margem:
pode bloquear locais livres em malhas côncavas, volumes de triggers e cenas com bounds amplos.
Não equivale a uma consulta Bullet de volume arbitrário; cápsulas, formas físicas que
excedem a malha e compounds precisam de validação específica. Não considerar o modo livre
validado para qualquer terreno/cena. A API `collide` existente usa pares já calculados e não
resolve uma consulta síncrona num destino hipotético. Nenhum C++ foi alterado para contornar isso.

## API para o jogo

Depois de `start`, encontre o componente pela classe/módulo ou pelo marcador
`anastacio_ragdoll` (não pelo nome do objeto). Métodos retornam sucesso explicitamente:

```python
comp.activate(velocity_source=veiculo)  # opcional; herda v + omega × distância
comp.recover()                         # destino calculado pelo modo configurado
comp.set_active(True)                  # equivalente a activate
armature['active_ragdoll'] = True      # observado no update seguinte
comp.auto_recover = False              # alteração de política durante o jogo
```

`recover(destination)` aceita matriz do **controlador** no modo FREE ou da **armature**
no modo ANCHOR. FREE mantém a verificação de volume; um destino explícito não busca chão
novamente. O jogo responde pelo chão de destinos explícitos e por âncoras apropriadas.
`recovery_validator(comp, rig_world_matrix)` pode vetar um destino adicionalmente.
`on_recovered(comp)` permite retomar AI/animação depois do retorno confirmado.

`active`, `is_valid`, `error` e `blocked_reason` permitem decidir se o controle pode voltar.
Não limpe a flag do jogo se `recover()` retornar False. Alvo/pivô/corpo removido ou alterado
produz erro explícito e não confirma recuperação. Uma falha congela os corpos ainda existentes;
recuperação dessa falha exige ação do jogo. Transições bem-sucedidas são idempotentes.

Animações nas camadas 0–7 são interrompidas na ativação. O componente restaura os canais
capturados, mas o jogo deve reiniciar suas ações de locomoção/dirigir. Recuperação com
animação de levantar e blend ainda não foi implementada. Não há setters de amortecimento
ou velocidade por quadro; o Bullet faz damping/sleep. A consulta de volume ocorre somente
na tentativa de retorno. A transformação mundial é composta de localTransform na transição,
evitando ler cache mundial ainda não atualizado no mesmo tick.

## Demonstração e evidência

Cena manual: `debug-logs/ragdoll-runtime-final-20261014/demo-ragdoll.range`.
No editor, **P** inicia; **V** derruba todos, com impulso; quatro retornam automaticamente
e o NPC roxo permanece caído; **R** solicita retorno de todos; **Esc** encerra o jogo.
Os corpos ficam visíveis apenas nesta demonstração. Por isso o controlador de teste também
alinha a representação visual enquanto inativa, sem escrever velocidades.

Geradores e regressões em `tools/debug/cenas/`:

- `validar_runtime_ragdoll.py`: presets, massas, juntas, persistência, rollback de escala,
  cinco rigs simultâneos, 100 ciclos por modo, Active inicial, automático/permanente,
  herança angular/linear, bloqueio por obstáculo, veto do jogo e alvo inválido.
- `validar_runtime_ragdoll_ui.py`: Undo/Redo de opções, preset, preparação e remoção de
  física/componente/pasta, preservando o controlador e os outros rigs.
- `criar_demo_ragdoll.py`: cinco rigs de dez ossos; com
  `ANASTACIO_RAGDOLL_DEMO_SMOKE=1`, gera cena separada com execução automática e JSON.

Player Windows validado; avaliação visual dos presets e teste em personagem real com
skinning/animação ainda dependem do usuário. Instanciar grupos de NPCs por Add Object,
blend, exportadores externos e Web/Android ainda não foram validados.
