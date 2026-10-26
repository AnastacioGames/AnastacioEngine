# Revisão da frente 4: física

Data: 2026-10-26. Frente 4 do [levantamento](levantamento-modulos-criticos.md). Primeira rodada,
concentrada no ciclo de vida de constraints e veículos: criação pelo Python e pelo editor,
`removeConstraint`, `endObject`, `suspendPhysics`/`restorePhysics` e o merge de cena do LibLoad.
Arquivos: [CcdPhysicsEnvironment.cpp](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp),
[CcdConstraint.cpp](../source/source/gameengine/Physics/Bullet/CcdConstraint.cpp),
[KX_ConstraintWrapper.cpp](../source/source/gameengine/Ketsji/KX_ConstraintWrapper.cpp).

Regressão: [criar_cena_revisao_fisica.py](../tools/debug/cenas/criar_cena_revisao_fisica.py), oito casos
rodados com `AnastacioRuntime.exe --server`.

## Achados corrigidos

| ID | Defeito | Reprodução antes | Correção | Depois |
|---|---|---|---|---|
| FIS-01 | `KX_ConstraintWrapper` guardava o ponteiro do `CcdConstraint`, que é apagado em `RemoveConstraint`. O comentário dizia que o wrapper guardava só o id, o que não era verdade | casos `remove_con` e `end_obj`: ler `constraint_id` depois de `removeConstraint` ou de `endObject` num dos corpos derrubava o player | Mesmo padrão do veículo: o `CcdConstraint` avisa seus wrappers no destrutor (`SetInvalidationCallback`), e todo método e atributo do wrapper gera `ReferenceError` | os 7 acessos dão `ReferenceError`, sem crash |
| FIS-02 | Na Bullet, `m_userConstraintId` e `m_userConstraintPtr` são uma `union`. Gravar o ponteiro sobrescrevia o id, então `constraint_id` virava os 32 bits baixos do endereço (ex.: -2031918448). Duas constraints podiam colidir no mesmo id | caso `vivo`: id negativo e diferente a cada execução | O id sequencial fica no `CcdConstraint`; as três buscas por id (`GetConstraintById`, `RemoveConstraintById`, `GetAppliedImpulse`) comparam com ele | `constraint_id` = 1, e `removeConstraint(1)` acha a constraint |

## Controles

- `vivo`: constraint viva continua legível e editável (tipo, `enabled`, `getParam`/`setParam`).
- `suspende`: com `suspendPhysics` a constraint só sai do mundo, sem ser apagada. O wrapper continua
  funcionando suspenso e depois de `restorePhysics`.
- `junta` e `junta_sem`: um Rigid Body Joint criado no editor segura o cubo pendurado em z = 3,0;
  sem a junta, o cubo cai até z = 1,0.
- `veiculo`: o wrapper do veículo já era protegido e dá `ReferenceError` depois de `endObject` no chassi.

## Conferido sem mudança

- `MergeEnvironment` (LibLoad) remove os corpos com `freeConstraints=true`. É intencional:
  `KX_Scene::MergeScene` recria as constraints com `ReplicateConstraints`. Os veículos passam por
  `MoveVehicles` antes, então não são apagados.
- `RemoveCcdPhysicsController` remove as constraints do corpo, os pares de colisão e o veículo do
  chassi, inclusive quando o corpo não está registrado (chassi movido ou suspenso).

## Pendente nesta frente

- `removeConstraint(id)` de uma constraint suspensa não a encontra, porque a busca é feita só no
  mundo. Ela volta no `restorePhysics`. Comportamento antigo, sem crash.
- Ainda não revisados: personagem, sensores de colisão (callbacks que removem objetos), soft body
  e o tempo de física com muitos corpos e contatos.
