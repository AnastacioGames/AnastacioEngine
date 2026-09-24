# Catálogos pt_BR, es e ru_RU do export Android (bl_ui/properties_android.py e range_web/android.py).
# Chave = texto em inglês do código. "Debug", "Release", "JDK" e "Android SDK" ficam como estão.

PT_BR = {
    # Propriedades
    "App ID": "ID do app",
    "Unique app identifier, for example com.yourstudio.yourgame. "
    "Do not change it after publishing: the phone would treat it as another app and the save is lost":
        "Identificador único do app, por exemplo com.seuestudio.seujogo. "
        "Não mude depois de publicar: o celular trataria como outro app e o save se perde",
    "App name": "Nome do app",
    "Name shown under the icon on the phone; empty uses the file name":
        "Nome mostrado embaixo do ícone no celular; vazio usa o nome do arquivo",
    "App version": "Versão do app",
    "Version shown to the player, for example 1.0": "Versão mostrada ao jogador, por exemplo 1.0",
    "Version code": "Código da versão",
    "Integer that must increase with each version for the phone to accept the update":
        "Número inteiro que precisa aumentar a cada versão para o celular aceitar a atualização",
    "App icon": "Ícone do app",
    "PNG image of the app icon (square, 512x512 recommended); empty uses the Android default":
        "Imagem PNG do ícone do app (quadrada, 512x512 recomendado); vazio usa o padrão do Android",
    "Screen orientation": "Orientação da tela",
    "Automatic": "Automática",
    "Landscape and portrait by the sensor, respecting the system rotation lock":
        "Paisagem e retrato pelo sensor, respeitando o bloqueio de rotação do sistema",
    "Landscape": "Paisagem",
    "Landscape only (both sides)": "Só paisagem (dos dois lados)",
    "Portrait": "Retrato",
    "Portrait only": "Só retrato",
    "Build type": "Tipo de build",
    "For testing on your phone; allows remote inspection (chrome://inspect)":
        "Para testar no seu celular; permite inspeção remota (chrome://inspect)",
    "Signed, for distribution to players (not available yet)":
        "Assinado, para distribuir aos jogadores (ainda não disponível)",
    "Folder of the APK, android-export.json, report and Gradle log":
        "Pasta do APK, do android-export.json, do relatório e do log do Gradle",
    "JDK folder; only used if JAVA_HOME and Android Studio are not found":
        "Pasta do JDK; só é usada se JAVA_HOME e o Android Studio não forem encontrados",
    "Android SDK folder; only used if ANDROID_HOME and Android Studio are not found":
        "Pasta do Android SDK; só é usada se ANDROID_HOME e o Android Studio não forem encontrados",

    # Painel e operadores
    "Android (Range)": "Android (Range)",
    "Tools (only if not found automatically):": "Ferramentas (só se não forem achadas sozinhas):",
    "Uses the package from the Web panel; exports it again if it is outdated.":
        "Usa o pacote do painel Web; exporta de novo se estiver desatualizado.",
    "No APK in the destination yet.": "Ainda não há APK no destino.",
    "Building APK": "Gerando APK",
    "Installing on phone": "Instalando no celular",
    "Build APK": "Gerar APK",
    "Builds the APK from the Web package with Gradle (JDK and Android SDK of Android Studio)":
        "Gera o APK a partir do pacote Web com o Gradle (JDK e Android SDK do Android Studio)",
    "Install on phone": "Instalar no celular",
    "Installs the last APK on the phone connected by USB (adb), keeping the save, and opens the game":
        "Instala o último APK no celular ligado por USB (adb), mantendo o save, e abre o jogo",

    # Mensagens
    "Web export failed; see the Web (Range) panel.": "O export Web falhou; veja o painel Web (Range).",
    "APK generated at %s": "APK gerado em %s",
    "Installed on %s and opened.": "Instalado em %s e aberto.",
    "Could not read %s: %s": "Não foi possível ler %s: %s",
    "Invalid %s: expected a JSON object.": "%s inválido: era esperado um objeto JSON.",
    "Fill in the app ID (for example com.yourstudio.yourgame).":
        "Preencha o ID do app (por exemplo com.seuestudio.seujogo).",
    "Invalid app ID %s: use at least two parts separated by dots, "
    "with letters, digits and _ (for example com.yourstudio.yourgame).":
        "ID do app inválido %s: use pelo menos duas partes separadas por ponto, "
        "com letras, números e _ (por exemplo com.seuestudio.seujogo).",
    "Fill in the app name.": "Preencha o nome do app.",
    "Fill in the version name (for example 1.0).": "Preencha a versão (por exemplo 1.0).",
    "The version code must be an integer from 1 to 2100000000.":
        "O código da versão precisa ser um inteiro de 1 a 2100000000.",
    "Invalid orientation: %s.": "Orientação inválida: %s.",
    "Invalid build type: %s.": "Tipo de build inválido: %s.",
    "Signed release build is not available yet; use debug.":
        "O build release assinado ainda não está disponível; use debug.",
    "Icon not found: %s": "Ícone não encontrado: %s",
    "The icon must be a PNG image: %s": "O ícone precisa ser uma imagem PNG: %s",
    "JDK and Android SDK not found": "JDK e Android SDK não encontrados",
    "JDK not found": "JDK não encontrado",
    "Android SDK not found": "Android SDK não encontrado",
    "%s (searched JAVA_HOME/ANDROID_HOME, Android Studio and the folders in the Android panel). "
    "Install Android Studio (it brings the JDK and the SDK) or point to the folders in the Android panel. "
    "Nothing was installed.":
        "%s (procurados em JAVA_HOME/ANDROID_HOME, no Android Studio e nas pastas do painel Android). "
        "Instale o Android Studio (ele traz o JDK e o SDK) ou indique as pastas no painel Android. "
        "Nada foi instalado.",
    "The Android SDK at %s does not have platform %d. Install it in Android Studio "
    "(SDK Manager > Android SDK Platform %d). Nothing was installed.":
        "O Android SDK em %s não tem a plataforma %d. Instale pelo Android Studio "
        "(SDK Manager > Android SDK Platform %d). Nada foi instalado.",
    "The Android SDK at %s has no Build-Tools. Install them in Android Studio "
    "(SDK Manager > SDK Tools). Nothing was installed.":
        "O Android SDK em %s não tem Build-Tools. Instale pelo Android Studio "
        "(SDK Manager > SDK Tools). Nada foi instalado.",
    "Web package not found at %s. Click Export Web first.":
        "Pacote Web não encontrado em %s. Clique em Exportar Web primeiro.",
    "Unreadable SHA256SUMS.txt in %s. Export Web again.":
        "SHA256SUMS.txt ilegível em %s. Exporte o Web de novo.",
    "Incomplete Web package: %s is missing. Export Web again.":
        "Pacote Web incompleto: falta %s. Exporte o Web de novo.",
    "Web package changed after export: %s. Export Web again.":
        "O pacote Web mudou depois do export: %s. Exporte o Web de novo.",
    "Android template changed: %s not found in %s.": "O template Android mudou: %s não encontrado em %s.",
    "Gradle failed (see %s): %s": "O Gradle falhou (veja %s): %s",
    "Gradle finished but the APK was not found at %s.": "O Gradle terminou, mas o APK não está em %s.",
    "Android template not found (tools/android/webview-template). Export from a development tree.":
        "Template Android não encontrado (tools/android/webview-template). "
        "Exporte a partir de uma árvore de desenvolvimento.",
    "adb not found at %s. Install Android SDK Platform-Tools in Android Studio.":
        "adb não encontrado em %s. Instale o Android SDK Platform-Tools pelo Android Studio.",
    "The phone did not authorize this computer. Unlock it and accept the USB debugging prompt.":
        "O celular não autorizou este computador. Desbloqueie e aceite o pedido de depuração USB.",
    "No phone connected. Connect it by USB with USB debugging enabled (Developer options).":
        "Nenhum celular conectado. Ligue por USB com a depuração USB ativada (Opções do desenvolvedor).",
    "APK not found at %s. Click Build APK first.": "APK não encontrado em %s. Clique em Gerar APK primeiro.",
    "The phone already has %s signed with another key. Uninstalling it erases the game's save; "
    "do it by hand only if you accept that.":
        "O celular já tem %s assinado com outra chave. Desinstalar apaga o save do jogo; "
        "faça isso à mão só se aceitar essa perda.",
    "The phone has a newer version of %s. Increase the version code.":
        "O celular tem uma versão mais nova de %s. Aumente o código da versão.",
    "adb install failed: %s": "adb install falhou: %s",
}

