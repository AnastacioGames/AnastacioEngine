# Export Android reaproveitando o runtime Web

Estado: **Android v1 concluído em 2026-09-24**: APK/AAB com WebView embutindo o pacote Web, export pelo editor,
release assinado, controles por toque e sensores, validados em aparelho físico. Histórico em
[changelog-arquivo.md](changelog-arquivo.md) (entradas de 2026-09-20 a 2026-09-25). Testes em aparelho:
[android-manual-tests.md](android-manual-tests.md). Controles: [android-touch-controls-plan.md](android-touch-controls-plan.md).
Pendências gerais: [roadmap.md](roadmap.md) (seção "Android / iOS").

Fora do escopo: iOS, editor em tablet, WebGL1/GLES2, multiplayer nativo, threads wasm e Play Asset Delivery.
Rota nativa (NDK) abandonada em 2026-10-17.

## 1. Etapas

| Etapa | Estado |
|---|---|
| A0a/A0b — prova no aparelho | Feita: template `tools/android/webview-template/` (Kotlin + `WebViewAssetLoader`) no Find X3 Pro e Tab S6 Lite |
| A1 — controles por toque | Feito (T0–T5); ver plano de controles |
| A2 — ciclo de vida e save | Feito: pausa/retomada, áudio suspenso em segundo plano, IDBFS persiste e sobrevive a atualização |
| A3 — CLI | Feita: `tools/web/package-android.py` chama `source/release/scripts/modules/range_web/android.py` |
| A4 — editor | Feito: painel "Android (Range)" (`bl_ui/properties_android.py`) |
| AAB | Feito: `--aab` / "Also build AAB (Google Play)", verificado com `bundletool` |
| A5 — aceite amplo | Parcial: dois aparelhos; ver pendências |

## 2. Pendências

- Envio a uma faixa de teste da Play Console (adiado por decisão do usuário). Conferir o limite de download pelo
  bundletool/Play Console: em 2026-09-20 a tabela informava 500 MB para o módulo base, guias gerais citavam
  200 MB ([tabela](https://support.google.com/googleplay/android-developer/answer/9859372?hl=en)). Reconferir
  `targetSdk` exigido (API 36 em 2026-09-20) pela [política](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en).
- Release 0.5.0 sem `web/android-template` no zip Windows e sem `web/` no tar Linux: corrigido no código; falta
  publicar e rodar o pacote Linux (ver roadmap).
- Casos ainda sem registro em aparelho: primeira abertura em modo avião, bloqueio de tela, perda de contexto
  WebGL/renderer com recuperação controlada, sessão de 15 min no jogo real (só a cena padrão parada foi medida).
- O aceite antigo no Chrome foi no OPPO Reno14; as medidas usaram Find X3 Pro e Tab S6 Lite.
- Frame do runtime acima de 16,7 ms no Find X3 Pro (custo de CPU por quadro, não WebView): otimização M4.
- Gamepad físico no Web a reconferir após o patch SDL2.
- Depois, se um jogo precisar: API Python de toque (`logic.touches`), vibração, ponte Kotlin para sensores
  (`SensorManager`) se a API Web faltar.

## 5. Casca WebView e ciclo de vida

Referência do template (citada em `app/build.gradle.kts`).

- Serve `assets/www/` por `https://appassets.androidplatform.net/assets/www/index.html`, MIME `application/wasm`,
  sem permissão `INTERNET`, sem service worker nem servidor local. Host, diretório de dados e identidade do app
  ficam estáveis entre atualizações.
- `minSdk 24` é **hipótese de cobertura**: a versão do SO não prova WebGL2/wasm do provedor WebView. Testado até
  agora em Android 13 e 14.
- Navegação externa sai para o navegador; sem acesso amplo por `file://`; depuração remota só no build debug.
- `launchMode="singleTask"`; rotação `fullUser`; pointer lock vira no-op no APK (o WebView rejeita).
- Pausa: liberar entradas, suspender áudio, flush de save. O callback Android não bloqueia esperando JS.
  `saveGlobalDict()` retornar não significa que o `syncfs` terminou; salvar em checkpoints.
- Processo morto: o jogo recarrega do zero; o estado da partida não volta (sem restauração de sessão).
- Pthreads fora do plano; COOP/COEP sozinhos não provam suporte.

## 6. Empacotamento (A3/A4)

- `package-android.py` consome a pasta de `package-web.py`, confere hashes e aplica `android-export.json`
  (applicationId, versionCode, versionName, nome, ícone, orientação, chave, `aab`). Não altera o manifesto Web.
- Chave PKCS12 criada pelo keytool ("Criar chave" ou `--create-keystore`), recusada dentro de repositório git e
  nunca sobrescrita. Senha só por `RANGE_ANDROID_KEYSTORE_PASSWORD` ou campo de sessão do painel (fora do `.blend`,
  JSON, log e relatório). APK conferido pelo `apksigner`; relatório guarda o SHA-256 do certificado.
- Teste `engine_android_export.py` só instala com `RANGE_ANDROID_TEST_INSTALL=1`.
- Não colocar chaves Android em `launcher/config.json` até decidir a integração com o Panel.

## 9. Quando reconsiderar a arquitetura

| Resultado medido | Próxima ação |
|---|---|
| API de sensor/vibração ausente, render bom | Ponte Kotlin pequena, mantendo wasm |
| Entrada digital insuficiente | Adaptador analógico explícito; API Python se o jogo precisar |
| Gargalo de resolução, textura ou shader | Ajustar perfil/assets e medir de novo |
| Limite de CPU/memória/áudio atribuível à rota Web, ou necessidade real de threads | Reabrir prova NDK limitada, com a mesma cena e critério |

Capacitor vale reavaliar se vários plugins nativos forem necessários; TWA, se a estratégia virar PWA hospedada.
