# AnastacioEngine 0.5.3

Versão de correções sobre a 0.5.2.

## Correções

- **Sons de efeito:** quando a chuva criava o módulo Effects do World Sound, ele vinha vazio e os outros
  efeitos (explosão, destruição) ficavam mudos. Agora o módulo já vem com os sons da engine, como no
  Add Sound Module.
- **Export Web e Android:** as partículas (fumaça, fogo, light flicker) e a chuva agora funcionam no WebGL2.

## Downloads

- `AnastacioEngine-0.5.3-windows-x64.zip`: editor e runtime para Windows.
- `RangeArmor-0.5.3-windows-x64.zip`: painel de exportação (Windows); exporta jogos para Windows e Linux.
- `AnastacioEngine-0.5.3-linux-x86_64.tar.xz`: editor e runtime para Linux, com as bibliotecas incluídas.
- `RangeArmor-0.5.3-linux-x86_64.tar.xz` (**novo**): o painel da RangeArmor agora também roda no Linux e
  exporta jogos para Linux e Windows. Extraia e abra `RangeArmor Panel`. O painel usa o `python3` do sistema
  para os scripts de exportação; o Set Icons (ícone do `.exe`) precisa do `wine`.
