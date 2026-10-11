# Tarefa deste worktree (Claude) — cluster cache GPU (uniforms/material)

Fonte: [docs/auditoria-suspeitos.md](docs/auditoria-suspeitos.md), seção
"gpu / depsgraph (lado Blender)". Leia a seção inteira antes de começar — a
tabela tem a coluna "Onde" com arquivo:linha de cada item.

Branch: `claude/auditoria-gpu-cache`. Worktree separado do projeto principal
e do worktree do Codex (`D:\AnastacioEngine-auditoria-codex`, cluster
Spawn/LibLoad) — arquivos não se cruzam, pode trabalhar em paralelo sem medo
de conflito.

## Itens para investigar/corrigir

Todos hoje marcados "analisado 2026-10-09: cache exige versão por imagem, luz
ou probe; não alterado" — é literalmente o mesmo bloqueio nos cinco, então a
tarefa real é desenhar UM mecanismo de versionamento e aplicá-lo nos cinco:

1. **GP3** (`gpu_codegen.c:1741` → `gpu_texture.c:453` → `gpu_draw.c:497`
   `GPU_verify_image`): acquire ibuf com spinlock global por bind de material,
   mesmo com a imagem igual.
2. **GP4** (`gpu_codegen.c:1774` `GPU_pass_update_uniforms`): reenvia todos os
   inputs dinâmicos a cada bind, sem comparar com o último valor.
3. **GP5** (`gpu_material.c:754` `GPU_material_bind`): recalcula `dynlayer`
   de todas as lamps, `BLI_findlink`, view/proj por bind.
4. **GP6** (`gpu_material.c:696` `GPU_material_update_lamps`, via
   `KX_BlenderMaterial.cpp:344`): recalcula matrizes do lamp por material
   (só dependem de lamp+view — poderiam cachear por combinação).
5. **GP7** (`Ketsji/BL_BlenderShader.cpp:309-322`): `FindProbe` + bind de probe
   por objeto todo frame; cache só existe pra probe ausente.

Desenho sugerido (do próprio relatório, seção "Correção comum GP1/GP2" como
referência de padrão já aplicado): um contador de versão que só incrementa
quando o estado de origem (imagem/luz/probe) realmente mudou, e um "último
valor enviado" por GPUMaterial/GPUShader, comparado antes de reenviar.
GP1/GP2 já usam esse padrão (cache no GPUShader, 2026-10-09) — ponto de
partida concreto pra copiar a estrutura.

**Bônus se der tempo** — mesma vizinhança de arquivo, ainda sem cache:
- **RA2** (`BL_BlenderShader.cpp:332` → `gpu_material.c:902`
  `GPU_material_bind_uniforms`): produto view×object já é reutilizado, mas as
  inversas (local-to-view, normal) continuam recalculadas por draw — relatório
  já confirma "cache de inversas não implementado".

## Como medir

Use a skill `cena-de-teste` (bpy legado) com cena de luzes/materiais, no
mesmo padrão do contador `lightUniforms` usado pra medir GP1/GP2 (ver
changelog de 2026-10-09). Rodadas curtas (~10s) são o suficiente.

## Build

Use a skill `build-anastacio` (vcvars64 + ninja). O worktree já tem `lib`
configurada (junction para a lib real do projeto principal) — **nunca** rode
`git worktree remove` neste worktree sem antes `cmd /c rmdir lib` (há um hook
em `.claude/settings.json` que bloqueia isso automaticamente, mas não confie
só nele).

## Ao terminar cada item

Atualize a tabela/status em `docs/auditoria-suspeitos.md` (mesmo padrão dos
itens já "corrigido"/"concluído" existentes) e registre no
`docs/changelog.md`. Não toque na seção "Spawn, remoção, LibLoad" (SP*) —
é do outro worktree.
