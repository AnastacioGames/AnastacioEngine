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
    # Release assinado
    "Signed with your key, for distribution to players": "Assinado com a sua chave, para distribuir aos jogadores",
    "Signing key": "Chave de assinatura",
    "Key file (.jks) of the release, outside git and with a backup. "
    "Updates only install if signed with the same key: losing it means publishing as a new app":
        "Arquivo da chave (.jks) do release, fora do git e com cópia de segurança. "
        "Atualizações só instalam se assinadas com a mesma chave: perder a chave obriga a publicar como outro app",
    "Key alias": "Alias da chave",
    "Name of the key inside the key file": "Nome da chave dentro do arquivo",
    "Key password": "Senha da chave",
    "Password of the signing key; kept only while the editor is open, never saved in the file":
        "Senha da chave de assinatura; fica só enquanto o editor está aberto, nunca é salva no arquivo",
    "Create key": "Criar chave",
    "Creates the release signing key with the JDK keytool, in the file chosen in Signing key":
        "Cria a chave de assinatura do release com o keytool do JDK, no arquivo escolhido em Chave de assinatura",
    "Keep the key and the password with a backup: updates need the same key.":
        "Guarde a chave e a senha com cópia de segurança: as atualizações precisam da mesma chave.",
    "Key created at %s. Back up the file and the password.":
        "Chave criada em %s. Faça cópia de segurança do arquivo e da senha.",
    "Release needs a signing key: choose the key file or create one.":
        "O release precisa de uma chave de assinatura: escolha o arquivo da chave ou crie uma.",
    "The signing key must stay outside git repositories (%s is inside %s). "
    "Keep it in a private folder with a backup.":
        "A chave de assinatura precisa ficar fora de repositórios git (%s está dentro de %s). "
        "Guarde numa pasta particular, com cópia de segurança.",
    "Signing key not found: %s": "Chave de assinatura não encontrada: %s",
    "Fill in the key alias.": "Preencha o alias da chave.",
    "Type the signing key password (or set %s).": "Digite a senha da chave de assinatura (ou defina %s).",
    "The key password needs at least %d characters.": "A senha da chave precisa de pelo menos %d caracteres.",
    "%s already exists; a signing key is never overwritten.":
        "%s já existe; uma chave de assinatura nunca é sobrescrita.",
    "keytool failed: %s": "O keytool falhou: %s",
    "Wrong password for the signing key %s.": "Senha errada para a chave de assinatura %s.",
    "The signing key %s has no alias %s.": "A chave de assinatura %s não tem o alias %s.",
    "The release APK is not signed (apksigner could not verify %s).":
        "O APK release não está assinado (o apksigner não conseguiu verificar %s).",
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
    "Signed with your key, for distribution to players": "Firmado con tu clave, para distribuir a los jugadores",
    "Signing key": "Clave de firma",
    "Key alias": "Alias de la clave",
    "Key password": "Contraseña de la clave",
    "Create key": "Crear clave",
    "Keep the key and the password with a backup: updates need the same key.":
        "Guarda la clave y la contraseña con copia de seguridad: las actualizaciones necesitan la misma clave.",
    "Key created at %s. Back up the file and the password.":
        "Clave creada en %s. Haz copia de seguridad del archivo y de la contraseña.",
    "Release needs a signing key: choose the key file or create one.":
        "El release necesita una clave de firma: elige el archivo de la clave o crea una.",
    "Type the signing key password (or set %s).": "Escribe la contraseña de la clave de firma (o define %s).",
    "Wrong password for the signing key %s.": "Contraseña incorrecta para la clave de firma %s.",
    "Could not read %s: %s": "No se pudo leer %s: %s",
    "Invalid %s: expected a JSON object.": "%s no válido: se esperaba un objeto JSON.",
    "Invalid app ID %s: use at least two parts separated by dots, "
    "with letters, digits and _ (for example com.yourstudio.yourgame).":
        "ID de app no válido %s: usa al menos dos partes separadas por puntos, "
        "con letras, dígitos y _ (por ejemplo com.tuestudio.tujuego).",
    "Fill in the version name (for example 1.0).": "Rellena la versión (por ejemplo 1.0).",
    "The version code must be an integer from 1 to 2100000000.":
        "El código de versión debe ser un entero de 1 a 2100000000.",
    "Invalid orientation: %s.": "Orientación no válida: %s.",
    "Invalid build type: %s.": "Tipo de build no válido: %s.",
    "Icon not found: %s": "Icono no encontrado: %s",
    "The icon must be a PNG image: %s": "El icono debe ser una imagen PNG: %s",
    "The Android SDK at %s does not have platform %d. Install it in Android Studio "
    "(SDK Manager > Android SDK Platform %d). Nothing was installed.":
        "El Android SDK en %s no tiene la plataforma %d. Instálala en Android Studio "
        "(SDK Manager > Android SDK Platform %d). No se instaló nada.",
    "The Android SDK at %s has no Build-Tools. Install them in Android Studio "
    "(SDK Manager > SDK Tools). Nothing was installed.":
        "El Android SDK en %s no tiene Build-Tools. Instálalas en Android Studio "
        "(SDK Manager > SDK Tools). No se instaló nada.",
    "Web package not found at %s. Click Export Web first.":
        "Paquete Web no encontrado en %s. Haz clic primero en Exportar Web.",
    "Unreadable SHA256SUMS.txt in %s. Export Web again.": "SHA256SUMS.txt ilegible en %s. Exporta Web de nuevo.",
    "Incomplete Web package: %s is missing. Export Web again.":
        "Paquete Web incompleto: falta %s. Exporta Web de nuevo.",
    "Web package changed after export: %s. Export Web again.":
        "El paquete Web cambió después de exportar: %s. Exporta Web de nuevo.",
    "Android template changed: %s not found in %s.": "La plantilla Android cambió: %s no está en %s.",
    "Gradle failed (see %s): %s": "Gradle falló (mira %s): %s",
    "Gradle finished but the APK was not found at %s.": "Gradle terminó, pero el APK no está en %s.",
    "Android template not found (tools/android/webview-template). Export from a development tree.":
        "Plantilla Android no encontrada (tools/android/webview-template). "
        "Exporta desde un árbol de desarrollo.",
    "adb not found at %s. Install Android SDK Platform-Tools in Android Studio.":
        "adb no encontrado en %s. Instala Android SDK Platform-Tools en Android Studio.",
    "APK not found at %s. Click Build APK first.": "APK no encontrado en %s. Haz clic primero en Generar APK.",
    "The phone already has %s signed with another key. Uninstalling it erases the game's save; "
    "do it by hand only if you accept that.":
        "El móvil ya tiene %s firmado con otra clave. Desinstalarlo borra el guardado del juego; "
        "hazlo a mano solo si lo aceptas.",
    "The phone has a newer version of %s. Increase the version code.":
        "El móvil tiene una versión más nueva de %s. Aumenta el código de versión.",
    "adb install failed: %s": "adb install falló: %s",
    "Key file (.jks) of the release, outside git and with a backup. "
    "Updates only install if signed with the same key: losing it means publishing as a new app":
        "Archivo de clave (.jks) del release, fuera de git y con copia de seguridad. "
        "Las actualizaciones solo se instalan firmadas con la misma clave: perderla obliga a publicar como otra app",
    "Name of the key inside the key file": "Nombre de la clave dentro del archivo",
    "Password of the signing key; kept only while the editor is open, never saved in the file":
        "Contraseña de la clave de firma; solo dura mientras el editor está abierto, nunca se guarda en el archivo",
    "Creates the release signing key with the JDK keytool, in the file chosen in Signing key":
        "Crea la clave de firma del release con el keytool del JDK, en el archivo elegido en Clave de firma",
    "The signing key must stay outside git repositories (%s is inside %s). "
    "Keep it in a private folder with a backup.":
        "La clave de firma debe quedar fuera de repositorios git (%s está dentro de %s). "
        "Guárdala en una carpeta privada, con copia de seguridad.",
    "Signing key not found: %s": "Clave de firma no encontrada: %s",
    "Fill in the key alias.": "Rellena el alias de la clave.",
    "The key password needs at least %d characters.": "La contraseña de la clave necesita al menos %d caracteres.",
    "%s already exists; a signing key is never overwritten.": "%s ya existe; una clave de firma nunca se sobrescribe.",
    "keytool failed: %s": "keytool falló: %s",
    "The signing key %s has no alias %s.": "La clave de firma %s no tiene el alias %s.",
    "The release APK is not signed (apksigner could not verify %s).":
        "El APK release no está firmado (apksigner no pudo verificar %s).",
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
    "Unique app identifier, for example com.yourstudio.yourgame. "
    "Do not change it after publishing: the phone would treat it as another app and the save is lost":
        "Уникальный идентификатор приложения, например com.yourstudio.yourgame. "
        "Не меняйте его после публикации: телефон сочтёт это другим приложением, и сохранение пропадёт",
    "Name shown under the icon on the phone; empty uses the file name":
        "Название под значком на телефоне; если пусто, используется имя файла",
    "Version shown to the player, for example 1.0": "Версия, которую видит игрок, например 1.0",
    "Integer that must increase with each version for the phone to accept the update":
        "Целое число, которое должно расти с каждой версией, чтобы телефон принял обновление",
    "PNG image of the app icon (square, 512x512 recommended); empty uses the Android default":
        "PNG-изображение значка (квадратное, рекомендуется 512x512); если пусто, используется значок Android",
    "Landscape and portrait by the sensor, respecting the system rotation lock":
        "Альбомная и портретная по датчику, с учётом системной блокировки поворота",
    "Landscape only (both sides)": "Только альбомная (обе стороны)",
    "Portrait only": "Только портретная",
    "For testing on your phone; allows remote inspection (chrome://inspect)":
        "Для проверки на своём телефоне; разрешает удалённую отладку (chrome://inspect)",
    "Folder of the APK, android-export.json, report and Gradle log":
        "Папка для APK, android-export.json, отчёта и журнала Gradle",
    "JDK folder; only used if JAVA_HOME and Android Studio are not found":
        "Папка JDK; используется, только если не найдены JAVA_HOME и Android Studio",
    "Android SDK folder; only used if ANDROID_HOME and Android Studio are not found":
        "Папка Android SDK; используется, только если не найдены ANDROID_HOME и Android Studio",
    "Uses the package from the Web panel; exports it again if it is outdated.":
        "Использует пакет из панели Web; экспортирует его заново, если он устарел.",
    "Builds the APK from the Web package with Gradle (JDK and Android SDK of Android Studio)":
        "Собирает APK из пакета Web с помощью Gradle (JDK и Android SDK из Android Studio)",
    "Installs the last APK on the phone connected by USB (adb), keeping the save, and opens the game":
        "Устанавливает последний APK на телефон по USB (adb), сохраняя прогресс, и запускает игру",
    "Web export failed; see the Web (Range) panel.": "Экспорт Web не удался; см. панель Web (Range).",
    "Could not read %s: %s": "Не удалось прочитать %s: %s",
    "Invalid %s: expected a JSON object.": "Неверный %s: ожидался объект JSON.",
    "Invalid app ID %s: use at least two parts separated by dots, "
    "with letters, digits and _ (for example com.yourstudio.yourgame).":
        "Неверный ID приложения %s: нужно минимум две части через точку, "
        "из букв, цифр и _ (например, com.yourstudio.yourgame).",
    "Fill in the app name.": "Укажите название приложения.",
    "Fill in the version name (for example 1.0).": "Укажите версию (например, 1.0).",
    "The version code must be an integer from 1 to 2100000000.":
        "Код версии должен быть целым числом от 1 до 2100000000.",
    "Invalid orientation: %s.": "Неверная ориентация: %s.",
    "Invalid build type: %s.": "Неверный тип сборки: %s.",
    "Icon not found: %s": "Значок не найден: %s",
    "The icon must be a PNG image: %s": "Значок должен быть изображением PNG: %s",
    "%s (searched JAVA_HOME/ANDROID_HOME, Android Studio and the folders in the Android panel). "
    "Install Android Studio (it brings the JDK and the SDK) or point to the folders in the Android panel. "
    "Nothing was installed.":
        "%s (поиск в JAVA_HOME/ANDROID_HOME, Android Studio и папках панели Android). "
        "Установите Android Studio (в нём есть JDK и SDK) или укажите папки в панели Android. "
        "Ничего не было установлено.",
    "The Android SDK at %s does not have platform %d. Install it in Android Studio "
    "(SDK Manager > Android SDK Platform %d). Nothing was installed.":
        "В Android SDK в %s нет платформы %d. Установите её в Android Studio "
        "(SDK Manager > Android SDK Platform %d). Ничего не было установлено.",
    "The Android SDK at %s has no Build-Tools. Install them in Android Studio "
    "(SDK Manager > SDK Tools). Nothing was installed.":
        "В Android SDK в %s нет Build-Tools. Установите их в Android Studio "
        "(SDK Manager > SDK Tools). Ничего не было установлено.",
    "Web package not found at %s. Click Export Web first.":
        "Пакет Web не найден в %s. Сначала нажмите «Экспорт Web».",
    "Unreadable SHA256SUMS.txt in %s. Export Web again.":
        "Не удаётся прочитать SHA256SUMS.txt в %s. Экспортируйте Web заново.",
    "Incomplete Web package: %s is missing. Export Web again.":
        "Неполный пакет Web: нет %s. Экспортируйте Web заново.",
    "Web package changed after export: %s. Export Web again.":
        "Пакет Web изменился после экспорта: %s. Экспортируйте Web заново.",
    "Android template changed: %s not found in %s.": "Шаблон Android изменился: %s не найдено в %s.",
    "Gradle failed (see %s): %s": "Ошибка Gradle (см. %s): %s",
    "Gradle finished but the APK was not found at %s.": "Gradle завершился, но APK не найден в %s.",
    "Android template not found (tools/android/webview-template). Export from a development tree.":
        "Шаблон Android не найден (tools/android/webview-template). Экспортируйте из дерева разработки.",
    "adb not found at %s. Install Android SDK Platform-Tools in Android Studio.":
        "adb не найден в %s. Установите Android SDK Platform-Tools в Android Studio.",
    "The phone did not authorize this computer. Unlock it and accept the USB debugging prompt.":
        "Телефон не разрешил доступ этому компьютеру. Разблокируйте его и примите запрос отладки по USB.",
    "APK not found at %s. Click Build APK first.": "APK не найден в %s. Сначала нажмите «Собрать APK».",
    "The phone already has %s signed with another key. Uninstalling it erases the game's save; "
    "do it by hand only if you accept that.":
        "На телефоне уже есть %s, подписанное другим ключом. Удаление сотрёт сохранение игры; "
        "делайте это вручную, только если согласны.",
    "The phone has a newer version of %s. Increase the version code.":
        "На телефоне более новая версия %s. Увеличьте код версии.",
    "adb install failed: %s": "Ошибка adb install: %s",
    "Signed with your key, for distribution to players": "Подписано вашим ключом, для распространения игрокам",
    "Signing key": "Ключ подписи",
    "Key file (.jks) of the release, outside git and with a backup. "
    "Updates only install if signed with the same key: losing it means publishing as a new app":
        "Файл ключа (.jks) для релиза, вне git и с резервной копией. "
        "Обновления ставятся, только если подписаны тем же ключом: потеря ключа означает публикацию как нового приложения",
    "Key alias": "Псевдоним ключа",
    "Name of the key inside the key file": "Имя ключа внутри файла",
    "Key password": "Пароль ключа",
    "Password of the signing key; kept only while the editor is open, never saved in the file":
        "Пароль ключа подписи; хранится только пока открыт редактор и никогда не сохраняется в файл",
    "Create key": "Создать ключ",
    "Creates the release signing key with the JDK keytool, in the file chosen in Signing key":
        "Создаёт ключ подписи релиза с помощью keytool из JDK в файле, указанном в «Ключ подписи»",
    "Keep the key and the password with a backup: updates need the same key.":
        "Храните ключ и пароль с резервной копией: для обновлений нужен тот же ключ.",
    "Key created at %s. Back up the file and the password.":
        "Ключ создан в %s. Сделайте резервную копию файла и пароля.",
    "Release needs a signing key: choose the key file or create one.":
        "Для релиза нужен ключ подписи: выберите файл ключа или создайте его.",
    "The signing key must stay outside git repositories (%s is inside %s). "
    "Keep it in a private folder with a backup.":
        "Ключ подписи должен находиться вне репозиториев git (%s внутри %s). "
        "Храните его в личной папке с резервной копией.",
    "Signing key not found: %s": "Ключ подписи не найден: %s",
    "Fill in the key alias.": "Укажите псевдоним ключа.",
    "Type the signing key password (or set %s).": "Введите пароль ключа подписи (или задайте %s).",
    "The key password needs at least %d characters.": "Пароль ключа должен содержать не менее %d символов.",
    "%s already exists; a signing key is never overwritten.": "%s уже существует; ключ подписи никогда не перезаписывается.",
    "keytool failed: %s": "Ошибка keytool: %s",
    "Wrong password for the signing key %s.": "Неверный пароль для ключа подписи %s.",
    "The signing key %s has no alias %s.": "В ключе подписи %s нет псевдонима %s.",
    "The release APK is not signed (apksigner could not verify %s).":
        "APK релиза не подписан (apksigner не смог проверить %s).",
}
