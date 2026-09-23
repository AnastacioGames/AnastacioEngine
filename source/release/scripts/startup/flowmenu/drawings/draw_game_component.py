import bpy

# Dicionário de fallback caso não esteja definido no escopo global
# Adicione seus ícones aqui se necessário
DEFAULT_ICON_DICT = {1: 'OBJECT_DATAMODE', 2: 'MODIFIER', 3: 'PARTICLES'}


def draw_game_component(self, context, layout):
    # Pega o dicionário global se existir, senão usa o padrão
    icons_map = globals().get('icondict', DEFAULT_ICON_DICT)

    # Layout Principal
    main_box = layout.box()

    ob = context.active_object
    if not ob or not ob.game:
        return

    game = ob.game
    wm = context.window_manager
    component_active = wm.collection_components_active

    # Proteção de Índice
    if component_active >= len(game.components):
        main_box.label(text="Select a component", icon="INFO")
        return

    component = game.components[component_active]

    # --- TOPO: Título e Botões de Ação ---
    header_row = main_box.row()
    header_row.alignment = "CENTER"
    header_row.label(text=component.name, icon="TEXT")

    row_actions = main_box.row(align=True)
    row_actions.scale_y = 1.2  # Botões um pouco maiores
    row_actions.operator("wm.flowmenu_python_component_reload_new",
                         text="Reload", icon="FILE_REFRESH")

    op_remove = row_actions.operator("logic.python_component_remove",
                                     text="", icon="X")  # Texto vazio para economizar espaço, só icone
    op_remove.index = component_active

    # --- CORPO: Propriedades ---
    content_box = main_box.column()

    if len(component.properties) == 0:
        msg = content_box.box()
        msg.label(text="No arguments found", icon="INFO")
        return

    # Variáveis de controle de desenho
    current_box = content_box.box()  # Começa numa caixa padrão
    icon_counter = 1
    use_custom_icons = False

    # Verifica se o modo de ícones está ativo
    # (Varrendo antes para configurar o estado)
    for prop in component.properties:
        if prop.name == "C_Icons":
            use_custom_icons = True
            break

    for prop in component.properties:
        # Pula a propriedade de controle interna "C_Icons"
        if prop.name == "C_Icons":
            continue

        # --- Lógica de CABEÇALHO (C_Header) ---
        if prop.name.startswith("C_Header"):
            # Cria uma nova caixa visual para separar seções
            current_box = content_box.box()

            # Define ícone do header
            header_icon = "DOWNARROW_HLT"
            split_name = prop.name.split("/")
            if len(split_name) > 1:
                header_icon = split_name[1]

            # Desenha o título da seção
            row_header = current_box.row()
            row_header.label(text=prop.value, icon=header_icon)

            # Adiciona uma linha separadora sutil
            current_box.separator()
            continue

        # --- Desenho das Propriedades Normais ---
        row = current_box.row(align=True)

        # Decide qual ícone usar para a propriedade
        prop_icon = "DOT"
        if use_custom_icons:
            # Tenta pegar do dicionário, se falhar usa DOT
            prop_icon = icons_map.get(icon_counter, "DOT")
            icon_counter += 1

        # Nome da Propriedade (Esquerda)
        row.label(text=prop.name, icon=prop_icon)

        # Valor da Propriedade (Direita)
        # O split faz o campo de valor não ficar grudado no texto
        # row.prop(prop, "value", text="") -> Versão simples
        # Versão mais robusta com caixa para o valor:
        val_col = row.column()
        val_col.alignment = "RIGHT"
        val_col.prop(prop, "value", text="")