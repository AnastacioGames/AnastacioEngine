# Release 0.5.0 — passos no Linux

Instruções para quem (pessoa ou Claude) for gerar e testar o pacote Linux da 0.5.0. Windows e Web já
foram gerados e testados em 2026-10-12 (commits ed2fe7fc, a8f045cc, ce19b151, c08a54e7). Regras gerais em
[AGENTS.md](../AGENTS.md); procedimento completo em [distribution-0.1.md](distribution-0.1.md).

## 1. Atualizar o repositório

```bash
git pull origin main        # precisa estar em c08a54e7 ou depois
```

Use um **clone separado** para o container: as pastas `build-linux*/` geradas dentro dele não servem para a
máquina host (e vice-versa).

## 2. Gerar o pacote no container Ubuntu 22.04

Na raiz do clone:

```bash
podman run --rm -v $PWD:/work:Z -v $PWD/tools/linux/container-build-22.04.sh:/build.sh:Z \
  docker.io/library/ubuntu:22.04 /build.sh
```

(`docker` funciona igual, sem os `:Z`.) A versão padrão do script é 0.5.0. Saída:
`AnastacioEngine-0.5.0-linux-x86_64.tar.xz`.

O script já falha se faltar no tar: `libae_uvatlas.so`, `icons_upbge/`, `icons_blender5/`,
`anastacio_network/`, ou se o `Range_Components_Label.rar` entrar. O `libae_denoise.so` só é conferido
quando foi compilado (precisa do OIDN).

Conhecido: o OIDN não está no apt do container, então o bake de lightmap no Linux usa o box blur. Não é bug.

## 3. Testar o pacote

Extraia numa pasta limpa (nunca teste a partir da pasta de build):

```bash
mkdir -p ~/teste-050 && tar -xJf AnastacioEngine-0.5.0-linux-x86_64.tar.xz -C ~/teste-050
```

Checklist (o usuário confirma o que é visual):

- [ ] Editor abre; tela inicial é o `startup.blend` novo (telas Asset Browser, Game Dev, Game Play, Script; sem pie menu no Z/Tab).
- [ ] About mostra 0.5.0.
- [ ] Runtime roda uma cena (ex.: Play no editor e o runtime do pacote com um `.range`).
- [ ] Cenas novas, geradas com o editor do pacote em modo background a partir de `tools/debug/cenas/`:
      `criar_cena_ssgi.py` (abria crash no Windows antes de a8f045cc), `criar_cena_vfog.py`,
      `criar_cena_vitral.py`, `criar_cena_world_sound.py`. Sem crash e sem erro de shader no terminal.
      As cenas de medição fecham sozinhas (endGame) — saída 0 é o esperado.
- [ ] Som (World Sound: Music/Ambient) toca.
- [ ] Bake de lightmap e UV atlas funcionam (usam `libae_denoise.so` / `libae_uvatlas.so`).

Só abra janelas do jogo/editor quando o usuário pedir; o resto valide em background.

## 4. Hash e publicação

```bash
sha256sum AnastacioEngine-0.5.0-linux-x86_64.tar.xz
```

Acrescente a linha ao `SHA256SUMS.txt` da release (mantendo as do Windows abaixo) e anexe o tar.xz e o
SHA256SUMS na release `v0.5.0` do GitHub (`gh release upload v0.5.0 ... --clobber`), só quando o usuário
mandar publicar.

Hashes do Windows (build/dist na máquina Windows, 2026-10-12):

```
34bd79db594cf5167f323739a1d43d611edfadd210fd88c911f2cf956b360c4e  AnastacioEngine-0.5.0-windows-x64.zip
e7b5045901d571d6b34f2ef6c443dc462c97af86644bde337630a50438311068  RangeArmor-0.5.0-windows-x64.zip
```

## Pendências conhecidas da 0.5.0 (não bloqueiam o Linux)

- Web: o feixe do Spot na Volumetric Fog não aparece no navegador (no desktop aparece).
- Sombra colorida no Sun com cascatas (CSM).
- Não alterar a licença do projeto.
