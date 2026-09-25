# Diretórios de build e nomes oficiais

Use estes nomes em conversas, commits, changelog e planos. Sempre que se falar de "Android" ou de "build do Cycles",
diga qual dos itens abaixo é. Assim um caminho não é confundido com outro.

| Nome oficial | Diretório | Estado | O que é |
|---|---|---|---|
| **Build principal** | `build/` | ativo | Editor (`RangeEngine`) e player (`RangeRuntime`) nativos do Windows. É ele que vira release. |
| **Build Web (debug)** | `build-web/` | ativo | Runtime Emscripten de depuração (preset `web-runtime`). Pode ter SAFE_HEAP. |
| **Build Web (release)** | `build-web-release/` | ativo | Runtime Emscripten release (preset `web-runtime-release`). É a base do Android Web. |
| **Android Web (APK WebView)** | *(sem build C++ próprio)* | **ativo, é o Android oficial** | APK Kotlin com WebView carregando o pacote Web. Recompilar o C++ do Android = recompilar `build-web-release`. Ver [android-export-plan.md](android-export-plan.md) e [android-manual-tests.md](android-manual-tests.md). |
| **Android Nativo (NDK), congelado** | `build-android/` | **congelado, não é o Android oficial** | Experimento antigo de compilar a engine com o NDK. Falha com centenas de dependências ausentes, e isso é esperado. Não use como sinal de "Android quebrado". Critérios para reabrir: [android-export-plan.md](android-export-plan.md), seção 9. |
| **Sandbox do Cycles** | `build-cycles/` | teste | Cópia do build principal com `WITH_CYCLES=ON`, usada para testar o Cycles sem arriscar o `build/`. |

## Expressões e o que significam

- **"Android"**, sem qualificação, = **Android Web (APK WebView)**. Erros em `build-android/` não bloqueiam o Android.
- **"Ligar o Cycles no build principal"** = pôr `WITH_CYCLES=ON` no `build/`. Assim o editor e o player que vão para
  release passam a ter Cycles.
- **"Sandbox do Cycles"** = só o `build-cycles/`. Compilar ali não significa que o release tem Cycles.

## Antes de relatar um build quebrado

1. Confira na tabela se o diretório está **ativo**. Falha em diretório congelado não é regressão.
2. Para o Android, a validação é: `build-web-release` compila, e depois o APK é empacotado e testado no aparelho.
