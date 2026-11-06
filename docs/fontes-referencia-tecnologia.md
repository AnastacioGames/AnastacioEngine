# Fontes de referência em tecnologia: as melhores empresas e o que serve à Anastacio

Levantamento de 2026-11-04. Reúne as empresas e equipes que publicam código aberto de alto nível em
gráficos, física, animação, texturas e ferramentas, e diz o que cada uma pode oferecer à Anastacio.
**Só pesquisa:** nada foi baixado para o build, integrado ou medido. Cada candidato a trazer ou adaptar
precisa de uma cena de teste controlada e de aprovação ([plano-processamento.md](plano-processamento.md)).

Critérios para entrar na lista: código público mantido pela empresa ou pelo autor, revisão registrada,
licença conferida no repositório e utilidade avaliada para o que a engine usa hoje (OpenGL 3.3+ no
desktop, WebGL2/GLSL ES 3.00 na Web e no Android). A licença aparece como dado de cada fonte; uma
eventual inclusão tem de ser conferida caso a caso, sem mudar a licença do projeto.

Revisões, datas e licenças conferidas pela API do GitHub em `artifacts/fontes-referencia/repos.tsv`.

Classificação:

- **Trazer:** biblioteca ou arquivo que pode entrar quase como está.
- **Adaptar:** o método serve, mas o código está em outra API (DX12, Vulkan, compute) ou outra estrutura.
- **Estudar:** referência de projeto, sem caminho direto.
- **Não serve:** exige hardware, API ou licença incompatível com a engine.

## Ponto de partida: a novidade do DirectX

