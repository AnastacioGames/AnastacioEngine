# Fonte local do RangeArmor

Recuperado em 2026-10-08 do commit `69df19d9`, caminho original
`tools/RangeArmor-master/RangeArmor-master/`. Esta pasta mantém o fonte fora do caminho
ignorado `tools/RangeArmor-master/`, permitindo revisar e versionar novas alterações.
Licença e créditos originais permanecem nos arquivos do projeto.

A GUI instalada em `build/bin/rangearmor/` foi preservada; seus scripts originais diferem
do snapshot e foram copiados para o backup da sessão. `build_release.py` e `prepare_cooked.py`
foram atualizados na instalação. O exportador cozinha o arquivo principal protegido com o
runtime do host antes de empacotar. O launcher Windows foi recompilado do fonte recuperado.
Um hash do template antigo permite substituí-lo apenas na entrega, preservando o launcher
original do projeto. Launchers personalizados não são substituídos por esse mecanismo.

Para compilar o launcher Windows, carregar `vcvars64.bat` e `VSLANG=1033` no mesmo processo
do Cargo, conforme `AGENTS.md`; usar `cargo build --release --locked` com `--target-dir`
fora desta pasta. Copiar `rangearmor.exe` para `release/launcher/Launcher.exe` da instalação
somente após testes. Os binários gerados não fazem parte do fonte.

Testes de segurança do exportador: `python tools/tests/test_rangearmor_release.py`.
Linux, outra GPU e o jogo real precisam de validação própria.

O painel atual é Rust/eframe (`source/gui-rs/`); a GUI Godot fica como backup na instalação.
As dependências fixadas no Cargo.lock exigem Rust 1.95 ou posterior; o Rust 1.92 da
máquina não as compila. Toolchain 1.95.0 instalado separadamente, sem trocar o padrão.
Com vcvars64/VSLANG configurados no mesmo processo, usar `cargo +1.95.0 test --locked`
e `cargo +1.95.0 build --release --locked`, com `--target-dir` fora do fonte.
O executável resultante é `rangearmor_panel.exe`; na instalação chama-se
`RangeArmor Panel.exe`. Preservar o anterior em backup antes de substituir.

Migração Windows de 2026-10-08: novos projetos usam `AnastacioRuntime.exe`;
configurações antigas com `RangeRuntime.exe` continuam reconhecidas. O caminho
explicitamente configurado ganha prioridade se existe, inclusive para runtimes
personalizados. Exportação atualiza somente o config da entrega para o arquivo
efetivamente copiado. Linux continua `RangeRuntime` e Web/Android mantêm seus artefatos.
Descoberta da instalação portátil funciona pela posição dos scripts ao lado da engine,
sem exigir variáveis de ambiente. Hashes de templates antigos permitem usar o launcher
atual no Run/Export sem sobrescrever launchers personalizados ou o projeto original.
