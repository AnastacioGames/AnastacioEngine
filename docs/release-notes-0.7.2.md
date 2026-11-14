# AnastacioEngine 0.7.2

Versão focada em aprender a engine por dentro dela: tutoriais interativos em português, inglês e espanhol, botão
Help nos painéis, o novo editor Mind Map e várias melhorias de shader, TAA, Web e carregamento.

## Novidades

### Tutoriais e ajuda

- **Tutoriais dentro da engine** (About > Tutorials): 38 tutoriais com cartão por janela, destaque do botão certo,
  cartão de concluído e check verde no menu. Cobrem do básico (interface, primeiro jogo, Logic Bricks, export) a
  Cutscene, Minimap, Material Atlas, céu, chuva e névoa, Compositing, Light Probe Volume, SSGI, Occlusion Culling,
  Video Player, microfone, Character com postura e Nodes GLSL. Idiomas: pt, en e es.
- **Botão Help** no cabeçalho: liga um "i" nos painéis que abre a explicação do painel e o tutorial dele.

### Mind Map

- Área nova para mapas mentais: lê e grava `.mm`, edição por teclado e mouse, vínculos, tarefas, ícones da engine,
  busca, copiar/recortar/colar ramos, exportar PNG e barra de botões por etapa.

### Gráficos

- **Nodes GLSL por arquivo:** cabeçalho `@input/@param/@output`, Add > GLSL Library, `@shading`, `@surface`
  (triplanar), `in_x(uv)`, parâmetros `image` e `meshmap`, Node Groups e presets de material como `.json`.
- **Meshmap bake** (painel GLSL Mesh Maps): AO, curvatura, espessura, normal e posição da malha.
- **TAA etapa 2:** movimento por objeto e GPU Skinning. **TAAU** (upscaling temporal) com modos
  Off/Quality/Balanced/Performance na cena e `filterManager.taaUpscale`.
- **Bake Probes:** botão no painel Light Probe Volume captura a luz de todos os volumes e salva `<cena>.probes`,
  que vai no pacote exportado.
- **Material:** IOR, Turbidity e SSS ajustam ao vivo, sem recompilar. Material Atlas ganhou modo Auto com paleta.
- **Build HLOD:** método Sloppy (meshoptimizer), 2,2x mais rápido; triângulos na ordem do cache de vértices.

### Áudio e lógica

- Microfone com reconhecimento de notas (YIN) e Tuner na UI Tree; eventos clicáveis na UI Tree.
- Animações rodam depois da lógica, como na BGE/UPBGE.
- Constantes `KX_MOUSESENSORMODE_*` no Python.

### Carregamento

- Aquecimento de shaders inclui os arquivos de LibLoad listados em `<jogo>.warmup` (no teste com 20 veículos o
  LibLoad caiu de 24 s para 1,8 s). O export copia o `.warmup` ao lado do executável.

### Web e celular

- Export leva os sons do World Sound e aceita módulos de `scripts/modules`.
- Contexto WebGL perdido mostra aviso e botão Recarregar página; ESC não congela mais a tela.
- GPU Skinning calcula o limite de ossos pelo aparelho (rig maior cai para CPU).
- Projetos com centenas de arquivos extras exportam no Windows (lista em arquivo).

## Correções

- Mipmaps com cores erradas na Web.
- Cutscene: Stop e Skip desligam a animação que o Take começou.
- Crash ao arrastar miniatura rápido no Rec Studio.
- P no editor: jogo aberto por `startGame` usa a própria câmera.
- `gpu.export_shader` sem janela dá erro claro em vez de crash.
- Lightmap UV: n-gon côncavo não cai mais sobre outras ilhas.

## Downloads

- Windows: `AnastacioEngine-0.7.2-windows-x64.zip`
- Linux: `AnastacioEngine-0.7.2-linux-x86_64.tar.xz` (Ubuntu 22.04 ou mais novo; inclui o runtime Web)
- RangeArmor: `RangeArmor-0.7.2-windows-x64.zip` e `RangeArmor-0.7.2-linux-x86_64.tar.xz`

Confira os arquivos com `SHA256SUMS.txt`.
