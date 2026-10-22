# Preparar texturas DDS

Implementação na branch `feat/preparar-texturas-dds`, baseada no plano revisado em 2026-10-22.

## Uso

Salve o projeto e abra **Game > Performance > Prepare Textures (DDS)**. A lista mostra seleção,
dimensões de saída, VRAM atual estimada com mipmaps, estimativa comprimida e DXT1/DXT5 sugerido.
Escolha resolução máxima e qualidade; confirme para converter. Escape interrompe entre imagens.
A imagem em processamento termina antes do cancelamento; conversões anteriores continuam válidas.
Salve o projeto novamente para persistir o mapa de exportação.

Os originais permanecem no editor. Os derivados ficam em `//textures_dds/`, com SHA-256 no nome.
**Revert Prepared Textures** remove o mapa de todas as imagens locais, preservando os arquivos do cache.
Não há troca de imagem no editor nesta versão: isso evita alterações em pintura, referências e packing.

## Contrato da primeira entrega

- Conversor nativo C++ em imbuf, API C `IMB_dds_write_dxt`, RNA `Image.save_dds` e interface Python.
  Exemplo: `image.save_dds(filepath='/destino/cor.dds', format='AUTO', max_size=2048, quality=10)`.
  `max_size=0` mantém dimensões; qualidade aceita 0–18. A API grava uma cópia do buffer atual;
  a ferramenta cria snapshot da fonte para evitar converter pixels antigos após edição externa.
- BC1/DXT1 para alpha inteiramente opaco; BC3/DXT5 para transparência. DXT1 explícito recusa alpha.
  rgbcx v1.12, revisão fixada, licença MIT; modo BC1 ideal, sem uso de transparência para codificar preto.
- Apenas imagens byte, arquivo simples, POT, maiores que 64 pixels, sRGB e usadas exclusivamente em
  entradas conhecidas de cor de materiais. Também aceita o canal alpha junto da cor.
  Dimensões POT são reduzidas por metades, sem aumentar a imagem nem deformar sua proporção.
  Imagens NPOT precisam ser redimensionadas explicitamente antes, com avaliação do autor.
- Normal maps, mapas de dados/usos mistos, fontes bitmap, lightmaps RGBM, HDR/float, animações,
  tiles e multiview ficam de fora. Nomes de normal/lightmap são apenas uma proteção adicional.
  Usos arbitrários por scripts/filtros/UI não podem ser inferidos: o autor deve desmarcar essas imagens.
- Mipmaps completos até 1x1, cor sRGB filtrada em luz linear e ponderada pelo alpha.
  Imbuf byte já normaliza pixels para straight alpha; o DDS exportado usa straight alpha também,
  inclusive para fontes premultiplicadas, evitando diferença entre upload comprimido e fallback.
- Hash inclui bytes efetivos (packed ou externos), interpretação da imagem, opções e versão do encoder/filtro.
  DDS também tem hash próprio e validação do tamanho de cada mip. Imagens com pintura não salva são recusadas.
  A publicação usa arquivo temporário no mesmo volume e substituição somente após sucesso.
  Mudança de fonte durante a conversão aborta; falha preserva a configuração/cache anterior.
- Save As para outra pasta não remapeia custom properties: prepare novamente no novo destino.

## Exportação

O save protegido do export RangeArmor e o exportador de runtime recebem temporariamente cópias DDS
empacotadas, com remapeamento dos usuários das imagens. As imagens originais e seus bytes packed não
são alterados; referências, nomes e fake users são restaurados em `finally`, inclusive após falhas.
Clamp, mapping e display aspect são preservados. O pacote abre sem depender dos PNGs/DDS externos.
Cache selecionado mas obsoleto interrompe o export com diagnóstico; use Prepare ou Revert antes de exportar.
O painel independente RangeArmor continua consumindo o `.rasec` preparado pelo editor.

Bibliotecas linkadas e arquivos usados por `LibLoad` são projetos independentes: preparar/exportar cada
arquivo separadamente. O export principal não reescreve bibliotecas nem percorre scripts para encontrá-los.
Web/Android continuam usando os originais: seus exportadores não entram nesse contexto de remapeamento.
O uso de S3TC no Web depende da plataforma; esta entrega mantém a política de não gerar DDS para Web.

O loader DDS existente ainda descomprime o primeiro nível na CPU e retém RGBA junto dos blocos.
O fator aproximado de 4–8x se refere à textura na GPU, na mesma resolução e com mipmaps equivalentes;
não é uma promessa de redução total de RAM, tempo de load ou aumento de FPS.

## Validação e reprodução

- `tools/tests/validate_prepare_textures_engine.py`: API, orientação, alpha, mipmaps, cache,
  invalidação, preservação após falha e exclusões. Executar no editor em background com `--python-exit-code 1`.
- `tools/debug/cenas/criar_cena_dds.py`: gera fonte, export `.range` e `.rasec`, câmera, Sun,
  cubos RGB/RGBA e sonda de runtime. O player grava propriedades reais das texturas GL em
  `DDS_TEST_OUTPUT` e encerra após doze ticks. Não usa screenshot como evidência visual.
- `ANASTACIO_NO_S3TC=1` força o fallback RGBA8 para validar máquinas sem S3TC.
- Build Windows: `RangeEngine` e `RangeRuntime`, com ambiente de `AGENTS.md`.
- Validação visual pelo usuário no jogo real, medidas RolimaRacer/iGPU e execução Linux continuam
  necessárias antes de afirmar qualidade visual ou ganho de performance nessas condições.

## Próximas fases

BC5 para normais, BC7, conversão em background, suporte mais amplo a grafos e preview reversível no
editor ficam para revisão posterior. Não foi ampliado o formato `.cooked` nesta entrega.

## Valida??o final Windows (2026-10-22)

Bloqueio de link resolvido ap?s fechamento do editor. Build final RangeEngine/RangeRuntime e regress?o completa passaram, incluindo PREMUL. Logs: `build/textures-dds-build-final.log` e `build/dds-validation/native-final.log` (DDS_API_VALIDATED, exit code 0). Visual real, benchmark e Linux/iGPU permanecem pendentes.

Usuario confirmou visualmente o alpha da textura de teste em 2026-10-22. Validacao no jogo real e benchmarks seguem pendentes.
