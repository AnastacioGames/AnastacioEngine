# Energia e clearcoat da Principled BSDF

Referência numérica e cenas para o plano de energia da branch `bsdf-energia`.
O trabalho do Codex cobre o integrador, as cenas e a análise do cache. A integração
do shader e os builds desktop/Web pertencem às fases L1–L4 do plano.

## Base

Medição de ms/frame **pendente**. O plano impede abrir o jogo/janela, enquanto
`--server` desativa a renderização: esse modo não fornece uma base de GPU válida.
Não há números estimados apresentados como medição. Usar o
[Performance Report](performance-report.md) em execução renderizada antes de F1/F2,
na cena de teste e em `D:/ProjetoRolimaRacer/RolimaRacer.range`, por aproximadamente
10 segundos, com iGPU real e com `RANGE_WEAK_GPU=16`. O simulador não identifica nem
substitui uma iGPU física; conferir o renderer no log.

| Cena | iGPU real | Simulador 16× |
|---|---|---|
| BSDF furnace/sol/HDRI/clearcoat | Pendente | Pendente |
| RolimaRacer | Pendente | Pendente |

O gerador [bsdf_energia.py](../tools/debug/cenas/bsdf_energia.py) produz em
`artifacts/bsdf-energia/cenas/` seis arquivos: furnace, sun, hdri_ssgi, clearcoat,
lightmap_ao e lightmap_indirect. As duas últimas são bakes reais CPU, atlas 256×256,
8 amostras. O HDRI de estúdio é linear, sintético, salvo como OpenEXR e empacotado
nos arquivos, sem dependência de imagens externas.

```powershell
& .\build\bin\AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/bsdf_energia.py -- D:/AnastacioEngine/artifacts/bsdf-energia/cenas
& .\build\bin\AnastacioEngine.exe -b artifacts/bsdf-energia/cenas/bsdf_clearcoat.range --python tools/debug/cenas/bsdf_energia.py -- D:/AnastacioEngine/artifacts/bsdf-energia/cenas inspect
```

Cada cena foi reaberta em background; as seis inspeções JSON verificaram câmera,
materiais Principled ligados ao output, Distribution, controlador Python e, quando
aplicável, imagem de bake empacotada e UV Lightmap. O clearcoat tem 24 esferas:
pesos 0/0,5/1 × roughness 0/0,1/0,5/1 × normal padrão/própria. As demais têm
roughness 0,1/0,35/0,65/1 × metallic 0/0,5/1 × GGX/Multiscatter.

`BSDF_SECONDS` e `BSDF_LOG` permitem encerrar o player e gravar evidência de execução.
Em `--server`, essa evidência valida apenas a lógica. A aparência requer aceite do
usuário com janela. Não foram feitas capturas automáticas como prova visual.

As seis cenas também executaram no player `--server`, encerrando automaticamente
após aproximadamente um segundo e gravando entre 61 e 63 frames de lógica nos
JSON `artifacts/bsdf-energia/runtime-*.json`. Isso não valida os shaders no driver.
SHA256 dos executáveis usados nesta preparação:

- Editor: `B61E0D731B559084871F853462562AD326F3A4887F2343B45AF163532361311F`.
- Player: `C3DF0EDA9B1A2D75B1D74FDAD0E71967EF6591CF9C771027A3739E8DAF9119C7`.

## F0: referência numérica

O [integrador](../tools/debug/bsdf/integrar_brdf.py) usa numpy. A geração usa
Hammersley e amostragem por importância de `D(H)·NdotH`. A referência independente
usa quadratura Gauss-Legendre em `log(tan(theta_H))` e azimute uniforme, dobrando
ambas as resoluções até variação relativa menor que 0,1% (piso absoluto de 1e-8).
Para cada canal, a condição exata é
`abs(atual-anterior) < max(0,001*abs(atual), 1e-8)`.
O antigo denominador `max(abs(atual), 1e-5)`, comparado com 0,001,
era matematicamente equivalente; agora as duas tolerâncias estão explícitas no
script e em `report.json`. O piso de erro absoluto é **1e-8**.