ES = {
    "App ID": "ID de la app",
    "Unique app identifier, for example com.yourstudio.yourgame. "
    "Do not change it after publishing: the phone would treat it as another app and the save is lost":
        "Identificador único de la app, por ejemplo com.tuestudio.tujuego. "
        "No lo cambies tras publicar: el móvil la trataría como otra app y se pierde la partida guardada",
    "App name": "Nombre de la app",
    "Name shown under the icon on the phone; empty uses the file name":
        "Nombre mostrado bajo el icono en el móvil; vacío usa el nombre del archivo",
    "App version": "Versión de la app",
    "Version shown to the player, for example 1.0": "Versión mostrada al jugador, por ejemplo 1.0",
    "Version code": "Código de versión",
    "Integer that must increase with each version for the phone to accept the update":
        "Entero que debe aumentar en cada versión para que el móvil acepte la actualización",
    "App icon": "Icono de la app",
    "PNG image of the app icon (square, 512x512 recommended); empty uses the Android default":
        "Imagen PNG del icono (cuadrada, 512x512 recomendado); vacío usa el de Android",
    "Screen orientation": "Orientación de pantalla",
    "Automatic": "Automática",
    "Landscape and portrait by the sensor, respecting the system rotation lock":
        "Horizontal y vertical según el sensor, respetando el bloqueo de rotación del sistema",
    "Landscape": "Horizontal",
    "Landscape only (both sides)": "Solo horizontal (ambos lados)",
    "Portrait": "Vertical",
    "Portrait only": "Solo vertical",
    "Build type": "Tipo de build",
    "For testing on your phone; allows remote inspection (chrome://inspect)":
        "Para probar en tu móvil; permite inspección remota (chrome://inspect)",
    "Signed, for distribution to players (not available yet)":
        "Firmado, para distribuir a los jugadores (aún no disponible)",
    "Folder of the APK, android-export.json, report and Gradle log":
        "Carpeta del APK, android-export.json, informe y log de Gradle",
    "JDK folder; only used if JAVA_HOME and Android Studio are not found":
        "Carpeta del JDK; solo se usa si no se encuentran JAVA_HOME ni Android Studio",
    "Android SDK folder; only used if ANDROID_HOME and Android Studio are not found":
        "Carpeta del Android SDK; solo se usa si no se encuentran ANDROID_HOME ni Android Studio",
    "Android (Range)": "Android (Range)",
    "Tools (only if not found automatically):": "Herramientas (solo si no se encuentran solas):",
    "Uses the package from the Web panel; exports it again if it is outdated.":
        "Usa el paquete del panel Web; lo exporta de nuevo si está desactualizado.",
    "No APK in the destination yet.": "Aún no hay APK en el destino.",
    "Building APK": "Generando APK",
    "Installing on phone": "Instalando en el móvil",
    "Build APK": "Generar APK",
    "Builds the APK from the Web package with Gradle (JDK and Android SDK of Android Studio)":
        "Genera el APK desde el paquete Web con Gradle (JDK y Android SDK de Android Studio)",
    "Install on phone": "Instalar en el móvil",
    "Installs the last APK on the phone connected by USB (adb), keeping the save, and opens the game":
        "Instala el último APK en el móvil conectado por USB (adb), conservando la partida, y abre el juego",
    "Web export failed; see the Web (Range) panel.": "La exportación Web falló; mira el panel Web (Range).",
    "APK generated at %s": "APK generado en %s",
    "Installed on %s and opened.": "Instalado en %s y abierto.",
    "Fill in the app ID (for example com.yourstudio.yourgame).":
        "Rellena el ID de la app (por ejemplo com.tuestudio.tujuego).",
    "Fill in the app name.": "Rellena el nombre de la app.",
    "Signed release build is not available yet; use debug.":
        "El build release firmado aún no está disponible; usa debug.",
    "JDK and Android SDK not found": "JDK y Android SDK no encontrados",
    "JDK not found": "JDK no encontrado",
    "Android SDK not found": "Android SDK no encontrado",
    "%s (searched JAVA_HOME/ANDROID_HOME, Android Studio and the folders in the Android panel). "
    "Install Android Studio (it brings the JDK and the SDK) or point to the folders in the Android panel. "
    "Nothing was installed.":
        "%s (buscados en JAVA_HOME/ANDROID_HOME, Android Studio y las carpetas del panel Android). "
        "Instala Android Studio (trae el JDK y el SDK) o indica las carpetas en el panel Android. "
        "No se instaló nada.",
    "No phone connected. Connect it by USB with USB debugging enabled (Developer options).":
        "Ningún móvil conectado. Conéctalo por USB con la depuración USB activada (Opciones de desarrollador).",
    "The phone did not authorize this computer. Unlock it and accept the USB debugging prompt.":
        "El móvil no autorizó este equipo. Desbloquéalo y acepta la depuración USB.",
}

