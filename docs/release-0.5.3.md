# Release 0.5.3 — Windows agora, Linux depois

Estado em 2026-10-18: versão subida para 0.5.3 (`ANASTACIO_VERSION_STRING`, About em `wm.py`,
`stage_release_windows.py`, `container-build-22.04.sh`). Mudanças desde a 0.5.2: `79556dad` (módulo Effects
criado pela chuva recebe os sons) e `4d81b518` (partículas e chuva no WebGL2). Notas em
[release-notes-0.5.3.md](release-notes-0.5.3.md).

## Windows (pronto, 2026-10-18)

- `RangeEngine` + `RangeRuntime` + `ninja install` OK; `ctest` 15/15.
- Runtime web de `build-web-release/bin` compilado depois de `4d81b518`; `web/` montado com `stage_release_web.py`.
- Lista de arquivos do pacote idêntica à da 0.5.2 (`blender.crt/` com manifesto, `ucrtbase.dll` solto,
  `sounds/effects/` presente). Zips sem `\` nos nomes. Editor abre a partir da cópia extraída (`-b`).
- RangeArmor sem mudanças desde a 0.5.2 (scripts e `legacy-template-sha256.json` iguais); zip refeito da
  pasta da 0.5.2 com raiz `RangeArmor-0.5.3-windows-x64/`.

```text
e90d6f46ba3ae7b18df111d3ddebca1a6ba9d6527d20a2015e9fa67b620a5a58  AnastacioEngine-0.5.3-windows-x64.zip
58049cf7ac1ceb4396cc4801d97c95445d9f807d9960b225c3696e0bac8f6c9f  RangeArmor-0.5.3-windows-x64.zip
```

## Linux (pendente, PC Linux)

1. Pacote da engine: `VERSION=0.5.3` no `container-build-22.04.sh` (já é o padrão), ver
   [release-0.5.0-linux.md](release-0.5.0-linux.md).
2. RangeArmor Linux: passos em [release-0.5.2.md](release-0.5.2.md#rangearmor-para-linux-pendente-pc-linux),
   trocando 0.5.2 por 0.5.3 (os launchers vêm de `RangeArmor-0.5.3-windows-x64.zip`).
3. Baixar o `SHA256SUMS.txt` da release, acrescentar as duas linhas Linux e subir com `--clobber`;
   atualizar README (linha Linux) e as notas.
