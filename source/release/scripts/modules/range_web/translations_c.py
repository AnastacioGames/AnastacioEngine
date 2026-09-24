# Textos de interface escritos em C (IFACE_/TIP_/N_ fora do RNA) que o catalogo do Blender 2.79 nao traduz em
# nenhum dos idiomas. Levantados por tools/tests/web_profile/i18n_scan_c.py; es/ru pedem revisao nativa.
# Ordem de cada linha: ingles (texto do codigo), pt_BR, es, ru. Textos que ja estao nos outros dicionarios vencem.
# Ficam de fora codigos e nomes (X:, RGB, Hex, Ctrl, Python, Range Engine) e as portas logicas (And, Or, Xor...).

TABLE = (
    # Cache, modificadores de curva e transformacao
    ("%s frames in memory (%s)", "%s quadros na memória (%s)", "%s fotogramas en memoria (%s)",
     "%s кадров в памяти (%s)"),
    ("Envelope", "Envelope", "Envolvente", "Огибающая"),
    ("Envelope:", "Envelope:", "Envolvente:", "Огибающая:"),
    ("Envelope: %s", "Envelope: %s", "Envolvente: %s", "Огибающая: %s"),
    ("Envelope: %3f", "Envelope: %3f", "Envolvente: %3f", "Огибающая: %3f"),
    ("(Linear)", "(Linear)", "(Lineal)", "(Линейно)"),

    # Menus de contexto, cabecalhos e seletor de tela
    ("Rename...", "Renomear...", "Renombrar...", "Переименовать..."),
    ("Edit Driver", "Editar driver", "Editar controlador", "Редактировать драйвер"),
    ("Open Drivers Editor", "Abrir editor de drivers", "Abrir editor de controladores", "Открыть редактор драйверов"),
    ("Animate property", "Animar propriedade", "Animar propiedad", "Анимировать свойство"),
    ("Switch to this screen", "Mudar para esta tela", "Cambiar a esta pantalla", "Переключиться на этот экран"),
    ("Change editor type", "Mudar o tipo de editor", "Cambiar el tipo de editor", "Изменить тип редактора"),

    # Editor de drivers e de curvas
    ("Driven Property:", "Propriedade controlada:", "Propiedad controlada:", "Управляемое свойство:"),
    ("Driven Property", "Propriedade controlada", "Propiedad controlada", "Управляемое свойство"),
    ("Driver Settings:", "Configurações do driver:", "Configuración del controlador:", "Настройки драйвера:"),
    ("Show in Drivers Editor", "Mostrar no editor de drivers", "Mostrar en el editor de controladores",
     "Показать в редакторе драйверов"),
    ("Add/Edit Driver", "Adicionar/editar driver", "Añadir/editar controlador", "Добавить/изменить драйвер"),
    ("Cursor X", "Cursor X", "Cursor X", "Курсор X"),
    ("Cursor Y", "Cursor Y", "Cursor Y", "Курсор Y"),
    ("Auto Handle Smoothing:", "Suavização automática de alças:", "Suavizado automático de manijas:",
     "Автосглаживание рукояток:"),
    ("Expression:", "Expressão:", "Expresión:", "Выражение:"),
    ("Add Input Variable", "Adicionar variável de entrada", "Añadir variable de entrada", "Добавить входную переменную"),
    ("Driver variables ensure that all dependencies will be accounted for, eusuring that drivers will update correctly",
     "As variáveis do driver garantem que todas as dependências sejam consideradas, para que os drivers "
     "atualizem corretamente",
     "Las variables del controlador garantizan que se tengan en cuenta todas las dependencias, para que los "
     "controladores se actualicen correctamente",
     "Переменные драйвера учитывают все зависимости, чтобы драйверы обновлялись правильно"),
    ("Force updates of dependencies - Only use this if drivers are not updating correctly",
     "Força a atualização das dependências - use só se os drivers não atualizarem corretamente",
     "Fuerza la actualización de las dependencias - úsalo solo si los controladores no se actualizan correctamente",
     "Принудительно обновлять зависимости - используйте, только если драйверы не обновляются правильно"),

    # Barra de informacoes e painel N da vista 3D
    (" | Free GPU Mem: %s", " | Mem. GPU livre: %s", " | Mem. GPU libre: %s", " | Своб. память GPU: %s"),
    ("Global", "Global", "Global", "Глобально"),
    ("Local", "Local", "Local", "Локально"),

    # Logic bricks
    ("Mouse", "Mouse", "Ratón", "Мышь"),
    ("Radar", "Radar", "Radar", "Радар"),
    ("Skip dt", "Pular dt", "Saltar dt", "Пропуск dt"),
    ("Add an animation event to the object!", "Adicione um evento de animação ao objeto!",
     "¡Añade un evento de animación al objeto!", "Добавьте объекту событие анимации!"),
    ("Event Index:", "Índice do evento:", "Índice del evento:", "Индекс события:"),
    ("Trigger index:", "Índice de disparo:", "Índice de disparo:", "Индекс срабатывания:"),

    # Editor de nos
    ("Matte Objects:", "Objetos de máscara:", "Objetos de máscara:", "Объекты маски:"),
    ("Add Crypto Layer", "Adicionar camada Crypto", "Añadir capa Crypto", "Добавить слой Crypto"),
    ("Remove Crypto Layer", "Remover camada Crypto", "Quitar capa Crypto", "Удалить слой Crypto"),
    ("Disabled, built without OpenImageDenoise", "Desativado, compilado sem OpenImageDenoise",
     "Desactivado, compilado sin OpenImageDenoise", "Отключено, собрано без OpenImageDenoise"),
    ("Interface", "Interface", "Interfaz", "Интерфейс"),
    ("Albedo", "Albedo", "Albedo", "Альбедо"),
    ("Script", "Script", "Script", "Скрипт"),
    ("Melanin", "Melanina", "Melanina", "Меланин"),
    ("Melanin Redness", "Vermelhidão da melanina", "Rojez de la melanina", "Краснота меланина"),
    ("Absorption Coefficient", "Coeficiente de absorção", "Coeficiente de absorción", "Коэффициент поглощения"),
    ("Radial Roughness", "Rugosidade radial", "Rugosidad radial", "Радиальная шероховатость"),
    ("Coat", "Revestimento", "Capa", "Покрытие"),
    ("Random Color", "Cor aleatória", "Color aleatorio", "Случайный цвет"),
    ("Random Roughness", "Rugosidade aleatória", "Rugosidad aleatoria", "Случайная шероховатость"),
    ("Sigma", "Sigma", "Sigma", "Сигма"),
    ("Fresnel", "Fresnel", "Fresnel", "Френель"),
    ("Linear", "Linear", "Lineal", "Линейный"),
    ("Color Intensity", "Intensidade da cor", "Intensidad del color", "Интенсивность цвета"),
    ("Spec Intensity", "Intensidade especular", "Intensidad especular", "Интенсивность блика"),
    ("Spec Translucency", "Translucidez especular", "Translucidez especular", "Полупрозрачность блика"),
    ("Columns Offset", "Deslocamento das colunas", "Desplazamiento de columnas", "Смещение столбцов"),
    ("Rows Offset", "Deslocamento das linhas", "Desplazamiento de filas", "Смещение строк"),
    ("Color Attribute", "Atributo de cor", "Atributo de color", "Атрибут цвета"),
    ("Density Attribute", "Atributo de densidade", "Atributo de densidad", "Атрибут плотности"),
    ("Absorption Color", "Cor de absorção", "Color de absorción", "Цвет поглощения"),
    ("Emission Strength", "Intensidade da emissão", "Intensidad de emisión", "Сила излучения"),
    ("Blackbody Intensity", "Intensidade de corpo negro", "Intensidad de cuerpo negro", "Интенсивность черного тела"),
    ("Blackbody Tint", "Tonalidade de corpo negro", "Tinte de cuerpo negro", "Оттенок черного тела"),
    ("Temperature Attribute", "Atributo de temperatura", "Atributo de temperatura", "Атрибут температуры"),
    ("Nabla", "Nabla", "Nabla", "Набла"),

    # Outliner
    ("Register a library's data-block in this file without instantiating it in any scene",
     "Registra o bloco de dados de uma biblioteca neste arquivo sem instanciá-lo em nenhuma cena",
     "Registra el bloque de datos de una biblioteca en este archivo sin instanciarlo en ninguna escena",
     "Зарегистрировать блок данных библиотеки в этом файле, не создавая его экземпляр ни в одной сцене"),
    ("Import this Text into the current file", "Importa este texto para o arquivo atual",
     "Importa este texto al archivo actual", "Импортировать этот текст в текущий файл"),
    ("Add a new scene", "Adiciona uma nova cena", "Añade una nueva escena", "Добавить новую сцену"),
    ("External Files", "Arquivos externos", "Archivos externos", "Внешние файлы"),
    ("Pose", "Pose", "Pose", "Поза"),

    # Fisica
    ("Bronze", "Bronze", "Bronce", "Бронза"),

    # Janela: fechar sem salvar e titulos das janelas da Range
    ("This file has not been saved yet. Save before closing?", "Este arquivo ainda não foi salvo. Salvar antes de fechar?",
     "Este archivo aún no se ha guardado. ¿Guardar antes de cerrar?", "Этот файл ещё не сохранён. Сохранить перед закрытием?"),
    ('Save changes to "%s" before closing?', 'Salvar as alterações em "%s" antes de fechar?',
     '¿Guardar los cambios en "%s" antes de cerrar?', 'Сохранить изменения в "%s" перед закрытием?'),
    ("Do not quit", "Não sair", "No salir", "Не выходить"),
    ("Discard Changes", "Descartar alterações", "Descartar cambios", "Отменить изменения"),
    ("Discard changes and quit", "Descarta as alterações e sai", "Descarta los cambios y sale",
     "Отменить изменения и выйти"),
    ("Save & Quit", "Salvar e sair", "Guardar y salir", "Сохранить и выйти"),
    ("Save and quit", "Salva e sai", "Guarda y sale", "Сохранить и выйти"),
    ("Range Settings", "Configurações da Range", "Configuración de Range", "Настройки Range"),
    ("Range File View", "Arquivos da Range", "Archivos de Range", "Файлы Range"),
)

PT_BR = {en: pt for en, pt, _es, _ru in TABLE}
ES = {en: es for en, _pt, es, _ru in TABLE}
RU = {en: ru for en, _pt, _es, ru in TABLE}
