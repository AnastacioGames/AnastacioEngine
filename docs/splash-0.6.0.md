# Splash 0.6.0 com o Rolima Racer

Composicao feita com a Pista 1, o carrinho de madeira e o piloto Fabio.
Os fragmentos de cerca da primeira proposta foram retirados apos avaliacao visual.
O projeto original nao e salvo pelo gerador.
Os assets continuam pertencendo ao jogo; a cena local nao integra o pacote da engine.

Gerar a partir da raiz do repositorio:

```powershell
& ./build/bin/AnastacioEngine.exe -b D:/ProjetoRolimaRacer/RolimaRacer.range --python tools/debug/cenas/criar_splash_rolima_060.py -- D:/AnastacioEngine/artifacts/splash-0.6.0/rolima-splash-060.range
```

O destino deve existir. O arquivo depende das texturas locais do jogo, cujos caminhos
sao convertidos para absolutos. A copia contem somente a cena da composicao, sem menus,
componentes de corrida ou loaders. A pose de pilotagem e uma action original do jogo.

Abrir a previa:

```powershell
& ./build/bin/AnastacioRuntime.exe D:/AnastacioEngine/artifacts/splash-0.6.0/rolima-splash-060.range
```

- R: disparar raio localizado e pequena explosao no asfalto a frente do piloto.
  O conjunto dispara sozinho apos 2 segundos e repete a cada 10 segundos;
  cada evento tem cinco pulsos do raio espaçados em 0,18 segundo.
- B: comparar com/sem desfoque radial e riscos animados de velocidade nas bordas. A mascara
  protege o piloto na composicao atual; se mudar a camera, ajuste-a no GLSL.
- F12: capturar a imagem do jogo em `captura-splash-060.png`, ao lado da cena.
- Esc: sair.

Resolucao: 1672 x 941. Chuva, pocas com SSR, respingos, aura de chuva, relampagos,
SSAO, bloom, tonemap, FXAA, DOF leve e vinheta usam os recursos da engine.
As particulas das rodas seguem para tras, com velocidade Z reduzida para 0,1.

O controlador embutido vem de `tools/debug/cenas/splash_rolima_runtime.py`.
O filtro custom de velocidade vem de `tools/debug/cenas/splash_rolima_speed.glsl`,
embutido na cena. Funciona com a camera parada e nao depende da velocidade real.
O desfoque usa 16 amostras e intensidade 0,10; filetes radiais animados reforcam
o movimento sem movimentar os objetos. `splash_rolima_arte.py` configura ceu
de tempestade (desliga a atmosfera diurna herdada), nuvens, contraste azul/ambar,
e reduz o DOF e os circulos da chuva para preservar detalhes. Copia anterior
local: `rolima-splash-060-antes-arte.range`, na pasta dos artefatos.
`tools/debug/cenas/splash_rolima_impacto.py` configura o emissor de raio Manual
e um template inativo Explosive, com Particle Explosion Small/Fire e Light Flash.
Cada evento cria uma instancia nova e chama `detonate()`. O impulso e zero para
preservar a composicao. O raio atinge o asfalto em X=0, Y=9; os raios aleatorios
do World ficam sem frequencia automatica. R reinicia a contagem dos 10 segundos.
O emissor fica acima do asfalto e aponta explicitamente para `Splash_Impacto_Alvo`,
usado tambem como origem da explosao. `SPLASH_CAPTURE` permite solicitar uma
captura nativa unica 0,12 s depois do primeiro impacto, no player com render.
Para smoke sem janela, definir `SPLASH_SMOKE=1` e `SPLASH_LOG` com um caminho
absoluto e executar o player com `--server`. O controlador encerra aos 120 quadros
e grava `SMOKE_COMPLETED_120`. Isso valida execucao, sem comprovar resultado visual.

O enquadramento, encaixe do piloto, iluminacao e efeitos precisam de avaliacao
no player pelo usuario antes da captura final e da aplicacao de logo/versao.
O splash instalado ainda nao foi substituido.

## Proposta alternativa: Tempestade Eletrica

A versao aprovada foi copiada com captura e scripts para
`artifacts/splash-0.6.0-aprovada/`; o `.range` e identico ao da pasta original.
A proposta alternativa fica em `artifacts/splash-0.6.0-surpresa/rolima-tempestade-eletrica.range`.

Gerador: `tools/debug/cenas/criar_splash_rolima_surpresa.py`, executado no editor
em background com a cena anterior como entrada e destino diferente apos `--`.
Ele muda somente a copia: camera traseira lateral rente ao chao (enquadramento
da proposta Claude B escolhido pelo usuario), horizonte inclinado, spray de agua
nas rodas, nevoa volumetrica, Sky Layers e impacto eletrico a frente. A tentativa
frontal foi substituida apos retorno do usuario. Nuvens volumetricas ficam
desligadas porque produziram quadriculado no horizonte da captura.
O filtro e o runtime sao embutidos com nomes proprios; B, R, F12 e Esc continuam
disponiveis. O ciclo de impacto continua em 10 segundos, com impulso zero.

O arquivo depende dos mesmos assets locais. Nao integra o pacote da engine e
nao substitui a composicao aprovada nem o splash instalado.
