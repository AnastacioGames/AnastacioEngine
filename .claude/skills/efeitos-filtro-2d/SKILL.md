---
name: efeitos-filtro-2d
description: Especialista em efeitos de tela cheia por Custom 2D Filter na Anastacio Engine (mar/ceu/fogo por raymarching, personagens por SDF, gotas na lente) integrados a camera real, a profundidade da cena e a jogabilidade em Python. Use ao criar ou ajustar shaders de filtro para jogos (ex.: D:\FuturoJogos) ou adaptar shaders estilo Shadertoy.
---

# Efeitos por 2D Filter jogaveis

Referencia viva: `D:\FuturoJogos\CuboNaTempestade\gerar_cena.py` (oceano, rastro, aneis,
monstro SDF, gotas na lente, flutuacao). Comece por ele antes de escrever do zero.

## Meta de jogo
Jogos feitos com esta skill seguem `D:\FuturoJogos\META_JOGO_VICIANTE.md` (vontade de jogar
"so mais uma"), adaptada ao estilo de cada jogo. Leia antes de propor mecanicas.

## Licenca primeiro
Shaders do Shadertoy sao quase sempre CC BY-NC-SA (ex.: "Seascape" do TDM): servem so para
estudo/prototipo. Para jogo vendavel, escreva codigo original (tecnicas sao livres, o codigo nao).
Anote no IDEIA.md do jogo quando um prototipo usa codigo de terceiros.

## Gerar a cena por script
- Um `gerar_cena.py` cria tudo com bpy legado (2.79): `scene.objects.link`, `obj.select`,
  `bpy.data.lamps`. Rode com `build/bin/AnastacioEngine.exe -b --factory-startup --python gerar_cena.py -- saida.range`.
- Shader e logica ficam como strings no gerador; uma unica lista de parametros (ex.: ONDAS)
  gera o GLSL **e** o Python, entao visual e fisica nunca divergem.
- Cuidado: strings formatadas com `%` exigem `%%` no codigo embutido.
- Filtro: atuador `FILTER_2D`, `mode='CUSTOMFILTER'`, `glsl_shader=texto`, `filter_pass` (0, 1...)
  ligado a Always (uma vez) + AND. Varios passos encadeiam: o passo N le o resultado do N-1
  em `bgl_RenderedTexture`.
- Resolucao de janela explicita (`game_settings.resolution_x/y`, ex.: 1600x900).

## Uniforms
- Builtins uteis (`RAS_2DFilter.cpp`): `bgl_RenderedTexture`, `bgl_DepthTexture`,
  `bgl_InverseViewMatrix`, `bgl_InverseProjectionMatrix`, `bgl_ViewMatrix`,
  `bgl_ProjectionMatrix`, `bgl_RenderedTextureWidth/Height`, `bgl_Time`.
- Valores do jogo: **game properties FLOAT/INT do objeto dono do atuador** (normalmente a
  camera) viram uniforms com o mesmo nome. Crie as props no gerador (`game_property_new`) e
  atualize no Python todo tick (`cam["tempoMar"] = ...`).
- Tempo: controle o relogio no Python (prop acumulada) e use o mesmo valor no shader e na
  fisica. Nao misture com `bgl_Time`.

## Camera real e composicao
```glsl
vec2 ndc = uv * 2.0 - 1.0;
vec4 v = bgl_InverseProjectionMatrix * vec4(ndc, 1.0, 1.0); v /= v.w;
vec3 o = bgl_InverseViewMatrix[3].xyz;
vec3 d = normalize(mat3(bgl_InverseViewMatrix) * v.xyz);
float zb = texture2D(bgl_DepthTexture, uv).r;
vec4 vp = bgl_InverseProjectionMatrix * vec4(ndc, zb * 2.0 - 1.0, 1.0);
float distCena = (zb >= 0.99999) ? 1e9 : length(vp.xyz / vp.w);   // mesma unidade de t
```
- Compare a distancia ao longo do raio (`t`) com `distCena`: o mais perto ganha. Objetos
  logo abaixo da superficie: misture a cor da cena tingida com `exp(-(distCena - t) * k)`.
