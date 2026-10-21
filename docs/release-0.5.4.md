# Release 0.5.4 — Windows agora, Linux depois

Estado em 2026-10-20. Notas em [release-notes-0.5.4.md](release-notes-0.5.4.md).

## Windows (publicado, 2026-10-20)

- Textos novos desde a 0.5.3 traduzidos (pt_BR, es, ru) em `translations_more.py`; os textos das receitas do
  Smart Component Wizard ficaram em português (são conteúdo do código gerado).
- `RangeEngine` + `RangeRuntime` + `ninja install`; `ctest` 15/15 (`range_language` entrou na lista de módulos
  só do jogo em `bl_load_py_modules.py`).
- Runtime Web de `build-web-release` recompilado (manifesto regenerado, 242 módulos); `web/` montado com
  `stage_release_web.py`.
- Lista de arquivos do zip igual à da 0.5.3 (sem arquivo removido ou adicionado fora de scripts), sem `\` nos
  nomes. Zip extraído: editor `-b` abre, runtime roda o `base6 anastacio.range` (relato do Discord) e nenhum
  erro SideBySide; traduções novas conferidas no editor do pacote.
- RangeArmor: painel recompilado (`cargo build --release`, testes 26/26) por causa do padrão
  `./engine/Linux64/AnastacioRuntime`; resto igual ao zip da 0.5.3.

```text
78cf434ddbea8fad2d0a91b183f1c237d373927bc543186b2b98ef2ec89166d0  AnastacioEngine-0.5.4-windows-x64.zip
5515dfa1e4099057a6c9d2cee3a737f44da518583232bef9e73b49ec7efb2235  RangeArmor-0.5.4-windows-x64.zip
```

## Linux (pendente, PC Linux)

Os pacotes Linux montados antes (`build-linux/dist/`) estão desatualizados: refazer com o main atual
(`tools/linux/container-build.sh`, `VERSION=0.5.4`), RangeArmor Linux com `stage_rangearmor_linux.sh`
(launchers do `RangeArmor-0.5.4-windows-x64.zip`), acrescentar as linhas no `SHA256SUMS.txt` da release e
subir com `--clobber`. Depois atualizar as notas (Downloads) e o README.

## Zip Windows refeito (2026-10-20, mesma noite)

Painel Baked Lighting, addon Anastacio Ragdoll e dicas soltas estavam escritos em português no código
(`63a1157e`); o addon Ragdoll passou a vir ativo (`66268bb6`). Zip da engine refeito e trocado na release com
`--clobber` (hash acima atualizado); RangeArmor sem mudança.