Na transformação para half-vector, `dOmega_L = 4·VdotH·dOmega_H`; o fator inverso
`1/(4·VdotH)` pertence à transformação da **densidade de probabilidade**. Confundir
as duas medidas produz uma integral incorreta. A malha logarítmica resolve o núcleo
estreito e a cauda da GTR1 sem usar a CDF da geração da LUT.

Contrato: linha = roughness, coluna = NdotV, centros de células. RGBA = A/B do
ambiente, Ecc com Fresnel exato IOR 1,5 e zero reservado (v3.2). Os resultados passam por float16
antes da interpolação bilinear, incluindo o arredondamento do armazenamento GPU.
A rugosidade de entrada é a posterior ao specular AA.

- Ambiente: GTR2 isotrópica, `a=max(r,0.1)^2`, Smith com `g=a`.
- Luzes: mesma D, Smith com `g=(0.5r+0.5)^2`. A v3.2 usa o fator de Ess_env
  também nas luzes; isso não normaliza a energia do lóbulo com hotness.
- Verniz: GTR1 com `a=max(cc_rough^2,0.001)`, Smith com `g=0.25`, Fresnel exato.
  Ecc não inclui o peso externo `0.25·clearcoat`.

```powershell
python tools/debug/bsdf/integrar_brdf.py
```

### Resultado em 2026-10-29

**C1 liberou o header numérico 64×64 no contrato v3.2.** RGBA = A/B/Ecc/0,
32 KiB em RGBA16F. Passou nos 30 pontos, enquanto 32×32 passou em 27/30.
O furnace das luzes deixou de ser critério: o plano retirou Ess_lit da textura
e adotou um fator único de Ess_env. Schlick no ambiente foi aceito como aproximação.
A avaliação anterior, que normalizava as luzes separadamente, reprovava ambas.

A geração usou 131.072 amostras por texel. `lut_32.npy` e `lut_64.npy` preservam
os quatro canais de diagnóstico; a exportação C zera o alfa reservado.
`report.json` registra critérios e medidas; `v32-validation.log`, a execução aprovada.

Foram conferidos 30 pontos: NdotV 0,01/0,05/0,173/0,527/0,931/1 × roughness
0/0,1/0,237/0,673/1. A comparação inclui interpolação e float16.

| Grade uniforme | Pontos aprovados | Máx. erro absoluto Ess_env | Máx. erro Ecc | Máx. desvio furnace ambiente | Máx. desvio furnace luzes |
|---|---:|---:|---:|---:|---:|
| 32×32 | 27/30 | 0,018392 | 0,009590 | 5,655% | 34,373% |
| 64×64 | 30/30 | 0,009106 | 0,000845 | 2,882% | 7,349% |

A última coluna é diagnóstico do contrato anterior, sem efeito na aprovação v3.2.

Pior furnace das luzes nas duas grades: NdotV=0,01, roughness=0,1. Na 64×64,
Ess_lit de referência=0,016447923; interpolado=0,017752472; energia compensada
resultante=0,926514514. O erro absoluto pequeno não garante erro relativo de 3%
quando a energia é baixa. O teste mede a BRDF independente multiplicada pelo fator
extraído da LUT, não a normalização da LUT por ela mesma.

Na grade 64×64, Ess_lit variou de 0,015152 a 0,999512: nenhum texel excedeu 1.
A maior diferença absoluta Ess_lit−Ess_env em módulo foi 0,897888. São energias
distintas: um fator único de Ess_env não conserva a energia das luzes com hotness.
Essa limitação é aceita na v3.2, evitando o ganho acima de 60× de 1/Ess_lit.

Referência independente: entre 131.072 e 8.388.608 avaliações por ponto na rodada
final; maior variação relativa entre rodadas aceitas=0,076693%, abaixo de 0,1%.
Como verificação analítica, em NdotV=1, roughness=1 e F=1, a energia é
`1−ln(2)`: a referência diferiu por 2,22e-16. A maior diferença geração por
importância × referência nos pontos foi (A/B/Ecc/Ess_lit):
0,001926 / 0,000064 / 0,000010 / 0,000082. Esse erro de amostragem permanece
separado do erro de interpolação.

### Fresnel da base

Os números abaixo isolam a substituição de FH exato por Schlick, sem erros da LUT.
Para metais coloridos, a diferença de saída por canal é `(1−Cspec0)·delta_B`;
para metal branco com Cspec0=1, ela se cancela porque A+B é independente do Fresnel.

