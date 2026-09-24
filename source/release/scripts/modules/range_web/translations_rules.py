# Catálogos das mensagens das regras Web (resultados do painel). As chaves são os moldes em inglês
# usados com i18n.Msg nos módulos de regras; tr() traduz o molde e depois aplica os argumentos.

# molde: (pt_BR, es, ru)
_TABLE = {
    # rules_files.py
    "Host path used at runtime: %s": (
        "Caminho do host usado no runtime: %s",
        "Ruta del host usada en el runtime: %s",
        "Путь хоста используется во время выполнения: %s"),
    "Remap to the virtual FS (path relative to the game).": (
        "Remapear para o FS virtual (caminho relativo ao jogo).",
        "Reasignar al FS virtual (ruta relativa al juego).",
        "Переназначьте путь в виртуальную ФС (относительно игры)."),
    "empty path": ("caminho vazio", "ruta vacía", "пустой путь"),
    "host path without remapping": (
        "caminho do host sem remapeamento", "ruta del host sin reasignar", "путь хоста без переназначения"),
    "absolute path in the virtual FS": (
        "caminho absoluto no FS virtual", "ruta absoluta en el FS virtual", "абсолютный путь в виртуальной ФС"),
    "escapes the package root": (
        "escapa da raiz do pacote", "sale de la raíz del paquete", "выходит за корень пакета"),
    "Invalid destination %r: %s.": (
        "Destino inválido %r: %s.", "Destino no válido %r: %s.", "Недопустимое назначение %r: %s."),
    "Normalize the destination inside the package root.": (
        "Normalizar o destino dentro da raiz do pacote.",
        "Normalizar el destino dentro de la raíz del paquete.",
        "Нормализуйте назначение внутри корня пакета."),
    "Destinations collide at %r (%s and %s).": (
        "Destinos colidem em %r (%s e %s).",
        "Los destinos coinciden en %r (%s y %s).",
        "Назначения совпадают в %r (%s и %s)."),
    "Rename one of the files or remap the destination.": (
        "Renomear um dos arquivos ou remapear o destino.",
        "Renombrar uno de los archivos o reasignar el destino.",
        "Переименуйте один из файлов или переназначьте путь."),
    "Names ambiguous across platforms: %r and %r.": (
        "Nomes ambíguos entre plataformas: %r e %r.",
        "Nombres ambiguos entre plataformas: %r y %r.",
        "Имена неоднозначны на разных платформах: %r и %r."),
    "Standardize the case of the name; file systems differ.": (
        "Padronizar a caixa do nome; sistemas de arquivos diferem.",
        "Unificar mayúsculas/minúsculas del nombre; los sistemas de archivos difieren.",
        "Приведите регистр имени к одному виду; файловые системы различаются."),
    "Reference %r does not match the case of %r.": (
        "Referência %r não coincide em maiúsculas/minúsculas com %r.",
        "La referencia %r no coincide en mayúsculas/minúsculas con %r.",
        "Ссылка %r не совпадает по регистру с %r."),
    "Fix the reference to %r (the virtual FS is case-sensitive).": (
        "Corrigir a referência para %r (o FS virtual diferencia a caixa).",
        "Corregir la referencia a %r (el FS virtual distingue mayúsculas).",
        "Исправьте ссылку на %r (виртуальная ФС учитывает регистр)."),
    "%s resolves outside the declared roots.": (
        "%s resolve para fora das raízes declaradas.",
        "%s se resuelve fuera de las raíces declaradas.",
        "%s указывает за пределы объявленных корней."),
    "Keep the file inside the project root; do not follow links outside it.": (
        "Incluir o arquivo dentro da raiz do projeto; não seguir links para fora.",
        "Mantener el archivo dentro de la raíz del proyecto; no seguir enlaces hacia fuera.",
        "Держите файл внутри корня проекта; не следуйте ссылкам наружу."),
    "%s is RangeArmor content without a validated reader in the Web runtime.": (
        "%s é conteúdo RangeArmor sem leitor validado no runtime Web.",
        "%s es contenido RangeArmor sin lector validado en el runtime Web.",
        "%s — содержимое RangeArmor без проверенного загрузчика в Web-рантайме."),
    "Use the content format supported by the Web profile.": (
        "Usar o formato de conteúdo suportado pelo perfil Web.",
        "Usar el formato de contenido admitido por el perfil Web.",
        "Используйте формат содержимого, поддерживаемый Web-профилем."),
    "Host native extension required: %s.": (
        "Extensão nativa do host requerida: %s.",
        "Se requiere una extensión nativa del host: %s.",
        "Требуется нативное расширение хоста: %s."),
    "Use Python source or a Wasm module built for the runtime.": (
        "Usar fonte Python ou módulo Wasm construído para o runtime.",
        "Usar código fuente Python o un módulo Wasm compilado para el runtime.",
        "Используйте исходный код Python или Wasm-модуль, собранный для рантайма."),
    "%s has a native extension, but its content is not a recognized binary.": (
        "%s tem extensão nativa, mas o conteúdo não é binário reconhecido.",
        "%s tiene extensión nativa, pero su contenido no es un binario reconocido.",
        "%s имеет нативное расширение, но содержимое не является известным бинарным форматом."),
    "Confirm what the file is before packaging.": (
        "Confirmar o que o arquivo é antes de empacotar.",
        "Confirmar qué es el archivo antes de empaquetar.",
        "Проверьте, что это за файл, перед упаковкой."),
    "%s is truncated: not a valid .pyc.": (
        "%s truncado: não é um .pyc válido.",
        "%s está truncado: no es un .pyc válido.",
        "%s обрезан: это не корректный .pyc."),
    "Use the .py source.": ("Usar o fonte .py.", "Usar el fuente .py.", "Используйте исходник .py."),
    "%s: the runtime manifest does not state the .pyc magic.": (
        "%s: o manifesto do runtime não informa o magic do .pyc.",
        "%s: el manifiesto del runtime no indica el magic del .pyc.",
        "%s: манифест рантайма не указывает magic для .pyc."),
    "Use the .py source or a runtime whose manifest declares python.pyc_magic.": (
        "Usar o fonte .py ou um runtime cujo manifesto declare python.pyc_magic.",
        "Usar el fuente .py o un runtime cuyo manifiesto declare python.pyc_magic.",
        "Используйте исходник .py или рантайм, манифест которого объявляет python.pyc_magic."),
    "%s was compiled for another Python version.": (
        "%s foi compilado para outra versão do Python.",
        "%s se compiló para otra versión de Python.",
        "%s скомпилирован для другой версии Python."),
    "Use the .py source or recompile it with the runtime's version.": (
        "Usar o fonte .py ou recompilar com a versão do runtime.",
        "Usar el fuente .py o recompilarlo con la versión del runtime.",
        "Используйте исходник .py или перекомпилируйте версией рантайма."),

    # rules_python.py
    "Syntax error: %s": ("Erro de sintaxe: %s", "Error de sintaxis: %s", "Синтаксическая ошибка: %s"),
    "Fix the syntax (the runtime uses the grammar of the manifest's Python).": (
        "Corrigir a sintaxe (o runtime usa a gramática do Python do manifesto).",
        "Corregir la sintaxis (el runtime usa la gramática del Python del manifiesto).",
        "Исправьте синтаксис (рантайм использует грамматику Python из манифеста)."),
    "Script could not be analyzed: %s": (
        "Script não pôde ser analisado: %s",
        "No se pudo analizar el script: %s",
        "Не удалось проанализировать скрипт: %s"),
    "Check the encoding and content of the file.": (
        "Verificar codificação e conteúdo do arquivo.",
        "Comprobar la codificación y el contenido del archivo.",
        "Проверьте кодировку и содержимое файла."),
    "Custom Python main loop (%s) without a validated Web adapter.": (
        "Main loop Python personalizado (%s) sem adaptador Web validado.",
        "Main loop Python personalizado (%s) sin adaptador Web validado.",
        "Собственный главный цикл Python (%s) без проверенного Web-адаптера."),
    "Use controllers/components run every frame.": (
        "Usar controllers/components executados por frame.",
        "Usar controllers/components ejecutados en cada frame.",
        "Используйте controllers/components, выполняемые каждый кадр."),
    "Loop with no apparent exit; it may freeze the browser.": (
        "Loop sem saída aparente; pode travar o navegador.",
        "Bucle sin salida aparente; puede bloquear el navegador.",
        "Цикл без явного выхода; может заморозить браузер."),
    "Run it per frame (controller/component) instead of a blocking loop.": (
        "Executar por frame (controller/component) em vez de um laço bloqueante.",
        "Ejecutar por frame (controller/component) en lugar de un bucle bloqueante.",
        "Выполняйте по кадрам (controller/component) вместо блокирующего цикла."),
    "Import of %s (editor-only API).": (
        "Import de %s (API exclusiva do editor).",
        "Import de %s (API exclusiva del editor).",
        "Импорт %s (API только для редактора)."),
    "Separate the authoring tool from the game logic.": (
        "Separar a ferramenta de autoria da lógica do jogo.",
        "Separar la herramienta de autoría de la lógica del juego.",
        "Отделите инструмент редактора от игровой логики."),
    "Unresolved import: %s (the engine exposes the API as Range).": (
        "Import não resolvido: %s (o motor expõe a API como Range).",
        "Import no resuelto: %s (el motor expone la API como Range).",
        "Неразрешённый импорт: %s (движок предоставляет API как Range)."),
    "Replace `import bge` with `import Range` (bge.logic -> Range.logic, bge.types -> Range.types).": (
        "Trocar `import bge` por `import Range` (bge.logic -> Range.logic, bge.types -> Range.types).",
        "Cambiar `import bge` por `import Range` (bge.logic -> Range.logic, bge.types -> Range.types).",
        "Замените `import bge` на `import Range` (bge.logic -> Range.logic, bge.types -> Range.types)."),
    "Unresolved import: %s.": ("Import não resolvido: %s.", "Import no resuelto: %s.", "Неразрешённый импорт: %s."),
    "Include the module in the package or use a module present in the runtime.": (
        "Incluir o módulo no pacote ou usar um módulo presente no runtime.",
        "Incluir el módulo en el paquete o usar un módulo presente en el runtime.",
        "Включите модуль в пакет или используйте модуль, имеющийся в рантайме."),
    "Process execution: %s.": ("Execução de processo: %s.", "Ejecución de proceso: %s.", "Запуск процесса: %s."),
    "Remove it from the Web path or move it to an external service.": (
        "Remover do caminho Web ou mover para um serviço externo.",
        "Quitarlo del camino Web o moverlo a un servicio externo.",
        "Уберите это из Web-пути или перенесите во внешний сервис."),
    "Native library loading: %s.": (
        "Carregamento de biblioteca nativa: %s.",
        "Carga de biblioteca nativa: %s.",
        "Загрузка нативной библиотеки: %s."),
    "There is no host DLL/SO in the browser; use a Wasm module of the runtime.": (
        "Não há DLL/SO do host no navegador; usar módulo Wasm do runtime.",
        "No hay DLL/SO del host en el navegador; usar un módulo Wasm del runtime.",
        "В браузере нет DLL/SO хоста; используйте Wasm-модуль рантайма."),
    "Thread/process creation: %s.": (
        "Criação de thread/processo: %s.",
        "Creación de hilo/proceso: %s.",
        "Создание потока/процесса: %s."),
    "Spread the work across frames or use a validated adapter.": (
        "Distribuir o trabalho por frames ou por adaptador validado.",
        "Repartir el trabajo entre frames o usar un adaptador validado.",
        "Распределите работу по кадрам или используйте проверенный адаптер."),
    "Blocking call in script: %s.": (
        "Chamada bloqueante em script: %s.",
        "Llamada bloqueante en script: %s.",
        "Блокирующий вызов в скрипте: %s."),
    "Avoid waiting inside the frame; measure it in the browser.": (
        "Evitar espera no frame; medir no navegador.",
        "Evitar esperas dentro del frame; medir en el navegador.",
        "Избегайте ожидания внутри кадра; измерьте в браузере."),
    "%s: static analysis covers only part of the code.": (
        "%s: análise estática cobre só parte do código.",
        "%s: el análisis estático cubre solo parte del código.",
        "%s: статический анализ охватывает только часть кода."),
    "Validate this path in the browser.": (
        "Validar esse caminho no navegador.",
        "Validar este camino en el navegador.",
        "Проверьте этот путь в браузере."),
    "Dynamic import: partial static analysis.": (
        "Import dinâmico: análise estática parcial.",
        "Import dinámico: análisis estático parcial.",
        "Динамический импорт: статический анализ неполный."),
    "Declare the module explicitly and validate it in the browser.": (
        "Declarar o módulo explicitamente e validar no navegador.",
        "Declarar el módulo explícitamente y validarlo en el navegador.",
        "Объявите модуль явно и проверьте в браузере."),
    "A dynamically built module is not discovered.": (
        "Módulo formado dinamicamente não é descoberto.",
        "Un módulo formado dinámicamente no se descubre.",
        "Динамически сформированный модуль не обнаруживается."),
    "Declare the additional set of modules in the package.": (
        "Declarar o conjunto adicional de módulos no pacote.",
        "Declarar el conjunto adicional de módulos en el paquete.",
        "Объявите дополнительный набор модулей в пакете."),
    "Host path used at runtime: %s (%s).": (
        "Caminho do host usado no runtime: %s (%s).",
        "Ruta del host usada en el runtime: %s (%s).",
        "Путь хоста используется во время выполнения: %s (%s)."),

    # runtime.py / manifest.py
    "Installed runtime is %r, but the project asks for %r.": (
        "Runtime instalado é %r, mas o projeto pede %r.",
        "El runtime instalado es %r, pero el proyecto pide %r.",
        "Установлен рантайм %r, но проект требует %r."),
    "Adjust the Runtime field or install the requested runtime.": (
        "Ajustar o campo Runtime ou instalar o runtime pedido.",
        "Ajustar el campo Runtime o instalar el runtime pedido.",
        "Измените поле Runtime или установите требуемый рантайм."),
    "no directory configured": ("nenhum diretório configurado", "ningún directorio configurado", "каталоги не настроены"),
    "Runtime manifest missing (searched in: %s).": (
        "Manifesto do runtime ausente (procurado em: %s).",
        "Falta el manifiesto del runtime (buscado en: %s).",
        "Манифест рантайма отсутствует (искали в: %s)."),
    "Install a compatible Web runtime with a valid manifest; do not reuse a desktop binary.": (
        "Instalar um runtime Web compatível com manifesto válido; não reutilizar binário desktop.",
        "Instalar un runtime Web compatible con manifiesto válido; no reutilizar un binario de escritorio.",
        "Установите совместимый Web-рантайм с корректным манифестом; не используйте настольный бинарник."),
    "Runtime manifest missing.": (
        "Manifesto do runtime ausente.", "Falta el manifiesto del runtime.", "Манифест рантайма отсутствует."),
    "Unreadable runtime manifest: %s": (
        "Manifesto do runtime ilegível: %s",
        "Manifiesto del runtime ilegible: %s",
        "Манифест рантайма не читается: %s"),
    "Invalid runtime manifest: %s": (
        "Manifesto do runtime inválido: %s",
        "Manifiesto del runtime no válido: %s",
        "Некорректный манифест рантайма: %s"),
    "Reinstall the Web runtime from the build that generated the manifest.": (
        "Reinstalar o runtime Web a partir do build que gerou o manifesto.",
        "Reinstalar el runtime Web desde la compilación que generó el manifiesto.",
        "Переустановите Web-рантайм из сборки, создавшей манифест."),
    "Runtime artifact missing: %s": (
        "Artefato do runtime ausente: %s",
        "Falta un artefacto del runtime: %s",
        "Отсутствует артефакт рантайма: %s"),
    "Size of %s differs from the manifest.": (
        "Tamanho de %s diverge do manifesto.",
        "El tamaño de %s no coincide con el manifiesto.",
        "Размер %s не совпадает с манифестом."),
    "Hash of %s differs from the manifest.": (
        "Hash de %s diverge do manifesto.",
        "El hash de %s no coincide con el manifiesto.",
        "Хеш %s не совпадает с манифестом."),
    "%s requires the '%s' capability, disabled in this runtime.": (
        "%s exige a capacidade '%s', desabilitada neste runtime.",
        "%s requiere la capacidad '%s', desactivada en este runtime.",
        "%s требует возможность '%s', отключённую в этом рантайме."),
    "%s requires the '%s' capability, not yet validated in this runtime.": (
        "%s exige a capacidade '%s', ainda não validada neste runtime.",
        "%s requiere la capacidad '%s', aún no validada en este runtime.",
        "%s требует возможность '%s', ещё не проверенную в этом рантайме."),

    # collect.py / collect_bpy.py
    "%s was not found: %s.": ("%s não foi encontrado: %s.", "%s no se encontró: %s.", "%s не найден: %s."),
    "Reference without %s set.": ("Referência sem %s definido.", "Referencia sin %s definido.", "Ссылка без заданного %s."),
    "Include the file in the project or fix the controller/component reference.": (
        "Incluir o arquivo no projeto ou corrigir a referência do controller/component.",
        "Incluir el archivo en el proyecto o corregir la referencia del controller/component.",
        "Добавьте файл в проект или исправьте ссылку controller/component."),
    "Module": ("Módulo", "Módulo", "Модуль"),
    "Image": ("Imagem", "Imagen", "Изображение"),
    "%s not found: %s.": ("%s não encontrado: %s.", "%s no encontrado: %s.", "%s не найден: %s."),
    "Include/replace the asset or fix the reference.": (
        "Incluir/substituir o asset ou corrigir a referência.",
        "Incluir/sustituir el asset o corregir la referencia.",
        "Добавьте/замените ассет или исправьте ссылку."),

    # preflight.py
    "Could not read the preflight report: %s": (
        "Não foi possível ler o relatório de pré-voo: %s",
        "No se pudo leer el informe de preflight: %s",
        "Не удалось прочитать отчёт предварительной проверки: %s"),
    "Generate the report with PREFLIGHT_OUT=file.json in verify-package.cjs.": (
        "Gerar o relatório com PREFLIGHT_OUT=arquivo.json no verify-package.cjs.",
        "Generar el informe con PREFLIGHT_OUT=archivo.json en verify-package.cjs.",
        "Создайте отчёт с PREFLIGHT_OUT=файл.json в verify-package.cjs."),
    "Preflight report missing or with an unknown schema.": (
        "Relatório de pré-voo ausente ou com schema desconhecido.",
        "Informe de preflight ausente o con esquema desconocido.",
        "Отчёт предварительной проверки отсутствует или имеет неизвестную схему."),
    "Run the Web test with the preflight page of the package.": (
        "Rodar o Testar Web com a página de pré-voo do pacote.",
        "Ejecutar la prueba Web con la página de preflight del paquete.",
        "Запустите Web-тест со страницей предварительной проверки пакета."),
    "Incompatible preflight report version: %r.": (
        "Versão do relatório de pré-voo incompatível: %r.",
        "Versión del informe de preflight incompatible: %r.",
        "Несовместимая версия отчёта предварительной проверки: %r."),
    "A threaded build requires origin isolation, but the page is not isolated.": (
        "Build com threads exige isolamento de origem, mas a página não está isolada.",
        "Una compilación con hilos requiere aislamiento de origen, pero la página no está aislada.",
        "Сборка с потоками требует изоляции источника, но страница не изолирована."),
    "Serve with Cross-Origin-Opener-Policy: same-origin and "
    "Cross-Origin-Embedder-Policy: require-corp. The serial binary is a different build.": (
        "Servir com Cross-Origin-Opener-Policy: same-origin e "
        "Cross-Origin-Embedder-Policy: require-corp. O binário serial é outro build.",
        "Servir con Cross-Origin-Opener-Policy: same-origin y "
        "Cross-Origin-Embedder-Policy: require-corp. El binario serial es otra compilación.",
        "Отдавайте с Cross-Origin-Opener-Policy: same-origin и "
        "Cross-Origin-Embedder-Policy: require-corp. Последовательный бинарник — другая сборка."),
    "WebGL unavailable in the browser%s.": (
        "WebGL indisponível no navegador%s.",
        "WebGL no disponible en el navegador%s.",
        "WebGL недоступен в браузере%s."),
    "Use a browser with WebGL 2 and hardware acceleration.": (
        "Usar um navegador com WebGL 2 e aceleração de hardware.",
        "Usar un navegador con WebGL 2 y aceleración por hardware.",
        "Используйте браузер с WebGL 2 и аппаратным ускорением."),
    "Required WebGL extension missing: %s.": (
        "Extensão WebGL obrigatória ausente: %s.",
        "Falta una extensión WebGL obligatoria: %s.",
        "Отсутствует обязательное расширение WebGL: %s."),
    "no response": ("sem resposta", "sin respuesta", "нет ответа"),
    "%s did not load: %s.": ("%s não carregou: %s.", "%s no se cargó: %s.", "%s не загрузился: %s."),
    "Check the URL and whether the file was published with the package.": (
        "Conferir a URL e se o arquivo foi publicado junto do pacote.",
        "Comprobar la URL y si el archivo se publicó junto con el paquete.",
        "Проверьте URL и опубликован ли файл вместе с пакетом."),
    "%s served as %r; expected %s.": (
        "%s servido como %r; esperado %s.",
        "%s servido como %r; se esperaba %s.",
        "%s отдаётся как %r; ожидалось %s."),
    "Configure the application/wasm MIME type on the server.": (
        "Configurar o MIME application/wasm no servidor.",
        "Configurar el tipo MIME application/wasm en el servidor.",
        "Настройте MIME-тип application/wasm на сервере."),
    "%s differs from the manifest (mixed cached versions?).": (
        "%s diverge do manifesto (cache de versões misturadas?).",
        "%s no coincide con el manifiesto (¿versiones mezcladas en caché?).",
        "%s не совпадает с манифестом (смешанные версии в кэше?)."),
    "Clear the cache and republish all package files together.": (
        "Limpar o cache e republicar todos os arquivos do pacote juntos.",
        "Vaciar la caché y volver a publicar todos los archivos del paquete juntos.",
        "Очистите кэш и заново опубликуйте все файлы пакета вместе."),
    "Runtime aborted during preflight: %s.": (
        "Runtime abortou durante o pré-voo: %s.",
        "El runtime abortó durante el preflight: %s.",
        "Рантайм аварийно завершился во время проверки: %s."),
    "Check the runtime log and fix the error before publishing.": (
        "Consultar o log do runtime e corrigir o erro antes de publicar.",
        "Consultar el log del runtime y corregir el error antes de publicar.",
        "Посмотрите журнал рантайма и исправьте ошибку перед публикацией."),
    "Runtime failed during preflight: %s.": (
        "Runtime falhou durante o pré-voo: %s.",
        "El runtime falló durante el preflight: %s.",
        "Сбой рантайма во время проверки: %s."),
    "Check the runtime log and the package files.": (
        "Consultar o log do runtime e conferir os arquivos do pacote.",
        "Consultar el log del runtime y revisar los archivos del paquete.",
        "Посмотрите журнал рантайма и проверьте файлы пакета."),
    "Runtime did not finish initializing during preflight.": (
        "Runtime não concluiu a inicialização durante o pré-voo.",
        "El runtime no terminó de inicializarse durante el preflight.",
        "Рантайм не завершил инициализацию во время проверки."),
    "Increase the preflight time or fix the runtime loading failure.": (
        "Aumentar o tempo de pré-voo ou corrigir a falha de carregamento do runtime.",
        "Aumentar el tiempo de preflight o corregir el fallo de carga del runtime.",
        "Увеличьте время проверки или исправьте сбой загрузки рантайма."),
    "WebGL context lost during execution.": (
        "Contexto WebGL perdido durante a execução.",
        "Contexto WebGL perdido durante la ejecución.",
        "Контекст WebGL потерян во время выполнения."),
    "Reload the page; the game should pause or warn instead of running without rendering.": (
        "Recarregar a página; o jogo deve pausar ou avisar em vez de continuar sem render.",
        "Recargar la página; el juego debe pausar o avisar en lugar de seguir sin renderizar.",
        "Перезагрузите страницу; игра должна приостановиться или предупредить, а не работать без отрисовки."),
    "Shader did not compile (stage %s%s).": (
        "Shader não compilou (estágio %s%s).",
        "El shader no compiló (etapa %s%s).",
        "Шейдер не скомпилировался (стадия %s%s)."),
    "Import failed at runtime: %s.": (
        "Import falhou no runtime: %s.",
        "Import falló en el runtime: %s.",
        "Импорт не удался во время выполнения: %s."),
    "Include the module in the package or remove it.": (
        "Incluir o módulo no pacote ou removê-lo.",
        "Incluir el módulo en el paquete o quitarlo.",
        "Включите модуль в пакет или удалите его."),
    "File not found at runtime: %s.": (
        "Arquivo não encontrado no runtime: %s.",
        "Archivo no encontrado en el runtime: %s.",
        "Файл не найден во время выполнения: %s."),
    "Include the file in the package.": (
        "Incluir o arquivo no pacote.", "Incluir el archivo en el paquete.", "Включите файл в пакет."),
    " in %s": (" em %s", " en %s", " в %s"),
    "Error": ("Erro", "Error", "Ошибка"),
    "%s at runtime%s: %s": ("%s no runtime%s: %s", "%s en el runtime%s: %s", "%s во время выполнения%s: %s"),

    # touch.py
    "Input action %s has no binding the touch layout '%s' presses.": (
        "A ação de entrada %s não tem binding que o controle na tela '%s' aperte.",
        "La acción de entrada %s no tiene binding que el control táctil '%s' pulse.",
        "У действия ввода %s нет привязки, которую нажимает сенсорная раскладка '%s'."),
    "Choose a touch layout that presses these inputs, or add a mapping the layout reaches.": (
        "Escolha um controle na tela que aperte essas entradas ou adicione um mapeamento que ele alcance.",
        "Elija un control táctil que pulse estas entradas o añada un mapeo que alcance.",
        "Выберите сенсорную раскладку, которая нажимает эти входы, или добавьте доступную ей привязку."),
    "Keyboard sensor %s (key %s)": (
        "Sensor Keyboard %s (tecla %s)",
        "Sensor Keyboard %s (tecla %s)",
        "Сенсор Keyboard %s (клавиша %s)"),
    "Joystick sensor %s": (
        "Sensor Joystick %s",
        "Sensor Joystick %s",
        "Сенсор Joystick %s"),
    "%s is not pressed by the touch layout '%s'.": (
        "%s não é apertado pelo controle na tela '%s'.",
        "%s no es pulsado por el control táctil '%s'.",
        "%s не нажимается сенсорной раскладкой '%s'."),
    "Touch controls are off: on phones and tablets only taps reach the game.": (
        "Controle na tela desligado: em celulares e tablets só toques chegam ao jogo.",
        "Controles táctiles desactivados: en móviles y tabletas solo los toques llegan al juego.",
        "Сенсорное управление выключено: на телефонах и планшетах в игру приходят только касания."),
    "Choose a touch layout in Web (Range) > Touch controls.": (
        "Escolha um layout em Web (Range) > Controle na tela.",
        "Elija un diseño en Web (Range) > Controles táctiles.",
        "Выберите раскладку в Web (Range) > Сенсорное управление."),

    # export.py
    "%d Web error(s) block the export.": (
        "%d erro(s) Web bloqueiam o export.",
        "%d error(es) Web bloquean la exportación.",
        "Ошибок Web, блокирующих экспорт: %d."),
}

PT_BR = {k: v[0] for k, v in _TABLE.items()}
ES = {k: v[1] for k, v in _TABLE.items()}
RU = {k: v[2] for k, v in _TABLE.items()}