Em 28/10/2026 a Microsoft publicou o Agility SDK 1.722 (prévia), com Clustered Geometry (CLAS) e
Partitioned TLAS (PTLAS). No teste da Microsoft numa Radeon RX 9070, a memória das estruturas de
aceleração caiu de 7.519 MiB para 774 MiB. A economia vale só para as estruturas de ray tracing do
DirectX 12, não para texturas e malhas, e exige mais memória temporária na construção
([Notebookcheck](https://www.notebookcheck.net/Microsoft-DirectX-12-update-slashes-ray-tracing-VRAM-usage-by-90.1439999.0.html),
[igor'sLAB](https://www.igorslab.de/en/directx-raytracing-lower-memory-usage-complex-scenes/),
[eTeknix](https://www.eteknix.com/microsoft-unveils-major-directx-raytracing-update-with-massive-vram-savings/)).
A Anastacio não usa DX12 nem ray tracing; a análise do que se aproveita está em
[analise-directx-clusters-ptlas.md](analise-directx-clusters-ptlas.md) e
[revisao-directx-claude.md](revisao-directx-claude.md). A pergunta seguinte, respondida aqui, é onde
encontrar código desse nível que **se aplique** à engine.

## Mapa das fontes

| Empresa | Repositório | Revisão | Licença | O que tem de melhor | Para a Anastacio |
|---|---|---|---|---|---|
| Microsoft | [DirectX-Graphics-Samples](https://github.com/microsoft/DirectX-Graphics-Samples) | `68a2b1e9` | MIT | Exemplos oficiais do DX12: DXR, CLAS/PTLAS, mesh shaders, sampler feedback | Estudar (ideias de atualização parcial já analisadas) |
| Microsoft | [DirectX-Specs](https://github.com/microsoft/DirectX-Specs) | `2808d210` | CC-BY-4.0 | Especificação completa do DX12 | Estudar |
| Microsoft | [DirectXTex](https://github.com/microsoft/DirectXTex) | `c0cb9776` | MIT | Referência em compressão BC1–BC7, mipmaps, normal maps (BC5) | **Adaptar:** normal maps em BC5 no "Prepare Textures (DDS)" |
| Microsoft | [DirectXMath](https://github.com/microsoft/DirectXMath) | `d400b652` | MIT | Matemática SIMD (SSE/AVX/NEON) só em headers | Estudar: padrão para SIMD portátil |
| Microsoft | [DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler) | `ea348910` | LLVM/NCSA | Compilador HLSL → DXIL/SPIR-V | Não serve hoje (shaders são GLSL) |
| AMD | [FidelityFX-FSR](https://github.com/GPUOpen-Effects/FidelityFX-FSR) (FSR 1) | `a21ffb8f` | MIT | Upscaling espacial (EASU) + nitidez (RCAS) num shader de pixel, com caminho GLSL (`A_GLSL`) | **Adaptar:** subir a imagem da resolução dinâmica |
| AMD | [FidelityFX-CAS](https://github.com/GPUOpen-Effects/FidelityFX-CAS) | `9fabcc9a` | MIT | Nitidez adaptativa barata | **Adaptar:** filtro de nitidez/escala |
| AMD | [FidelityFX-CACAO](https://github.com/GPUOpen-Effects/FidelityFX-CACAO) | `0ddca95e` | MIT | AO adaptativo em compute | Estudar (compute não existe no WebGL2) |
| AMD | [FidelityFX SDK / FSR SDK 2.4](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK) | `7539ae8b` | ver `3rdpartynotice.md` | FSR 2/3/4, frame generation, efeitos novos | Não serve hoje: só DX12/Vulkan |
| AMD | [Compressonator](https://github.com/GPUOpen-Tools/compressonator) | `095a143a` | MIT (readme) | Compressão e análise de qualidade de texturas | Estudar (ferramenta de comparação de qualidade) |
| AMD | [VulkanMemoryAllocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator) | `0f1a757d` | MIT | Gerência de memória de GPU | Estudar só se houver backend Vulkan |
| NVIDIA | [PhysX 5](https://github.com/NVIDIA-Omniverse/PhysX) | `b97365c6` | BSD-3 | Física de produção, CPU e GPU | Estudar; não substituir o Bullet |
| NVIDIA | [NVRHI](https://github.com/NVIDIA-RTX/NVRHI) | `bf0bbd9b` | MIT | Camada sobre DX11/DX12/Vulkan | Estudar só se houver backend novo |
| NVIDIA | [RTXNTC](https://github.com/NVIDIA-RTX/RTXNTC) | `8311b54b` | licença própria NVIDIA | Compressão neural de texturas | Não serve: exige hardware/API recentes e licença própria |
| Intel | [XeGTAO](https://github.com/GameTechDev/XeGTAO) | `a5b1686c` | MIT | GTAO de alta qualidade com filtro de ruído | **Adaptar** para shader de pixel (o original é compute) |
| Intel | [XeSS](https://github.com/intel/xess) | `de0fb9c1` | licença própria | Upscaling com IA | Não serve: DX11/DX12/Vulkan |
| Google | [Filament](https://github.com/google/filament) | `f868cc11` | Apache-2.0 | Renderizador PBR com OpenGL/GLES/WebGL e documentação de física de luz exemplar | **Estudar** (a engine já usa a fórmula de multiscatter dele) |
| Google | [ANGLE](https://github.com/google/angle) | `9bb53668` | BSD-3 | Camada que executa o WebGL do Chrome (sobre D3D11 no Windows) | Estudar: explica o desempenho da build Web |
| Khronos | [KTX-Software](https://github.com/KhronosGroup/KTX-Software) | `93cdb1d0` | Apache-2.0 (e outras, ver LICENSE) | Formato e ferramentas KTX2 | **Trazer** junto com o Basis |
| Binomial (Khronos) | [basis_universal](https://github.com/BinomialLLC/basis_universal) | `073eb6a0` | Apache-2.0 | Textura única que vira BC, ETC2 ou ASTC no aparelho | **Trazer:** texturas comprimidas na Web/Android |
| Khronos | [Vulkan-Samples](https://github.com/KhronosGroup/Vulkan-Samples) | `56a72bd1` | Apache-2.0 | Boas práticas de GPU, inclusive móvel | Estudar |
| Khronos | [glTF-Sample-Assets](https://github.com/KhronosGroup/glTF-Sample-Assets) | `8f492390` | por arquivo | Modelos de referência para testes de material | Estudar: base de cenas de teste |
| Arm | [astc-encoder](https://github.com/ARM-software/astc-encoder) | `b26bfead` | Apache-2.0 | Compressor ASTC oficial | Trazer só se o Basis não bastar |
| Arm | [opengl-es-sdk-for-android](https://github.com/ARM-software/opengl-es-sdk-for-android) | `c3caf759` | ver LICENSE | Exemplos GLES para GPU de celular (tile-based) | Estudar: Android |
| Godot Foundation | [Godot](https://github.com/godotengine/godot) | `bf194eb5` | MIT | Renderizador "Compatibility" em GLES3/WebGL2, as mesmas restrições da Anastacio | **Estudar** (a referência mais próxima) |
| Linux Foundation | [O3DE](https://github.com/o3de/o3de) | `19c096e5` | Apache-2.0 ou MIT | Engine AAA aberta (origem Amazon) | Estudar |
| Blender Foundation | [Blender](https://github.com/blender/blender) | `6f4fc760` | GPL | Mesma origem do código da engine (2.79) | **Adaptar:** correções e otimizações posteriores a 2.79 |
| UPBGE | [UPBGE](https://github.com/UPBGE/upbge) | `63f69c70` | GPL | Sucessor do BGE sobre Blender 2.8+ | Estudar: mesmas APIs de jogo |
| Bullet | [bullet3](https://github.com/bulletphysics/bullet3) | `d3afe761` | zlib | Física usada pela engine (aqui 2.84) | Adaptar correções pontuais |
| Jolt (Guerrilla) | [JoltPhysics](https://github.com/jrouwe/JoltPhysics) | `0f69a6b8` | MIT | Física de Horizon Forbidden West | Estudar (ver [estudo](estudo-modernizacao-processamento.md)) |
| Erin Catto | [Box2D v3](https://github.com/erincatto/box2d) | `dd8bd3fb` | MIT | Solver com SIMD e grafo de cores | Estudar (técnicas de solver) |
| Nicholas Frechette | [ACL](https://github.com/nfrechette/acl) | `3ee56854` | MIT | Compressão de animação usada na Unreal | Estudar: melhor referência que o ozz para clips compactos |
| ozz | [ozz-animation](https://github.com/guillaumeblanc/ozz-animation) | `744eb9d9` | MIT | Amostragem SoA de animação | Estudar |
| zeux | [meshoptimizer](https://github.com/zeux/meshoptimizer) | `f0a684f1` | MIT | Otimização e compressão de malhas | Etapa 4 do [plano](plano-processamento.md) |
| Bartosz Taudul | [Tracy](https://github.com/wolfpld/tracy) | `3dced9c2` | BSD-3 | Profiler de CPU e GPU (inclui OpenGL), usado na indústria | Estudar contra o Range Trace e o amostrador |

## O que podemos trazer ou adaptar, comparado com a engine

A coluna "Hoje na engine" foi conferida no código desta árvore.

| # | Técnica e fonte | Hoje na engine | Por que pode valer | Cuidados | Classe |
|---|---|---|---|---|---|
| 1 | **Texturas KTX2/Basis Universal** (Khronos, Binomial) | Web/Android usam as imagens originais sem compressão; o DDS (BC1/BC3) é só desktop ([plano-texturas-dds.md](plano-texturas-dds.md)). GPUs de celular não leem BC | Textura comprimida na VRAM do celular e do navegador; um arquivo só para BC, ETC2 e ASTC | Tamanho do transcodificador no `.wasm`; tempo de transcodificação no carregamento; qualidade ETC1S x UASTC; os números de "4–8x" achados são de fornecedores, não medidos | Trazer |
| 2 | **FSR 1 (EASU + RCAS) / CAS** (AMD) | Resolução dinâmica existe (`m_dynamicResolution*` em `KX_KetsjiEngine`); o filtro que sobe a imagem ainda precisa ser conferido. A iGPU é limitada pela GPU | Mesmo custo de pixel com imagem mais nítida, ou resolução menor com a mesma nitidez | O EASU usa `textureGather`, que existe no GLSL do desktop (a engine já usa em `gpu_shader_material.glsl`), mas não no GLSL ES 3.00 do WebGL2: a Web precisa de uma variante com leituras simples. Comparar com a imagem atual | Adaptar |
| 3 | **Normal maps em BC5** (DirectXTex) | "Prepare Textures (DDS)" exclui normal maps; o leitor DDS já reconhece BC4/BC5 (`DirectDrawSurface.cpp`) | Normal maps são grandes e hoje ficam sem compressão | Reconstruir Z no shader; conferir todos os nós que leem normal map | Adaptar |
| 4 | **XeGTAO** (Intel) | SSAO próprio (`gpu_shader_fx_ssao_frag.glsl`); granulado no SSAO está pendente | AO de qualidade de referência e filtro de ruído | Original em compute/HLSL; precisa virar shader de pixel em várias passadas para valer no WebGL2 | Adaptar |
| 5 | **Formatos de vértice compactos** (Filament, meshoptimizer) | Todos os atributos em float32: posição 12 B, normal 12, tangente 16, UV 8, ossos 16 + pesos 16 (`RAS_StorageVao.cpp`) | Normal+tangente em 8 B e ossos/pesos em 8 B cortariam ~40–60% do buffer de vértices de malhas com skinning | WebGL2 aceita `INT_2_10_10_10_REV` e half float; todos os shaders e o GPU Skinning leem esses atributos. Estimativa, sem medição | Estudar → adaptar |
| 6 | **Tracy** | Range Trace, profiler por categoria e amostrador próprio | Linha do tempo de CPU e GPU por thread, útil para as esperas entre os três pools de threads | Ferramenta só de desenvolvimento; não deve entrar no runtime publicado | Estudar |
| 7 | **Blender pós-2.79 e UPBGE** | Engine derivada do Blender 2.79 | Mesma base de código: correções de animação, avaliação de curvas e GPU já resolvidas lá | Arquitetura do 2.8+ (depsgraph, draw manager) é outra; trazer só peças isoladas | Adaptar |
| 8 | **ACL** | Avaliação de fcurves do Blender por quadro | Formato compacto de clips, usado em produção | Mesmo limite do ozz: não reproduz Bézier, IK e NLA | Estudar |
| 9 | **Godot Compatibility e Filament** | Renderizador próprio em GL 3.3/WebGL2 | Mostram como engines maduras resolvem sombras, PBR e pós-processamento dentro das mesmas restrições | Arquitetura diferente; copiar ideias, não estruturas | Estudar |
| 10 | **Guias de GPU móvel** (Arm, Khronos) | Nenhuma chamada a `glInvalidateFramebuffer` no código | GPUs de celular (tile-based) economizam banda quando o conteúdo descartado é avisado | Benefício só no Android/WebView; medir em aparelho | Adaptar |

Descartados como integração: FSR 2/3/4, XeSS, NVIDIA RTXNTC, recursos novos do DirectX (DX12/Vulkan,
hardware novo ou licença própria); PhysX ou Jolt no lugar do Bullet; NVRHI ou VMA sem backend novo.

## Onde acompanhar as próximas novidades

Fontes primárias das próprias empresas e equipes, para consultar antes de cada estudo:

- [DirectX Developer Blog](https://devblogs.microsoft.com/directx/) — Microsoft; anúncios como o CLAS/PTLAS.
- [GPUOpen](https://gpuopen.com/) — AMD; artigos de técnica com código MIT.
- [NVIDIA Developer](https://developer.nvidia.com/) e [NVIDIA-RTX no GitHub](https://github.com/NVIDIA-RTX).
- [Intel GameTechDev no GitHub](https://github.com/GameTechDev).
- [Khronos](https://www.khronos.org/) — padrões OpenGL, WebGL, KTX, glTF.
- [Arm Developer](https://developer.arm.com/) — boas práticas de GPU móvel.
- [Advances in Real-Time Rendering (SIGGRAPH)](https://advances.realtimerendering.com/) — palestras dos grandes estúdios.
- [GDC Vault](https://gdcvault.com/) e [JCGT](https://jcgt.org/) — palestras e artigos com código.

## Próximos passos (para aprovar)

Seguem a regra do plano: cena de teste controlada, gerada por script, nunca o jogo.

1. **KTX2/Basis na Web:** cena com N texturas de tamanhos fixos; medir VRAM estimada, tamanho do pacote,
   tempo de carregamento e custo de transcodificação no Chrome e no WebView, original x KTX2.
2. **FSR 1/CAS na resolução dinâmica:** conferir primeiro como a imagem é ampliada hoje; depois uma cena com
   padrões de teste (texto, bordas, grade) em escalas 0,5/0,67/0,75, comparando nitidez e ms de GPU no
   simulador de PC fraco (`RANGE_WEAK_GPU`).
3. **Normal maps BC5:** cena com normal maps conhecidos; diferença de imagem e memória contra o original.

Os demais itens ficam como estudo até haver um problema medido que eles resolvam.