| Specular | eta | Máx. erro absoluto em A ou B | NdotV / roughness do pior caso | Erro na saída dielétrica nesse ponto |
|---|---:|---:|---|---:|
| 0 | 1 | 0,757750 | 0,01 / 0 | 0,757750 |
| 0,01 | 1,058215 | 0,256278 | 0,173 / 0 | 0,256073 |
| 0,25 | 1,329431 | 0,051335 | 0,173 / 0 | 0,050308 |
| 0,5 | 1,5 | 0,031295 | 0,05 / 0 | 0,030044 |
| 1 | 1,788789 | 0,032293 | 0,05 / 0 | 0,029710 |

Schlick foi aceito no ambiente na v3.2, inclusive com esses erros. O Fresnel
exato das luzes permanece. Uma representação dependente de eta ficou fora do
contrato aprovado.

#### Ajuste proposto para Specular baixo

Foi medido `Cspec0·A + B·min(1,F0/0,04)`, com `F0=0,08·Specular`.
A tabela isola a fórmula: usa integrais convergidas, sem erro da LUT, e reporta
o máximo absoluto nos mesmos 30 pontos, em unidades lineares.

| Specular | Escala de B | Erro dielétrico sem ajuste | Erro dielétrico com ajuste | Erro metal branco com ajuste |
|---|---:|---:|---:|---:|
| 0 | 0 | 0,757750 | 0 | 0,757750 |
| 0,01 | 0,02 | 0,256073 | 0,627322 | 0,742595 |
| 0,25 | 0,5 | 0,050308 | 0,356039 | 0,378875 |
| 0,5 | 1 | 0,030044 | 0,030044 | < 1e-15 |
| 1 | 1 | 0,029710 | 0,029710 | < 1e-15 |

**Recomendação: não aplicar esse ajuste como aproximação do Fresnel exato.**
Ele resolve eta=1, mas suprime a reflexão rasante para eta ligeiramente maior que 1.
Para metal branco, Schlick sem ajuste tem erro zero nesta integral; reduzir apenas
B quebra A+B=Ess e a compensação white-furnace. Uma escala usando Cspec0 em vez
do F0 escalar seria outra fórmula e exigiria validação, incluindo metais coloridos
e specular tint. Casos por ponto e canais metálicos 0/0,25/0,5/1 estão em
`report.json`, campo `low_specular_correction`. Não foi alterado GLSL nesta tarefa.

Como comparação, o Karis atual apresentou erro máximo de 0,197958 em Ess_env.
Usar indevidamente `0.04·A_Karis+B_Karis` como integral do verniz apresentou erro
0,893044 frente a Ecc. Isso compara fórmulas; não há hoje verniz de ambiente para
chamar essa diferença de regressão visual.

Revalidar tabelas salvas, sem repetir a geração inteira:

```powershell
python tools/debug/bsdf/integrar_brdf.py --reuse-luts
```

Os caminhos padrão são calculados a partir de `__file__`: a saída fica em
`artifacts/bsdf-energia/` e o header em `source/source/blender/gpu/intern/` deste
repositório, mesmo executando o script de outra pasta. Um `--out` relativo também
é resolvido contra a raiz do repositório. `--reuse-luts` requer os arquivos
`lut_32.npy` e `lut_64.npy` de uma geração anterior; sem eles, executar sem essa
opção para gerar e validar as tabelas completas. O script tem cabeçalho GPL,
e o header gerado tem identificação GPL e guard `GPU_BRDF_LUT_H`.

O comando retorna erro quando os critérios falham e não sobrescreve o header.
Os ensaios `--probe-sqrt`, `--probe-endpoints` e `--probe-size N` calculam somente
os texels necessários para esses pontos, sem emitir header; não validam uma
tabela completa nem autorizam mudar o contrato.

### Ensaios anteriores de resolução (não adotados)

