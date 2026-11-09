# AnastacioEngine 0.7.1

Versão de correções da 0.7.0: o Export Web volta a funcionar em projetos com nomes de arquivo comuns, e ajustar
luzes e materiais no editor ficou instantâneo.

## Correções

### Export Web

- **Arquivos com espaço ou acento no nome** (ex.: `3rd person.range` carregado por LibLoad) não cancelam mais o
  export com "nome de arquivo extra invalido". Nomes com `#` e `%` também funcionam.
- **Cenas sem cutscene** em arquivos antigos não derrubam mais o export com erro de Python.
- **Pasta de scripts sem `__init__.py`** e os módulos antigos `Rasterizer`, `GameLogic`, `GameKeys`, `GameTypes` e
  `PhysicsConstraints` não bloqueiam mais o export como "import não resolvido".
- **Cache do navegador:** cada export ganha uma versão própria, então o navegador não mistura arquivos de um
  export antigo com o novo.

### Python

- `KX_Camera.boxInsideFrustum` aceita um `KX_GameObject` (usa a caixa no mundo), e os testes de frustum dão o
  resultado certo já antes do primeiro quadro desenhado.

## Melhorias

- **Editor mais rápido ao ajustar luz e material:** mudar Distance, Energy, Color, Sphere, sombra, Spot, valores do
  World/névoa, Diffuse, Specular, Alpha, Emit, Hardness e os fatores dos slots de textura só redesenha a tela, sem
  recompilar shaders. O jogo continua com os shaders otimizados de sempre.

## Downloads

- Windows: `AnastacioEngine-0.7.1-windows-x64.zip`
- Linux: `AnastacioEngine-0.7.1-linux-x86_64.tar.xz` (Ubuntu 22.04 ou mais novo; inclui o runtime Web)
- RangeArmor: `RangeArmor-0.7.1-windows-x64.zip` e `RangeArmor-0.7.1-linux-x86_64.tar.xz`

Confira os arquivos com `SHA256SUMS.txt`.