RU = {
    "App ID": "ID приложения",
    "App name": "Название приложения",
    "App version": "Версия приложения",
    "Version code": "Код версии",
    "App icon": "Значок приложения",
    "Screen orientation": "Ориентация экрана",
    "Automatic": "Автоматически",
    "Landscape": "Альбомная",
    "Portrait": "Портретная",
    "Build type": "Тип сборки",
    "Android (Range)": "Android (Range)",
    "Tools (only if not found automatically):": "Инструменты (только если не найдены автоматически):",
    "No APK in the destination yet.": "В папке назначения ещё нет APK.",
    "Building APK": "Сборка APK",
    "Installing on phone": "Установка на телефон",
    "Build APK": "Собрать APK",
    "Install on phone": "Установить на телефон",
    "APK generated at %s": "APK создан в %s",
    "Installed on %s and opened.": "Установлено на %s и запущено.",
    "Fill in the app ID (for example com.yourstudio.yourgame).":
        "Укажите ID приложения (например, com.yourstudio.yourgame).",
    "JDK and Android SDK not found": "JDK и Android SDK не найдены",
    "JDK not found": "JDK не найден",
    "Android SDK not found": "Android SDK не найден",
    "No phone connected. Connect it by USB with USB debugging enabled (Developer options).":
        "Телефон не подключён. Подключите его по USB с включённой отладкой по USB (параметры разработчика).",
}