O ensaio de uma grade **256×256 uniforme** calculou os 99 texels necessários aos
mesmos 30 pontos, incluindo float16 e bilinear. O maior desvio furnace foi
0,733% no ambiente e 1,341% nas luzes; maior erro absoluto de canal foi 0,002263.
Todos esses pontos ficaram dentro dos critérios anteriores. A v3.2 dispensou
essa resolução ao retirar o furnace das luzes dos critérios. Não foi gerada a
tabela completa nem alterado o contrato para 256×256.
Ela ocupa 512 KiB em RGBA16F, frente aos 32 KiB da 64×64. O ensaio está em
`artifacts/bsdf-energia/probe_uniform256.json` e pode ser reproduzido com:

```powershell
python tools/debug/bsdf/integrar_brdf.py --probe-size 256
```

Dois ensaios com coordenada sqrt(NdotV) em 64×64 não resolveram todos os pontos:
centros de células deixaram desvio furnace de até 3,677%; incluir os extremos
deixou até 8,285% nas luzes. A função muda de derivada no piso de roughness=0,1,
então alterar apenas a densidade de amostras em NdotV não resolve a interpolação
nessa faixa. Os ensaios estão registrados, sem alterar o contrato do shader.

## Cache

Não é necessário alterar a versão do `.cooked` por mudar a assinatura GLSL.

- `source/source/blender/gpu/intern/gpu_shader.c:547`: `binary_key` faz hash FNV-1a
  dos trechos de fonte, flags e strings GL_VENDOR/GL_RENDERER/GL_VERSION.
- `source/source/blender/gpu/intern/gpu_shader.c:763`: os trechos incluem versão,
  extensões, defines, biblioteca comum, vertexcode, libcode e fragcode. A função
  nova e suas chamadas alteram a chave; a biblioteca pode ser reduzida às funções
  utilizadas em `source/source/blender/gpu/intern/gpu_codegen.c:3659`.
- `source/source/gameengine/Physics/Bullet/CcdCookedData.cpp:431`: `FindShader`
  procura a chave completa; chave nova resulta em miss e compilação normal.
- `source/source/blender/gpu/intern/gpu_shader.c:777`: se o driver rejeitar um
  binário encontrado, o programa é recriado e compilado normalmente.
- Cache em memória: `source/source/blender/gpu/intern/gpu_codegen.c:163` faz hash
  de vertex/fragment/geometry e flags; `shader_cache_acquire` em
  `source/source/blender/gpu/intern/gpu_codegen.c:224` também confere igualdade
  das strings e identidade da biblioteca. Ele dura apenas o processo; recompilar
  o texto embutido exige reiniciar o executável.

Alterar **somente os dados da textura LUT** não muda a fonte GLSL nem exige
invalidação do binário: basta recompilar o header e recriar/enviar a textura no
processo novo. Não apagar os dados físicos/meshes do `.cooked` por esse motivo.
`RANGE_SHADER_SALT` é útil para medir compilação fria, não é requisito de migração.

## F1: aproximação de multiscatter

Integração L2 a cargo do Claude. Somente Distribution Multiscatter GGX.
`ms = 1 + Cspec0·(1-Ess_env)/Ess_env`, com o mesmo fator para ambiente/luzes
por decisão v3.2. Não se espera furnace unitário nas luzes com hotness.
É uma aproximação para tempo real; não implementa o random walk do
Cycles 2.79. Difuso, lightmap e SSGI não recebem um novo fator kd.

## F2: clearcoat no ambiente

Implementada pelo Claude no commit `6ee167a4`, ainda pendente de validação L4.
Soma `env_cc_mirror·Ecc·0.25·clearcoat`, com a normal própria do verniz, sem
atenuar a base. A revisão confirmou que `env_cube_tex`, `env_equirect_tex` e
`env_probe_sample` selecionam mip por `sqrt(roughness)·maxlod`. Não é uma
convolução GTR1; a integral Ecc corrige a energia, mas não transforma esse filtro
no lóbulo do verniz. A roughness da consulta do ambiente vem do socket; a da
integral recebe specular AA no shader, outra aproximação em geometria pequena.

## Compatibilidade

| Distribution | Ambiente da base | Luzes da base | Verniz no ambiente |
|---|---|---|---|
| GGX (padrão preservado) | Karis atual | Sem compensação | Muda na F2 se clearcoat > 0 |
| Multiscatter GGX | LUT e ms_env | Mesmo ms_env | Mesmo caminho do GGX |

