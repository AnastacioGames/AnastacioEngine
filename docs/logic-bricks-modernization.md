# Modernização dos Logic Bricks

## Objetivo

Evoluir os Property Sensors e Property Actuators para ler e alterar propriedades de runtime expostas por um objeto, com seleção visual, validação de tipos e comportamento previsível. As Game Properties atuais continuam compatíveis e suportadas.

## Princípios

- Compatibilidade com Logic Bricks e arquivos `.blend` existentes.
- Exposição explícita: não mostrar automaticamente toda propriedade interna do Blender.
- Tipagem real: a UI, as operações e a validação seguem o tipo da propriedade.
- O runtime é a fonte da verdade; nunca alterar apenas um campo do editor.
- Cada etapa precisa de build e cena de regressão verificáveis.

## Experiência proposta

```text
Objeto-alvo: [Self | objeto da cena]
Categoria:    [Game | Transform | Physics]
Propriedade:  [lista filtrada pelo alvo]
Operação:     [opções compatíveis com o tipo]
Valor:        [checkbox, número, texto ou X/Y/Z]
```

O campo atual de Game Property permanece na categoria `Game`; `Self` é o alvo padrão.

## Contrato de runtime

Implementar um registro central de propriedades expostas (nome de implementação a definir, por exemplo `RuntimePropertyRegistry`). Cada entrada deve conter identificador estável, categoria, rótulo, tipo, permissão de leitura/escrita, operações válidas, getter/setter e regras de validação.

Tipos iniciais: `bool`, `int`, `float`, `string`, `Vector3` e enum. Coleções, ponteiros, matrizes e conversões implícitas ficam fora do primeiro corte.

| Categoria | Propriedade | Tipo | Escrita inicial |
|---|---|---|---|
| Transform | posição, rotação, escala | Vector3 | sim |
| Transform | visível | bool | sim |
| Physics | massa dinâmica | float | após validação Bullet |
| Physics | velocidades linear/angular, gravidade | Vector3 | após validação Bullet |
| Game | Game Properties existentes | tipos já suportados | sim |

Massa só pode ser gravável para corpos dinâmicos. Em objetos `Static`, a UI deve explicar que massa efetiva é incompatível; alterar o dado sem reconfigurar o corpo Bullet não é válido.

## Milestones

### M0 — Levantamento e contrato

- Mapear DNA, RNA/UI, conversão Blender → Ketsji e classes runtime dos Property Sensors/Actuators atuais.
- Registrar os arquivos envolvidos e confirmar como cada propriedade física chega ao Bullet.
- Aprovar a lista inicial e os identificadores estáveis.

**Aceite:** diagrama de fluxo e tabela de propriedades aprovados; nenhuma mudança funcional.

**Levantamento concluído (2026-08-26):** dados persistidos em `bPropertySensor`/`bPropertyActuator`; conversão em `Converter/BL_ConvertSensors.cpp` e `Converter/BL_ConvertActuators.cpp`; execução legada em `GameLogic/SCA_PropertySensor.cpp` e `SCA_PropertyActuator.cpp`. O acesso ao estado vivo do objeto está em `Ketsji/KX_GameObject`, que já fornece `NodeGetLocalPosition`, `GetVisible`, `GetMass` e `GetPhysicsController`. A escrita de massa permanece fora de M1: `CcdPhysicsController::SetMass` precisa de teste próprio antes de ser exposta.

### M1 — Base tipada, somente leitura

- Implementar o registro e metadados de propriedades.
- Implementar leitura de um `bool`, `float` e `Vector3`.
- Validar alvo ausente, propriedade indisponível e tipo incompatível.

**Aceite:** builds COMPAT e CORE; Logic Bricks antigos sem alteração de comportamento.

**Implementação (2026-08-26):** `KX_RuntimePropertyRegistry` adiciona os identificadores estáveis somente-leitura `transform.local_position` (`Vector3`), `render.visible` (`bool`) e `physics.mass` (`float`). Alvo ausente, identificador desconhecido e massa sem controlador físico retornam falha com diagnóstico. Ainda não há UI, serialização nem ligação aos Logic Bricks; isso começa em M2/M3.

**Validação (2026-08-26):** `RangeRuntime` foi compilado com sucesso nos builds COMPAT (`build/`) e CORE (`build_core/`). Como o registro ainda não está ligado à UI ou à execução dos Logic Bricks, a validação funcional por cena começa em M2/M3.

### M2 — Seletor na UI

- Adicionar objeto-alvo, categoria e propriedade, sem remover o campo legado.
- Filtrar a lista por tipo de alvo e situação física.
- Persistir o identificador estável no `.blend`.

