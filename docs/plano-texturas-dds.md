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
- BC5/ATI2 (2026-11-05) para normal maps tangent-space: só X/Y, mipmaps renormalizados, Z reconstruído no shader.
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
Web (2026-11-05): o Export Web também grava a cópia do jogo com as texturas preparadas em DDS. O navegador de
desktop sobe os blocos S3TC direto (`WEBGL_compressed_texture_s3tc`, log "DDS: WebGL S3TC on"); celular e
Android WebView, sem a extensão, descomprimem para RGBA no load. Conferido no Edge com a cena `criar_cena_dds.py`.
BC5 na Web (2026-11-05): normal maps sobem como RGTC2 quando há `EXT_texture_compression_rgtc`
(log "DDS: WebGL RGTC on"); sem a extensão, descomprimem com Z reconstruído. Conferido no Edge.

O loader DDS existente ainda descomprime o primeiro nível na CPU e retém RGBA junto dos blocos.
O fator aproximado de 4–8x se refere à textura na GPU, na mesma resolução e com mipmaps equivalentes;
não é uma promessa de redução total de RAM, tempo de load ou aumento de FPS.

## KTX2 / Basis Universal (Web e Android)

Implementado em 2026-11-05. A biblioteca Basis Universal (revisão 073eb6a0, Apache-2.0) fica em
`source/extern/basis_universal`, com licença em `release/text/basisu-license.txt`.

- **Arquivo:** um só, que vira no load o formato que a GPU aceita, nesta ordem: BC (navegador de desktop),
  ETC2/EAC (celular) e ASTC 4x4. Sem nenhum desses formatos, vira RGBA.
- **Formatos:**
  - Cores usam ETC1S. A conversão para ETC1/ETC2 não perde nada, e o arquivo é pequeno.
  - Normal maps tangent-space usam UASTC, com X no RGB e Y no alpha. Elas viram BC5 ou EAC RG11, e o
    shader reconstrói Z como no BC5 do DDS.
  - Normal map só com ASTC disponível vira RGBA: o WebGL não tem swizzle de textura.
- **Encoder:** `Image.save_ktx2(filepath, normal, max_size, quality=0-100, srgb)`. Usa os mesmos mipmaps
  do DDS (luz linear, alpha ponderado, normais renormalizadas). Só existe nos builds de desktop; o
  `.wasm` leva apenas o transcodificador (+0,9 MB, de 23,7 para 24,6 MB).
- **Loader:** imbuf (`ktx2_api.cpp`) converte para o mesmo `DDSData` do DDS, então o upload é o mesmo.
  Com `IB_dds_blocks`, ficam só os blocos e uma cópia do KTX2, de onde os pixels são decodificados se
  algo pedir. Linhas na ordem do ImBuf (de baixo para cima), sem flip no load.
- **Export Web:** Web > Export > **Prepared textures** = KTX2 (padrão) ou DDS. O KTX2 sai das imagens já
  preparadas (Prepare Textures), com a mesma elegibilidade e tamanho máximo, e fica em cache por hash em
  `//textures_ktx2/`.
- **Testes:**
  - `ANASTACIO_KTX2_TARGET=bc|etc2|astc|rgba` limita os formatos para testar.
  - `tools/debug/cenas/criar_cena_ktx2.py` monta a cena KTX2 a partir da cena DDS.
  - Sonda no player Windows:
    - BC: 33777, 33779 e 36285.
    - ETC2: 37492, 37496 e 37490.
    - RGBA: 32856.
    - Mip 1 presente e `gl_error` 0 em todos.
  - No Edge, o pacote Web passou nos caminhos BC, ETC2, ASTC e RGBA.
- **Pendente:**
  - aceite visual;
  - celular real (Android WebView, ETC2/ASTC);
  - medidas de VRAM e de tempo de transcodificação;
  - build Linux.

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

BC7, conversão em background, suporte mais amplo a grafos e preview reversível no
editor ficam para revisão posterior. Não foi ampliado o formato `.cooked` nesta entrega.

## Valida??o final Windows (2026-10-22)

Bloqueio de link resolvido ap?s fechamento do editor. Build final RangeEngine/RangeRuntime e regress?o completa passaram, incluindo PREMUL. Logs: `build/textures-dds-build-final.log` e `build/dds-validation/native-final.log` (DDS_API_VALIDATED, exit code 0). Visual real, benchmark e Linux/iGPU permanecem pendentes.

Usuario confirmou visualmente o alpha da textura de teste em 2026-10-22. Validacao no jogo real e benchmarks seguem pendentes.