A regressão GGX com clearcoat zero precisa de diferença zero após F0/F1.
Materiais existentes não devem ser migrados automaticamente. O aceite visual da
mudança intencional no verniz e os builds desktop/Web ficam pendentes de L4.

## Limitações

- LUT isotrópica; o shader direto aceita anisotropia.
- Split-sum e filtragem do ambiente são aproximações direcionais.
- Schlick na base difere do Fresnel dielétrico exato, especialmente perto de eta=1;
  aproximação aceita na v3.2. O ajuste linear proposto de B piora casos não nulos.
- Specular AA muda a rugosidade conforme a geometria/tela; estas tabelas recebem
  a rugosidade já modificada, sem reproduzir derivadas de tela no integrador.
- Não cobre subsurface real, BSDFs avulsos ou clearcoat em reflexos planares.
- Nenhum resultado de GPU, imagem ou build desktop/Web foi inferido da quadratura.

Verificação documental: `python tools/check_docs.py` foi executado novamente
após a v3.2: 53 erros e 157 avisos, em mapas defasados, incluindo os mapas GPU e
gameengine. Não houve erro apontado neste documento. Os mapas acompanham código
modificado em outras frentes e não foram reescritos por esta tarefa. Log:
`artifacts/bsdf-energia/check-docs-v32-final.log`. A checagem sintática dos dois
scripts passou; o header foi relido e conferido contra o RGB da LUT validada,
incluindo 16.384 floats finitos e todos os valores de alfa iguais a zero.

## Revisão cruzada de L1–L3

Revisão estática dos commits `6d40afa9`, `652d0a7d` e `6ee167a4`, em 2026-10-29:

- L1: RGBA16F com filtro linear e clamp, criação/liberação global; coordenadas
  correspondem à interpolação validada. O header numérico substitui o provisório
  no diretório de trabalho e precisa entrar na entrega final.
- L2: seletor Multiscatter habilita LUT/ms somente quando a textura existe;
  GGX mantém Karis. Compensação multiplica specular das luzes e do ambiente;
  difuso, lightmap e saídas SSGI não receberam fator kd.
- L3: segunda consulta do ambiente condicionada ao uso do clearcoat, com normal
  própria e peso 0,25. A leitura da LUT usa canal azul; alfa não é consumido.
- Ajuste para Specular baixo não aparece nesses commits, em acordo com a
  recomendação numérica. Sem bloqueio funcional confirmado nesta revisão.

Dois comentários ainda descrevem alfa como energia das luzes, em `GPU_texture.h`
e junto de `env_brdf_lut` no GLSL; devem dizer reservado/zero para refletir v3.2.
Não foram editados porque pertencem aos arquivos do Claude. A revisão de fonte
não comprova regressão visual zero, compilação GLSL no driver ou desempenho.
Não foi localizado log de build L4 na pasta de evidências desta tarefa.

### Revisão adicional do parser GLSL

O commit `2976bd78` aumenta `MAX_PARAMETER` de 32 para 48. Uma varredura dos
protótipos `void` da biblioteca confirmou 35 parâmetros no Principled, o maior
protótipo atual; nenhum ultrapassa 48. Os vetores de tipos e qualificadores usam
a mesma constante, portanto a correção cobre a assinatura atual.

Melhoria de robustez pendente: em `gpu_parse_functions_string`, atingir o limite
interrompe o laço de parâmetros, mas ainda executa `BLI_ghash_insert` com a
assinatura truncada. O aviso impede a escrita fora do vetor, porém não rejeita
a função inválida. Recomenda-se liberar e descartar essa função antes do registro,
avançando até a próxima definição. Não afeta os protótipos atuais; não é bloqueio
confirmado do Principled. O arquivo pertence à implementação do Claude e foi
somente revisado.

### Verificações adicionais após a revisão

- Desktop: `ninja RangeEngine RangeRuntime` com vcvars64 e VSLANG=1033 terminou
  com código 0. Log `artifacts/bsdf-energia/build-desktop-confirmed.log` e código
  em `build-desktop-exit-code.txt`. Ambos os alvos estão atualizados para as
  fontes disponíveis nesta revisão; o editor foi relinkado e instalado.
- Player atualizado: cena HDRI+SSGI executou em `--server`, código 0,
  62 frames em aproximadamente 1 segundo, com `logic_only=true` em
  `review-runtime-hdri.json`. Isso não compila nem valida o shader no driver.
