# Plano de trabalho em paralelo (Claude + Codex)

Criado em 2026-09-24, depois do fechamento do Android v1. Cada agente cuida de uma frente, e as frentes foram
escolhidas para não mexer nos mesmos arquivos. Regras gerais de build e anti-loop continuam em
[`../AGENTS.md`](../AGENTS.md).

## Isolamento (obrigatório)

- **Claude** trabalha em `D:\AnastacioEngine` (branch `main`, build em `build/`).
- **Codex** trabalha num worktree próprio, com um build separado. Nunca rode o `ninja` em `D:\AnastacioEngine\build`
  enquanto o Claude estiver compilando lá.
  ```
  git -C D:\AnastacioEngine worktree add D:\AnastacioEngine-codex -b codex/<frente> main
  ```
  Configure `D:\AnastacioEngine-codex\build` com as mesmas opções de `build/CMakeCache.txt`. O primeiro build
  leva cerca de 50 minutos.
- Faça um commit por unidade lógica, na branch `codex/<frente>`. Antes de pedir o merge, rode
  `git rebase main`. O merge em `main` é feito pelo Claude ou pelo usuário.
- **Arquivos reservados ao Claude**:
  - não edite `DNA_object_types.h`, `rna_object.c` nem `rna_game*.c`;
  - não edite a parte de veículo de `properties_game.py`;
  - não edite `source/gameengine/Physics/Bullet/*Vehicle*`, `source/gameengine/Ketsji/KX_VehicleWrapper*` nem os
    componentes Python de veículo.
  - Se a sua frente precisar deles, pare e avise.
- **`docs/changelog.md` e `docs/roadmap.md`**: só acrescente entradas novas, sem reescrever as existentes. O
  conflito de texto é resolvido no merge.
- Não altere a licença do projeto.

## Frentes

### Claude: Vehicle System (plano 2)

Executar o [vehicle-system-plan-2.md](vehicle-system-plan-2.md) nesta ordem:

1. Fase B: direção, freios, freio de mão e volante visual.
2. Fase C: `has_drive`, drive type, torque/RPM e gearbox.
3. Fase A: deslocamento do centro de massa.

Essa frente mexe em DNA e exige rebuild limpo, por isso fica isolada no build principal. Cada sub-passo para
para o usuário testar no jogo real.

### Codex, frente 1: auditoria de bugs silenciosos (`codex/auditoria`)

- Percorrer os candidatos de [relatorio-varredura-bugs-silenciosos.md](relatorio-varredura-bugs-silenciosos.md),
  do mais grave para o menos grave.
- Para cada candidato:
  - reproduzir o bug ou provar, pelo código, que ele não acontece;
  - aplicar uma correção isolada, num commit por bug;
  - fazer o build de `RangeEngine` e `RangeRuntime` e testar.
- Marcar no relatório o resultado de cada candidato: confirmado e corrigido, ou descartado com o motivo.
- Candidatos em arquivos reservados ficam anotados, sem correção.

### Codex, frente 2: associação de arquivos no Windows (`codex/assoc`)

- Abrir `.blend` com o `RangeEngine` e `.range` com o `RangeRuntime`, pelo duplo clique.
- Começar pelo registro do Blender que já existe (`creator` `-R`/`-r`, `BLI_windows_register_blend_extension`),
  adaptando os nomes, os ícones e a extensão `.range`.
- Documentar em `docs/` como registrar e desfazer o registro, e testar no Windows real.

### Codex, frente 3: lacunas de tradução (`codex/i18n`)

- Rodar `i18n_audit.py`, que fica em `tools/tests/web_profile/`, para pt_BR e es.
- Preencher as lacunas do catálogo que restaram do Blender 2.79: cerca de 455 no pt_BR e 511 no es.
- Mexer só nos arquivos `translations_*.py` e no fluxo de catálogo já existente. Não precisa de build C++, só do
  editor já compilado para a auditoria.
- O russo continua dependendo de revisão nativa. Não gerar tradução em massa para ele.

## Próximas frentes (para quem terminar primeiro)

- **Vendorizar Recast/Detour** a partir de `tools/recastnavigation-main`. Ver
  [relatorio-varredura-recastnavigation.md](relatorio-varredura-recastnavigation.md). Mexe no CMake, então
  combinar antes com o outro agente.
- **Medir `MainRender`** na cena de benchmark ([performance-audit.md](performance-audit.md)). Primeiro medir,
  depois levantar hipóteses.

## Bloqueadas (dependem do usuário)

- Cutscene, Fase 3: faltam os PNGs aprovados, com autoria e licença.
- Idioma: conferir na janela real e revisão nativa de es e ru.
- Export presets e janela do Linux: testes manuais.
- Play Console: adiada.