- Personagem por SDF entra como "mais um objeto": se `tSdf < distCena`, troque
  `distCena`/`cena` por ele **antes** de tracar o mar; o mar cobre a parte submersa sozinho.
- Eixo Z para cima (shaders Shadertoy usam Y): converta `p.xz -> p.xy`, `e.y -> e.z`.

## Tecnicas
- Mar: soma de ondas direcionais com crista `2*pow(0.5+0.5*sin(fase), sharp)-1`, direcoes e
  comprimentos irregulares (nada de multiplos simples, senao forma grade). Raymarch em
  laje [-topo, topo]: passos lineares + bisseccao.
- Detalhe so visual (normal): ruido de valor com rotacao por oitava, atenuado com a distancia
  (`exp(-dist*k)`), senao serrilha e vira "xadrez".
- Hash sem `sin()` (Hoskins `fract(p*0.1031)...`) quando GPU e Python precisam bater.
- Rastro: esteira de Kelvin em V (bracos em `lat = atras*0.36`) + espuma central; aneis de
  ondulacao por posicao/tempo de inicio (`ondaX/ondaY/ondaT`).
- SDF: toros verticais (corcovas), capsula (pescoco), elipsoide `(length(p/r)-1)*min(r)`;
  ondulacao somando `sin` em z; esfera envolvente antes do sphere tracing (64 passos,
  passo `d*0.8` por causa da deformacao). Normal por diferencas centrais.
- Gotas na lente: segundo passo, grade em camadas com hash por celula; cada gota tem limiar
  proprio contra a prop `respingo` (somem uma a uma); centro + raio + escorrimento cabendo na
  celula (senao a gota sai cortada); distorcao de lente invertendo o UV.

## Jogabilidade em Python
- Reimplemente so o necessario (altura da onda, SDF sem detalhes) com as mesmas constantes.
- Empuxo: amostre cantos inferiores, `applyImpulse(ponto, (0,0,k*min(prof,1)*dt))` + arrasto.
- Colisao com SDF: `dist_sdf(posicao) < raio_do_objeto` (so quando o personagem esta visivel).
- **Nao existe `applyAngularImpulse`** nesta engine (so `applyImpulse`/`applyTorque`): o erro
  interrompe o tick no meio e quebra controles/regras em silencio (sintoma: Logic alto no
  profile e fisica identica entre rodadas). Para girar, some direto em `worldAngularVelocity`.
- Corpo boiando estavel: torque de endireitar `cima.cross(Z) * k * dt` na velocidade angular +
  amortecer `v.z` submerso, senao quica e capota sozinho.
- Camera lateral (cubo indo para a direita): camera em +X olhando -X, ou seja, +Y fica a
  direita da tela. Personagens devem nascer do lado de la e dentro da largura visivel.

## HUD
- Texto 3D preso a camera fica escondido: o filtro pinta a tela inteira. Use ImGui
  (`from bge import imgui`, fallback `from Range import imgui`), chamado no tick da logica: o
  frame do ImGui comeca antes da logica e e desenhado no fim, por cima dos filtros.
- Sem `set_game_ui_open(True)` (isso solta o mouse e e para menus). `begin` nao aceita flags:
  janela `"##nome"` + `push_style_color` transparente em `COL_TITLE_BG(_ACTIVE)`/`COL_BORDER`,
  `set_next_window_pos/size` todo frame, fonte grande com `load_default_font(tam)` (None no
  primeiro frame).

## Validar
- O runtime nao imprime erros de GLSL no console: valide por imagem. Modo diagnostico via
  variavel de ambiente (ex.: `CUBO_LOG`): grava log, `bge.render.makeScreenshot(caminho)` aos
  5 s e `bge.logic.endGame()` aos 8 s; depois leia o PNG.
- Se algo parecer quebrado, troque `gl_FragColor` por visualizacoes (distCena, t, mascaras)
  numa copia do gerador no scratchpad.
- Antes de culpar o shader, confira se nao ha `ninja` rodando: runtime em relink da imagens
  erradas ou "Device or resource busy".
- Custo: Filters2D no profile mede CPU; raymarching em tela cheia pesa em iGPU. Reduza passos
  ou distancia maxima se o usuario relatar queda.
- Aceite visual final e do usuario (AGENTS.md).