- Os dois scripts passaram em `py_compile`. Após a atualização dos mapas pelo
  Claude, `check_docs.py` passou com **0 erros e 0 avisos**, conforme
  `artifacts/bsdf-energia/check-docs-additional-review.log`.
- O build Web foi observado em execução em `build-web-release`, sob controle
  do Claude. Não foi considerado aprovado sem seu log final. Medições de GPU
  e aceite visual continuam pendentes nesta revisão.

### Revisão do commit 0cc30d8f

- Resolvida a recomendação anterior: o parser libera e descarta funções acima
  de `MAX_PARAMETER`, sem registrar uma assinatura truncada. O cursor já avançou
  pelos parâmetros, permitindo procurar a próxima definição sem repetir a atual.
- O parâmetro `r_flag` do helper de ambiente agora aceita NULL; o clearcoat deixa
  de criar o link uniforme não utilizado. Os demais chamadores preservam a flag.
- Não foram encontrados bloqueios funcionais nessas alterações. Os comentários
  antigos sobre o alfa da LUT também foram corrigidos.
- A nova compilação compilou os objetos alterados, mas o link do player falhou
  com `LNK1104: cannot open file 'bin\\AnastacioRuntime.exe'`: havia um player
  aberto (PID 16860), que foi preservado. Log: `build-review-0cc30d8f.log` em
  `artifacts/bsdf-energia/`. O build anterior aprovado não valida este commit.
- `check_docs.py`: 0 erros e 1 aviso sobre a contagem de linhas do mapa GPU
  (3.732 documentadas contra 3.740 atuais). Validação visual permanece pendente.

### Revisão do commit d7d9aff3

- Build desktop dos alvos RangeEngine e RangeRuntime confirmado com código 0,
  após o player anterior ter sido fechado. Log `build-review-final.log` em
  `artifacts/bsdf-energia/`. Smoke HDRI+SSGI em `--server`: código 0,
  62 frames, `logic_only=true`, em `review-final-runtime.json`.
- O commit novo altera documentação. Os custos declarados no changelog não
  puderam ser reproduzidos a partir dos artefatos BSDF disponíveis: faltam o
  log de timings, configuração e procedimento do A/B. Multiplicar o custo da
  RX 6800M por 16 é estimativa, não medição no HD 4400; o custo de shaders
  distintos não tem garantia de escalar pelo mesmo fator entre GPUs.
- A entrega versionada ainda depende da inclusão do header numérico final,
  deste documento e dos scripts: estão presentes no diretório de trabalho,
  mas ausentes dos commits revisados. O build aprovado usa esse diretório.
- Nenhum novo defeito funcional encontrado nas correções de código revisadas.
  Aceite visual e confirmação do build Web permanecem pendentes nesta revisão.

### Preparação da entrega do Codex

Revalidação executada de `C:/Users/f_bro`, fora do repositório, com
`python D:/AnastacioEngine/tools/debug/bsdf/integrar_brdf.py --reuse-luts`.
Terminou com código 0 e selecionou 64×64; os caminhos padrão apontaram para
este repositório. A tabela de erros do ajuste de Specular baixo acima foi
recalculada e confirmou os valores publicados. Log em
`artifacts/bsdf-energia/revalidate-for-commit.log`.

O header regenerado foi conferido contra o RGB float16 da tabela validada:
16.384 valores finitos, alfa todo zero, resolução 64 e guard presente.
Os dois scripts passaram em `py_compile`. `check_docs.py` apresentou 0 erros
e o único aviso já existente no mapa GPU, mantido fora desta entrega.
Somente o header, este documento, o integrador e a cena de teste fazem parte
da entrega do Codex; os fontes e documentos do Claude não foram alterados.

Após regenerar o header, `ninja RangeEngine RangeRuntime` com vcvars64 e
VSLANG=1033 passou (código 0, `build-commit-lut.log`). O player reconstruído
executou HDRI+SSGI em `--server` sem erro: 62 frames, aproximadamente 1 segundo,
`logic_only=true` (`runtime-commit-lut.json`). Este smoke valida execução lógica;
o aceite visual com janela continua pendente antes do merge.
