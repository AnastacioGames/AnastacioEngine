# AnastacioEngine 0.5.3

Versão de correções sobre a 0.5.2, com foco nos efeitos do export Web/Android, e a primeira RangeArmor para Linux.

## Correções

- **Sons de efeito:** quando a chuva criava o módulo Effects do World Sound, ele vinha vazio e os outros
  efeitos (explosão, destruição) ficavam mudos. Agora o módulo já vem com os sons da engine, como no
  Add Sound Module.
- **Export Web e Android (WebGL2):** os efeitos que antes não apareciam no navegador agora rodam:
  - partículas de fumaça, fogo e light flicker;
  - chuva com aura em volta da câmera, raios/relâmpagos e máscara de superfície molhada;
  - shaders dos efeitos convertidos para WebGL2, partículas animadas na GPU e saída de cor em float
    conferida antes de usar;
  - cópia da tela sem erro de buffers de desenho, que deixava a imagem preta ou faltando efeito.

## Downloads

- `AnastacioEngine-0.5.3-windows-x64.zip`: editor e runtime para Windows.
- `RangeArmor-0.5.3-windows-x64.zip`: painel de exportação (Windows); exporta jogos para Windows e Linux.
- `AnastacioEngine-0.5.3-linux-x86_64.tar.xz`: editor e runtime para Linux, com as bibliotecas incluídas.
- `RangeArmor-0.5.3-linux-x86_64.tar.xz` (**novo**): o painel da RangeArmor agora também roda no Linux e
  exporta jogos para Linux e Windows. Extraia e abra `RangeArmor Panel`. O painel usa o `python3` do sistema
  para os scripts de exportação; o Set Icons (ícone do `.exe`) precisa do `wine`.
