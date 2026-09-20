# Catálogo pt_BR do perfil Web. As chaves são os textos em inglês do código; o inglês é o idioma-fonte.
# Registrado em bl_ui.register(); só tem efeito com o editor compilado com WITH_INTERNATIONAL.

_PT_BR = {
    # Propriedades
    "Version of the Web profile settings": "Versão das configurações do perfil Web",
    "Check Web compatibility": "Verificar compatibilidade Web",
    "Shows Web compatibility warnings while editing. Web export always validates, regardless of this option":
        "Mostra avisos de compatibilidade Web durante a edição. "
        "A exportação Web sempre valida, independentemente desta opção",
    "Web runtime used in the package; availability is checked on export":
        "Runtime Web usado no pacote; a disponibilidade é verificada na exportação",
    "Entry scene": "Cena de entrada",
    "Initial scene of the Web package; empty uses the current scene":
        "Cena inicial do pacote Web; vazio usa a cena atual",
    "Preflight after export": "Pré-voo após exportar",
    "After exporting, opens the package in a windowless Chrome/Edge (about 15 s) "
    "and adds the problems seen in the browser to the report":
        "Depois de exportar, abre o pacote num Chrome/Edge sem janela (cerca de 15 s) "
        "e junta ao relatório os problemas vistos no navegador",
    "Open after export": "Abrir após exportar",
    "After exporting, starts a local server and opens the game in the default browser":
        "Depois de exportar, sobe um servidor local e abre o jogo no navegador padrão",
    "Destination": "Destino",
    "Output directory of the Web package": "Diretório de saída do pacote Web",

    # Operadores (nomes e dicas)
    "Validate Web": "Validar Web",
    "Analyzes the file's scenes, controllers, scripts and assets against the Web profile":
        "Analisa cenas, controllers, scripts e assets do arquivo contra o perfil Web",
    "Export Web": "Exportar Web",
    "Validates again and generates the Web package; errors block it and the previous export is preserved":
        "Valida de novo e gera o pacote Web; erros bloqueiam e o export anterior é preservado",
    "Test package in browser": "Testar pacote no navegador",
    "Opens the exported package in a windowless Chrome/Edge and adds what the browser saw to the report (about 15 s)":
        "Abre o pacote exportado num Chrome/Edge sem janela e junta ao relatório o que o navegador viu (cerca de 15 s)",
    "Open in browser": "Abrir no navegador",
    "Starts a local server with the exported package and opens the game in the default browser":
        "Sobe um servidor local com o pacote exportado e abre o jogo no navegador padrão",
    "Stop server": "Parar servidor",
    "Stops the local server of the Web package": "Para o servidor local do pacote Web",
    "Import Web preflight": "Importar pré-voo Web",
    "Reads the preflight report (JSON) of the package in the browser and adds the results to the report":
        "Lê o relatório de pré-voo (JSON) do pacote no navegador e junta os resultados ao relatório",
    "Locate": "Localizar",
    "Selects the origin of the result (scene and object)": "Seleciona a origem do resultado (cena e objeto)",

    # Textos do painel
    "Desktop preview (P key) is not a Web test.": "Prévia desktop (tecla P) não é Teste Web.",
    "Serving at %s": "Servindo em %s",
    "No check has been run.": "Nenhuma verificação executada.",
    "Result of the last validation; revalidate after editing.":
        "Resultado da última validação; revalide após editar.",
    "... and %d more result(s).": "... e mais %d resultado(s).",
    "Chrome or Edge not found for the automatic test.": "Chrome ou Edge não encontrado para o teste automático.",

    # Mensagens (relatórios e status)
    "Serving at %s (click Play on the page).": "Servindo em %s (clique em Jogar na página).",
    "Could not start the local server: %s": "Não foi possível iniciar o servidor local: %s",
    "Preflight not run: %s": "Pré-voo não executado: %s",
    "Preflight: %d problem(s).": "Pré-voo: %d problema(s).",
    "Preflight found no problems.": "Pré-voo sem problemas.",
    "Save the file before exporting: the package uses the saved .range.":
        "Salve o arquivo antes de exportar: o pacote usa o .range salvo.",
    "Export from a development tree with tools/web/package-web.py.":
        "Exporte a partir de uma árvore de desenvolvimento com tools/web/package-web.py.",
    "Web runtime unavailable; see WEB-PKG-001 in the report.":
        "Runtime Web indisponível; veja WEB-PKG-001 no relatório.",
    "%s Fix and validate again.": "%s Corrija e valide novamente.",
    "Export failed; the previous one was preserved: %s": "Export falhou; o anterior foi preservado: %s",
    "Web package generated at %s": "Pacote Web gerado em %s",
    "Local server stopped.": "Servidor local parado.",
    "Stale result; validate again.": "Resultado desatualizado; valide novamente.",
    "Origin outside the scenes (spawn pool object).": "Origem fora das cenas (objeto do pool de spawn).",
    "Package not found at %s. Click Export Web first.": "Pacote não encontrado em %s. Clique em Exportar Web primeiro.",
    "The package is older than the saved .range. Click Export Web first.":
        "O pacote está desatualizado em relação ao .range salvo. Clique em Exportar Web primeiro.",
    "Could not open the browser: %s": "Não foi possível abrir o navegador: %s",
    "The browser did not send the report within %d s.": "O navegador não enviou o relatório em %d s.",
    "Unreadable preflight report.": "Relatório de pré-voo ilegível.",
    "the packager produced no files": "o empacotador não gerou arquivos",
    "%d error(s), %d warning(s)": "%d erro(s), %d aviso(s)",
    "No incompatibility detected (%d warning(s))": "Nenhuma incompatibilidade detectada (%d aviso(s))",
    "No incompatibility detected": "Nenhuma incompatibilidade detectada",
}

# Nomes de operadores Python usam o contexto "Operator"; o resto usa o padrão "*".
_CONTEXTS = ("*", "Operator")

from .translations_es_ru import ES as _ES, RU as _RU

translations_dict = {
    lang: {(ctx, msgid): msgstr for msgid, msgstr in table.items() for ctx in _CONTEXTS}
    for lang, table in (("pt_BR", _PT_BR), ("es", _ES), ("ru_RU", _RU))
}
# pt_PT partilha o mesmo texto (o catálogo do Blender também oferece os dois).
translations_dict["pt_PT"] = translations_dict["pt_BR"]

_DOMAIN = "range_web"


def register():
    import bpy
    try:
        bpy.app.translations.register(_DOMAIN, translations_dict)
    except ValueError:
        # Já registrado (recarga dos scripts): refaz para pegar edições.
        bpy.app.translations.unregister(_DOMAIN)
        bpy.app.translations.register(_DOMAIN, translations_dict)


def unregister():
    import bpy
    bpy.app.translations.unregister(_DOMAIN)
