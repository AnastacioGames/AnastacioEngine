# AnastacioEngine 0.6.1

Versão de ajuste depois da 0.6.0: tempo de jogo mais estável (inclusive no Wine), movimento liso no
Fixed Timestep e menos custo de GPU em placas integradas.

## Novidades

- **Fixed Timestep suave:** o desenho agora é interpolado entre os passos de lógica. Quando o PC desenha num
  ritmo diferente do jogo, a imagem continua lisa em vez de "tremer" (num teste a ~33 fps a variação do
  movimento por quadro caiu de 18,7% para 0,6%). Objetos teleportados (mais de 10 m num passo) não são
  suavizados. Para comparar, abra com `RANGE_NO_INTERP=1`.
- **Fixed Timestep ligado por padrão em cenas novas.** Os jogos que já existem mantêm a opção como estava.
  No modo antigo (legacy), um PC que desenha abaixo da taxa de lógica deixa o jogo em câmera lenta; se o seu
  jogo sofre com isso, ligue **Fixed Timestep** nas propriedades da cena.
- **Espera entre quadros no estilo spin/sleep** (ideia do Kitsuy): parte do tempo esperando ativo, parte
  dormindo, e só giro puro no final. A engine mede ao abrir a precisão do sleep do sistema, então o tempo
  fica certo também no Wine e com o timer de 15 ms do Windows.
- **Qualidade do lens flare e das estrelas** (Low/Medium/High) no World, com o sol do flare escolhido entre as
  Lamps da cena. O Quality Preset ajusta as duas junto com o resto.
- **Céu e lens flare mais leves em GPUs integradas.** A cena inicial e os Worlds novos começam sem lens flare,
  lua e estrelas realistas (custavam muito por pixel: uma cena vazia rodava a ~10 fps numa Intel HD 4400);
  ligue no World quando quiser.
- **Performance Report:** simulador de PC fraco (GPU até 32x mais lenta), tempo de GPU por etapa do desenho,
  céu como etapa própria com dica do que custa, selo de PC antigo e menu Performance em submenus.

## Correções

- Troca de cena no modo online carrega a cena nova como fundo, então o World dela aparece.
- Shaders das cenas convertidas são recarregados quando o clarão de explosão libera materiais (sem objetos
  sem material depois de uma explosão).
- UI Tree: Auto Arrange mantém o layout da tela e só organiza os nós de ação.
- Web: botões de toque do topo abaixo do botão Controls e do notch; botão de tela cheia respeita o notch;
  tela de carregamento e relatório mostram a GPU do WebGL.
- **Gravação de tela (Rec):** o codificador de vídeo usava só um núcleo, e o vídeo gravado saía com ~7 fps.
  Agora usa vários núcleos e o preset rápido de verdade: no RolimaRacer (1280x720) o vídeo foi de ~7 para
  ~48 fps (136 ms → ~20 ms por quadro). Vale também para o render de vídeo do editor.
- Interface traduzida (pt_BR, es, ru) para as opções novas de lens flare e estrelas.

## Downloads

- `AnastacioEngine-0.6.1-windows-x64.zip`: editor e runtime para Windows, portátil (extraia e rode).
- `RangeArmor-0.6.1-windows-x64.zip`: ferramenta para criar e empacotar projetos (Windows).
- `AnastacioEngine-0.6.1-linux-x86_64.tar.xz`: editor e runtime, portátil, com as bibliotecas incluídas.
- `RangeArmor-0.6.1-linux-x86_64.tar.xz`: ferramenta para criar e empacotar projetos (Linux).
- `SHA256SUMS.txt`: hashes para conferir o download.

No Windows: extraia e abra `AnastacioEngine.exe`.

No Linux: extraia, abra `AnastacioEngine` e, se quiser o ícone no menu, rode `./install-desktop.sh`.