**Teste:** salvar/reabrir cenas com alvos dinâmicos e estáticos; massa não fica editável para `Static`.

**Implementado:** Property Sensor e Property Actuator agora persistem `use_runtime_property`, propriedade de runtime e, no Sensor, alvo opcional. Valores de runtime são persistidos tipadamente (`bool`, `float` ou `Vector3`) e a UI usa checkbox, campo numérico ou X/Y/Z conforme a propriedade. A UI mantém o fluxo legado quando a opção está desligada.

### M3 — Property Sensor tipado

- Comparações para bool, int, float, string e Vector3.
- Exibir somente operadores válidos por tipo.
- Definir igualdade vetorial por componente com tolerância documentada; sem operadores de ordem para vetores nesta versão.

**Teste:** cena mínima para cada tipo e operador permitido.

**Implementado:** comparação tipada para `bool`, `float` e `Vector3` (igualdade vetorial por componente com tolerância `0.0001`). A UI restringe operadores: bool e vetor usam Equal/Not Equal; massa também oferece Interval, Less Than e Greater Than.

### M4 — Property Actuator: Transform e Game

- Implementar `Set` para Transform e Game Properties.
- Implementar `Add` apenas para números e vetores quando a semântica for inequívoca.
- Criar widgets adequados: checkbox, número, texto e X/Y/Z.

**Teste:** posição, escala, visibilidade e Game Properties; repetir testes em `.blend` antigo.

**Implementação:** escrita de posição local, escala e visibilidade pelo modo runtime. `Assign` e `Add` funcionam para `float` e `Vector3`; modos sem semântica segura são recusados. O fluxo de Game Properties permanece inalterado quando o novo modo está desligado.

### M5 — Property Actuator: Physics

- Expor velocidade linear/angular e gravidade somente após confirmar atualização segura no Bullet.
- Expor massa somente depois de validar reinicialização/reconfiguração do corpo físico.
- Bloquear alvo sem corpo, `Static`, `No Collision` e objeto removido.

**Teste:** queda, colisão, massa e velocidade numa cena de regressão, sem crash nem comportamento físico inconsistente.

**Implementação:** massa, velocidade linear/angular e gravidade foram expostas ao runtime. Massa só aceita corpo físico dinâmico com massa atual positiva e valor novo maior que zero; os demais setters exigem controlador físico. Referências de Sensor e Actuator a objetos removidos são desvinculadas com segurança. A cena de regressão física continua pendente.

**Validação de build:** `RangeEngine` foi compilado nos perfis COMPAT (`build/`) e CORE (`build_core/`) após as mudanças de DNA/RNA e runtime. O teste `tests/python/bl_logic_runtime_properties.py` cria, salva, reabre e verifica Property Sensor/Actuators com vetor, float e bool nos dois perfis. A validação visual/física em cena fica pendente para execução no hardware do projeto.

### M6 — Debug, documentação e estabilização

- No Debug Mode, mostrar alvo, propriedade, tipo, último valor e erro de validação.
- Documentar uso e limites; criar cena de regressão em `projects-teste/`.
- Evitar reflexão/busca por string em cada frame.
- Atualizar `changelog.md`, arquitetura e guia de manutenção.

**Aceite final:** standalone e embedded validados; COMPAT e CORE compilam; regressão legada passa.

**Implementação (2026-08-26):** os Logic Bricks de runtime têm regressão de persistência em `tests/python/bl_logic_runtime_properties.py`. Os sensores Near, Radar e Ray também possuem `Debug Volume`/`Debug Ray`: Near desenha a distância de gatilho (verde) e de reset (amarelo), Radar desenha o cone (azul) e Ray desenha o alcance (vermelho), sobrepondo o trecho até o hit em verde. As linhas usam `RAS_DebugDraw`, sem afetar a simulação quando o checkbox está desligado.

**Teste manual de debug:** habilite o checkbox no sensor, inicie o jogo e confirme que a forma acompanha a orientação do objeto. Near deve mostrar duas esferas quando `Reset Distance` for maior; Radar deve mostrar um cone alinhado ao eixo configurado; Ray deve mostrar seu alcance e a porção verde até a colisão.

## Fora do escopo inicial

- Expor todo RNA/Blender API automaticamente.
- Materiais, shaders, animação e áudio.
- Migração automática ou remoção de Logic Bricks antigos.

## Estado atual

M0 a M6 foram implementados e os builds/persistência automatizada foram validados. Ainda falta a validação
manual da cena física descrita em M5 e do desenho de debug descrito em M6. Esses testes também constam no
roadmap para não ficarem escondidos neste documento de projeto.
