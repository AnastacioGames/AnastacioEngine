# Plano — Export Android reaproveitando o runtime Web

Data: 2026-09-20. Status: **revisado; viabilidade Android ainda não demonstrada**.
Esta revisão confere documentação, código local e fontes oficiais; não implementa o exportador nem comprova execução em Android.

## 1. Recomendação e escopo

**O melhor próximo passo é um APK experimental mínimo com WebView e o jogo real.** Reaproveitar o runtime Web é a rota de menor trabalho inicial identificada, mas sua adoção para distribuição depende do resultado em aparelho físico. Chrome Android serve de referência; o produto precisa passar no WebView dentro do APK.

Recomenda-se Kotlin + AndroidX WebKit (`WebViewAssetLoader`), pacote Web local e APK para testes via `adb`. O backend NDK fica congelado com critérios de reabertura (seção 9). Não desenvolver as duas rotas ao mesmo tempo.

Primeiro escopo jogável: carregar offline desde a primeira abertura, render WebGL2, controle direcional e botões por toque simultâneo, áudio, save e retomada confiáveis. Sensores, entrada analógica completa, API Python mobile, AAB/Play e integração no editor entram depois da prova desse núcleo; antecipar inclinação somente se indispensável ao jogo escolhido.

Não há estimativa confiável antes dessa prova. As antigas faixas de 1–2 semanas (WebView) e 6–9 semanas (NDK) eram hipóteses sem execução Android; não devem orientar compromisso de entrega.

Fora do escopo inicial: iOS, editor em tablet, WebGL1/GLES2, multiplayer nativo, threads wasm e Play Asset Delivery.

## 2. Evidência disponível e correções da revisão

O Web já roda com Python 3.11 wasm, Bullet, materiais GLSL, sombras/filtros, teclado/mouse, áudio e IDBFS. Os pacotes 8201–8211 tiveram aceite do usuário. O gamepad físico ainda precisa ser reconferido após o patch SDL2. Isso reduz o trabalho de portabilidade, mas não prova comportamento ou desempenho mobile.

| Premissa anterior | Conclusão da revisão |
|---|---|
| Chrome Android aprovado basta para avançar | Exigir também APK WebView no mesmo aparelho: APIs e ciclo de vida diferem. |
| Todos os sensores existem no WebView sem código Android | Verificar API, eventos efetivos e frequência. Contexto seguro é necessário para algumas APIs, mas não garante implementação nem sensor físico. |
| Inclinação vira gamepad apenas com JS | Não há uma API Web padrão para inserir um controle virtual em `navigator.getGamepads()`. Definir e provar a ponte de entrada; evento sintético não cria esse controle. |
| `FS.syncfs()` é síncrono | É assíncrono. O risco principal é encerrar/suspender antes do callback, além do custo de cópias e saves grandes. |
| `onPause` pausa o jogo e garante o save | `WebView.onPause()` não pausa JavaScript; o app precisa de um protocolo explícito com o runtime. |
| `.wasm`/`.data` já são comprimidos | O pacote local copia os arquivos brutos. Há redução expressiva por gzip documentada em `web-deploy.md`. |
| `minSdk 24` garante WebGL2 | A versão do SO não comprova as capacidades do provedor WebView/GPU. Fazer testes de capacidade no início. |
| TWA não funciona offline | Pode funcionar com service worker; não é a opção mais direta para embutir este pacote e abrir offline desde a primeira execução. |
| O editor depende de liberar `CompanyName`/`IconPath` | Esses campos já são gravados em `wm.py`; a restrição citada era histórica. Campos Android ainda precisam de schema próprio. |

Evidência no repositório:

- `tools/web/package-web.py`: `fetchInto()` carrega arquivos inteiros e os copia ao FS; `preRun` inicia jogo e extras em paralelo. Medir o pico de memória de carga, não só a cena estabilizada.
- `source/source/blenderplayer/web_idbfs_prerun.js`: monta `/saves` e aguarda `syncfs(true)` antes do jogo. Erro inicial hoje é logado e a dependência liberada; definir tratamento para não sobrescrever progresso após falha de leitura.
- `source/source/gameengine/Ketsji/KX_PythonInit.cpp`: `saveGlobalDict` já chama `syncfs(false, callback)` após escrever; aproveitar esse caminho, adicionando confirmação de persistência e serialização das solicitações se necessário.
- `tools/web/verify-capabilities.cjs`: modo `touch` verifica toque convertido em clique de mouse, **não multitouch real**. Usa criação de aba CDP; adaptar para conectar ao alvo WebView existente via ADB.
- `tools/web/make-runtime-manifest.py`: `touch` está `disabled`; não promover capacidades a validadas com base em emulação desktop.
- `source/release/scripts/startup/bl_operators/wm.py`: grava `CompanyName`, `IconPath` e seletores desktop. `docs/export-presets-plan.md` registra a extensão já feita.

As distinções de plataforma estão documentadas pelo [Chromium](https://chromium.googlesource.com/chromium/src/+/HEAD/android_webview/docs/web-platform-compatibility.md); a [Gamepad API](https://www.w3.org/TR/gamepad/) define leitura de controles, e a [API de FS do Emscripten](https://emscripten.org/docs/api_reference/Filesystem-API.html#FS.syncfs) define sincronização assíncrona. A política de pausa do WebView está na [referência Android](https://developer.android.com/reference/android/webkit/WebView#onPause()).

## 3. Sequência recomendada e critérios de avanço

Preservam-se os identificadores A0–A5 para referência; a ordem muda para provar o produto cedo.

| Etapa | Entrega | Condição para avançar |
|---|---|---|
| A0a — referência | Runtime release, cena pequena e jogo real no Chrome Android; registrar aparelho, configurações e hashes. | WebGL2/wasm iniciam e existe orçamento inicial plausível; falha exclusiva do navegador não encerra a investigação do WebView. |
| A0b + A2 mínimo — prova decisiva | APK de teste com pacote embutido, logs, primeiro controle por toque e leitura das capacidades. | Jogo real executa no WebView físico; offline, memória, frame time, áudio e persistência têm resultados registrados. |
| A1 mínimo + A2 completo | Controle simultâneo, pausa/retomada, cancelamento de entradas, saves confirmados e recuperação de falhas. | Testes funcionais da seção 8 passam no aparelho mínimo escolhido. |
| A3 — CLI de exportação | Template parametrizado e `package-android.py`; APK debug/release e relatório. | Instalação limpa e atualização assinada preservando save, executadas no aparelho. |
| A4 — editor | Preset Android e chamada da CLI, com validação e diagnóstico. | Mesmo pacote reproduzível pela CLI e pelo editor; ausência de SDK gera erro útil. |
| A5 — aceite | Matriz de dispositivos e sessão sustentada no jogo real. | Aceite visual/jogável do usuário e relatório de limitações. Só então anunciar suporte. |
| Depois do núcleo | Sensores, eixos analógicos/API Python e AAB/Play, conforme necessidade. | Cada capacidade recebe evidência própria, sem herdar aceite do desktop. |

A0b é um template pequeno feito diretamente com Gradle, sem exportador genérico e sem painel. **Estado 2026-09-23:** template em `tools/android/webview-template/` compilado e rodando a cena `motion` no OPPO Find X3 Pro (carga offline, WebGL 2, Python, sensores); o jogo real e as medições de A0b seguem pendentes, ver [android-manual-tests.md](android-manual-tests.md). Não esperar A3 para descobrir incompatibilidades do WebView. Testar emulador para instalação/erros básicos; não usá-lo para aprovar FPS, memória ou latência mobile.

## 4. Entrada mobile: começar pequena, manter caminho de evolução

### A1 mínimo — direcional e botões

**Decisão 2026-09-24:** overlay HTML (Pointer Events) alimentando um pad virtual lido pela engine por `EM_JS`, com alvo gamepad (índice 0, analógico) ou tecla (origem separada do teclado físico), estendendo o Range Input System em vez de criar sistema paralelo. SDL virtual joystick não está habilitado na porta Emscripten. Plano e etapas T0–T4 em [android-touch-controls-plan.md](android-touch-controls-plan.md).

O harness captura Pointer Events e mantém estado por `pointerId`, com captura do ponteiro, coordenadas normalizadas ao canvas e tratamento de `pointercancel`, perda de foco e pausa. Aplicar `touch-action: none` à área do jogo e respeitar recortes/barras do sistema. Dois dedos precisam manter movimento + ação simultaneamente sem clique duplicado do SDL.

Começar com controles digitais mapeados a teclas existentes. Fazer uma prova curta de injeção na cadeia JS → SDL/GHOST → lógica do jogo. Se eventos sintéticos não chegarem corretamente, usar uma pequena ponte explícita JS→wasm; **não assumir que “sem C++” é um requisito** nem alterar globais privados do SDL/Emscripten. Preservar o estado do teclado físico: soltar um toque não pode soltar uma tecla ainda mantida por outra fonte.

Guardar configurações em `android-export.json` versionado por projeto, incluindo layout, ações, teclas, deadzone e sensibilidade quando aplicáveis. Antes de criar outro sistema de ações, conferir o Range Input System existente; o JSON deve mapear controles mobile para ações/bindings existentes quando compatíveis.

Critérios: mover + ação, dois botões juntos, arrastar para fora, cancelar toque e alternar app sem entrada presa. Um joystick virtual digital não deve ser anunciado como suporte a eixo analógico nem como API multitouch Python.

### Depois — analógico, sensores e API do jogo

- Provar primeiro um eixo com faixa e deadzone conhecidas chegando à lógica do jogo. Avaliar API pública de joystick virtual do SDL na versão efetivamente usada ou um adaptador de entrada do engine; testar antes de escolher. Não sobrescrever `navigator.getGamepads()` como arquitetura de produção.
- `DeviceOrientationEvent`/`DeviceMotionEvent` são candidatos a inclinação/movimento; medir eventos reais, valores nulos, taxa, latência e transformação de eixos. Generic Sensor API e `navigator.vibrate` são opcionais, com detecção e fallback.
  **Atualização 2026-09-23:** antecipado por decisão do usuário. `bge.logic.motion` (giroscópio, acelerômetro, gravidade, `tilt`, `calibrate()`) já existe no runtime Web, com eixos da tela e verificação por sensores emulados (`tools/web/verify-motion.cjs`); ver changelog. Inclinação e `calibrate()` aprovados no APK WebView em aparelho real (2026-09-23, [android-manual-tests.md](android-manual-tests.md)); falta medir taxa/latência.
- Se uma API Web faltar, avaliar adaptador Android pequeno (`SensorManager`/vibração) com mensagens limitadas à origem local. Isso não exige portar o engine inteiro para NDK.
- Só então estabilizar API Python (`touches`, aceleração, orientação etc.), reutilizando a infraestrutura de input existente. Não exigir de saída novo `SCA_IInputDevice`, DNA ou Logic Bricks.
- Calibrar posição neutra, filtrar ruído, reinicializar ao retomar e funcionar sem sensores. O gesto do botão Jogar continua necessário para áudio quando exigido pelo provedor.

## 5. Casca WebView e ciclo de vida

Template em `tools/android/webview-template/`, Kotlin com dependências AndroidX explícitas e versões fixadas. `WebViewAssetLoader` pertence ao AndroidX WebKit; “sem dependências extras” não descrevia a proposta corretamente.

Servir `assets/www/` por `https://appassets.androidplatform.net/assets/www/index.html`, mantendo URLs relativas e MIME `application/wasm`. A origem HTTPS local evita servidor próprio e permite conteúdo empacotado sem rede, conforme o [guia Android](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content). Manter host, diretório de dados e identidade do app estáveis entre atualizações; validar persistência, não presumir que a origem por si só a garante.

Configuração proposta:

- JavaScript, DOM storage e aceleração de hardware; fullscreen imersivo, insets, botão Voltar e tela acesa somente durante jogo ativo.
- Abrir apenas conteúdo do pacote no WebView; navegação externa sai para navegador. Desabilitar acesso amplo por `file://` e limitar qualquer ponte nativa à origem e mensagens previstas. Depuração remota somente no build debug.
- Não incluir service worker nem servidor HTTP local no MVP: todos os recursos vêm do APK. `fetch` de arquivo ausente deve falhar claramente, sem fallback acidental para rede.
- `minSdk 24` permanece **hipótese de cobertura**, sujeita a A0. Verificar wasm, criação de contexto WebGL2, limites/extensões necessários e armazenamento real; a versão do WebView é diagnóstico complementar.
- Fixar `compileSdk`/`targetSdk` conforme toolchain validado. Na consulta de 2026-09-20, a Play exige API 36 para novos apps/atualizações comuns; reconferir ao publicar, pela [política oficial](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en).
- Paisagem/retrato por preset, mas suportar resize e reconstrução da Activity. Não presumir que orientação fixa impede mudanças em tablets/dobráveis; conferir [comportamento adaptativo Android](https://developer.android.com/develop/adaptive-apps/guides/app-orientation-aspect-ratio-resizability).

Protocolo de pausa: liberar entradas → suspender lógica/física e áudio explicitamente → pedir flush de save pendente → acompanhar resultado. O callback Android não deve bloquear esperando JS. Retomada restaura relógio do engine para evitar recuperar todo o tempo em segundo plano, reinicia áudio quando permitido e recalibra controles. Verificar também se o jogo simula por trás do overlay inicial; o botão atual do harness principalmente revela o canvas.

Salvar durante o jogo, em checkpoints, e confirmar conclusão do IDBFS. Flush ao ir para segundo plano é uma tentativa adicional, nunca a única garantia. Serializar gravações, reportar erro/quota e manter save anterior recuperável. `saveGlobalDict()` retornar não significa que o callback de persistência terminou.

Tratar `webglcontextlost`, encerramento do renderer (`onRenderProcessGone`, quando disponível) e morte do processo: oferecer reinício controlado a partir do último save confirmado. Não prometer restaurar objetos GPU ou RAM de uma sessão destruída sem implementação específica.

Pthreads não entram no plano atual. COOP/COEP isoladamente não comprovam suporte: qualquer investigação futura precisa verificar `crossOriginIsolated`, `SharedArrayBuffer`, workers e o runtime recompilado no provedor real.

## 6. Empacotamento e integração

### A3 — CLI antes do editor

**Estado 2026-09-24:** feito junto com A4 por decisão do usuário. A lógica está em
`source/release/scripts/modules/range_web/android.py`; `tools/web/package-android.py` (terminal) e o painel
"Android (Range)" (`bl_ui/properties_android.py`) só a chamam. APK debug aceito no aparelho. Release assinado feito
no mesmo dia: chave PKCS12 criada pelo keytool do JDK ("Criar chave" no painel ou `--create-keystore`), recusada
dentro de repositório git e nunca sobrescrita; caminho e alias no `android-export.json`, senha só pela variável
`RANGE_ANDROID_KEYSTORE_PASSWORD` ou pelo campo de sessão do painel (não vai para o `.blend`, JSON, log nem
relatório); o Gradle recebe tudo pelo ambiente. Senha e alias conferidos pelo keytool antes do Gradle; o APK sai
verificado pelo `apksigner` e o relatório guarda o SHA-256 do certificado. Falta no aparelho: atualização release
sobre release preservando o save.

`tools/web/package-android.py` consome a pasta produzida por `package-web.py`, verifica hashes e manifestos, copia recursos de execução para o template e aplica `android-export.json`. Não reimplementa coleta de assets ou validação Web.

- Metadados: `applicationId` estável, `versionCode` inteiro crescente, `versionName`, nome, ícone, orientação e perfil de qualidade. Separar identidade do app do nome da cena para não perder saves ao renomeá-la.
- Fixar e registrar Gradle Wrapper, Android Gradle Plugin, Kotlin, AndroidX, SDK e JDK compatíveis. JDK 17 é candidato conforme AGP escolhido, não requisito independente da versão. Diagnosticar SDK/licenças/pacotes ausentes sem instalação silenciosa.
- APK debug para desenvolvimento via ADB. Distribuição a jogadores usa APK release e chave estável; segredo fora do JSON, logs e repositório. Testar atualização sem desinstalar usando a mesma identidade/assinatura.
- Copiar assets brutos inicialmente e deixar a compressão do APK ser medida. Comparar compressão padrão e `noCompress` somente se tamanho/carga justificarem. `.wasm`/`.data` não são gzip por definição e remover compressão não reduz RAM do jogo.
- Saída: APK, hashes e relatório com versão do template, hashes do runtime/conteúdo, toolchain e capacidades Android testadas. Não alterar o manifesto Web para fingir que a validação desktop vale para Android.
- AAB é etapa posterior. O limite deve ser verificado pelo tamanho de download calculado por bundletool/Play Console. Em 2026-09-20, a página específica de limites informa **500 MB para o módulo base**, enquanto guias gerais ainda citam 200 MB; usar a [tabela da Play Console](https://support.google.com/googleplay/android-developer/answer/9859372?hl=en), reconferida ao publicar. PAD exige resolver caminhos, disponibilidade dos assets e primeira abertura offline; não é só um flag de empacotamento.

### A4 — editor

Reutilizar validador Web e pré-voo existente, identificando que a execução desktop é apenas uma camada de validação. Avisar para input sem mapeamento mobile, vídeo/FFmpeg, efeitos OpenAL e threads indisponíveis.

Tamanho de arquivo ou textura permite estimativas; não prova memória total de execução. Bloquear incompatibilidades determinísticas e limites explicitamente configurados. Avisar para custos estimados; desempenho só recebe aprovação com execução no aparelho/perfil declarado.

A CLI e o editor compartilham `android-export.json`; não introduzir chaves Android em `launcher/config.json` até decidir a integração com o Panel. Isso elimina a dependência desnecessária de modificar Godot para o primeiro export Android. Traduzir mensagens novas pela infraestrutura i18n existente.

## 7. Orçamento mobile e qualidade

Definir aparelho mínimo e jogo representativo antes de fixar orçamento. Começar a medição com runtime release e resolução interna limitada (por exemplo, 1280×720 como configuração experimental), sem multiplicar automaticamente pelo DPR inteiro do aparelho. Registrar separadamente resolução CSS e do framebuffer; manter coordenadas de toque corretas.

Medir carga fria/quente, pico e estado estável de memória, frame time p50/p95/p99 e áudio em sessão de pelo menos 15 minutos. **Proposta inicial de aceite:** alvo de 30 FPS, p95 até 33,3 ms na parte jogável após aquecimento, sem OOM/crash e sem degradação sustentada abaixo do alvo ao aquecer. Se o jogo exigir 60 FPS, mudar o critério antes da comparação. Registrar transições e travadas de carga separadamente, sem escondê-las na média.

Memória inclui buffers JS de download, MEMFS, heap wasm, conteúdo descompactado, texturas/buffers GPU e processos Android. `HEAPU8.length` mede capacidade do heap, não o total utilizado pelo app. Usar ferramentas Android e registrar app/renderer quando separáveis; nem toda memória GPU será atribuída precisamente. Não adotar um teto universal de RAM com base em um único celular.

Verificar extensões e formatos de textura (inclusive DDS/S3TC) na GPU mobile. Existência de WebGL2 não garante todas as extensões vistas no desktop. Se faltar suporte, verificar o fallback do engine e medir expansão de memória, ou converter os assets do perfil.

Reduzir resolução, sombras, filtros multipass e preload antes de atribuir FPS/OOM ao WebView. Já existem LOD, instancing, culling e resolução dinâmica no engine; verificar compatibilidade Web e disponibilidade de timer queries antes de reaproveitar o ajuste dinâmico. Um gargalo de fill rate pode continuar ruim no NDK.

## 8. Validação e registro A0/A5

Nenhum resultado Android produzido nesta revisão. Criar `docs/android-manual-tests.md` durante A0; a tabela abaixo é um modelo, não evidência.

| Campo | Chrome no aparelho | APK WebView no mesmo aparelho |
|---|---|---|
| Modelo, RAM, GPU, Android, provedor/versão | Pendente | Pendente |
| Hash runtime/jogo e perfil/resolução | Pendente | Pendente |
| Carga fria/quente e primeira abertura offline | Pendente | Pendente |
| Frame time p50/p95/p99, início/fim da sessão | Pendente | Pendente |
| Memória de carga/estável/transição; OOM/context loss | Pendente | Pendente |
| Áudio, toque simultâneo, cancelamento, gamepad | Pendente | Pendente |
| Save confirmado/reabertura/atualização | Pendente | Pendente |
| Pausa/retomada, lock screen, resize, processo morto | Pendente | Pendente |
| Sensores: API, disponibilidade, taxa/latência | Opcional | Opcional |

Matriz mínima proposta: um aparelho físico no piso escolhido e outro de GPU/família diferente; emulador para smoke. Validar o jogo real pelo usuário, sem aprovar aparência com screenshot automatizado.

Casos obrigatórios antes de suporte público: primeira abertura em modo avião; salvar e reabrir; matar o processo depois de confirmação do save; atualizar o APK preservando progresso; vários ciclos Home/retorno e bloqueio de tela; mover e agir simultaneamente; verificar áudio após retomada; perda de contexto/renderer com recuperação controlada. Documentar perda possível de alterações ainda não confirmadas e que desinstalar/limpar dados remove saves locais.

Reutilizar `verify-persistence.cjs`, `verify-save.cjs` e verificações de capacidades adaptando transporte/alvo CDP. O modo touch antigo continua sendo regressão do clique, com um teste separado para multitouch. Rodar regressões Web das partes compartilhadas quando essas partes forem alteradas.

## 9. Quando reconsiderar a arquitetura

| Resultado medido | Próxima ação |
|---|---|
| API de sensor/vibração ausente, render bom | Ponte Kotlin pequena e medida, mantendo wasm. |
| Entrada digital insuficiente | Adaptador analógico explícito; API Python se o jogo precisar. |
| Gargalo de resolução, textura ou shader | Ajustar perfil/assets e medir novamente. |
| Pico de carga excessivo | Reduzir preload/cópias/conteúdo e reavaliar orçamento. |
| Limite persistente de CPU/memória/áudio atribuível à rota Web, ou necessidade real de threads/extensões nativas | Reabrir prova NDK limitada com a mesma cena e critério de aceite. |

NDK não garante ganho suficiente; exigir comparação reproduzível. Consultar `mobile-export-plan.md` e as fases Android de `android-web-export-roadmap.md` como levantamento histórico. Bloqueios registrados: Bionic/`malloc_stats`, `GL/glu.h` e backend de janela Android ausente. Reaproveitar primeiro SDL/infraestrutura existente antes de criar outro backend completo. Preservar presets, contrato de entrada e testes de persistência da trilha Web.

Kotlin mínimo é a recomendação para o escopo atual. Capacitor merece reavaliação se vários plugins nativos passarem a ser necessários. TWA é mais adequada se a estratégia virar uma PWA hospedada; pode operar offline com service worker, conforme o [guia do Chrome](https://developer.chrome.com/docs/android/trusted-web-activity/offline-first), mas muda o modelo de distribuição do pacote local.

## 10. Decisões que ainda dependem do produto

- Jogo/cena representativa, aparelho mínimo disponível e alvo de 30 ou 60 FPS.
- Controle apenas digital atende ao primeiro jogo, ou eixo analógico/inclinação é essencial desde o início?
- Distribuição para testes privados primeiro (recomendado); Play depois do aceite do APK.

Essas decisões calibram A0/A1. O próximo trabalho técnico recomendado é **A0a + APK mínimo A0b**, com resultados registrados antes de construir exportador genérico, API de sensores ou painel.
