import bpy


def draw_game_properties(self, context, layout):
    ob = context.active_object
    if not ob: return

    game = ob.game
    is_font = (ob.type == 'FONT')

    # =======================================================
    # ÁREA ESPECIAL: TEXTO (Se for objeto de Fonte)
    # =======================================================
    if is_font:
        box_font = layout.box()
        box_font.label(text="Text Game Settings", icon="FONT_DATA")

        prop_index = game.properties.find("Text")
        prop_indexR = game.properties.find("Text-Res")

        # Configuração da Propriedade "Text"
        row = box_font.row(align=True)
        if prop_index != -1:
            prop = game.properties[prop_index]
            row.prop(prop, "name", text="", icon="OUTLINER_OB_FONT", emboss=False)  # Mostra nome fixo
            row.label(text="(Linked to Body)")

            # Botão de remover a propriedade especial
            op_rem = row.operator("object.game_property_remove", text="", icon='X')
            op_rem.index = prop_index
        else:
            op_add = row.operator("object.game_property_new", text="Add 'Text' Property", icon="ADD")
            op_add.name = "Text"
            op_add.type = 'STRING'

        # Configuração da Resolução "Text-Res"
        if prop_index != -1:  # Só mostra resolução se tiver Texto
            row = box_font.row(align=True)
            if prop_indexR != -1:
                propR = game.properties[prop_indexR]
                row.label(text="Resolution:", icon="RNDCURVE")
                row.prop(propR, "value", text="")

                op_rem = row.operator("object.game_property_remove", text="", icon='X')
                op_rem.index = prop_indexR
            else:
                op_add = row.operator("object.game_property_new", text="Add Resolution", icon="ADD")
                op_add.name = "Text-Res"
                op_add.type = 'FLOAT'

    # =======================================================
    # ÁREA COMUM: PROPRIEDADES DO JOGO
    # =======================================================

    # Cabeçalho da Lista
    row_header = layout.row()
    row_header.label(text="Game Properties", icon="GAME")

    op_add_gen = row_header.operator("object.game_property_new", text="New", icon="ADD")
    op_add_gen.name = "Prop"

    # Lista de Propriedades
    col_props = layout.column(align=True)

    for i, prop in enumerate(game.properties):
        # Pula as propriedades de Texto que já desenhamos acima
        if is_font and prop.name in ["Text", "Text-Res"]:
            continue

        box = col_props.box()
        row = box.row(align=True)

        # Ícone do tipo (Tenta mapear tipos para ícones se possível, ou usa genérico)
        icon_type = 'BRUSH_DATA'  # Padrão
        if prop.type == 'BOOL':
            icon_type = 'CHECKBOX_HLT'
        elif prop.type == 'STRING':
            icon_type = 'STRING'
        elif prop.type == 'FLOAT':
            icon_type = 'w'  # Decimal icon hack ou similar

        # Coluna 1: Nome e Tipo
        # Split layout: 40% Nome, 60% Valor/Controles
        split = row.split(percentage=0.4, align=True)

        row_left = split.row(align=True)
        row_left.prop(prop, "name", text="")

        # Coluna 2: Valor e Debug
        row_right = split.row(align=True)
        row_right.prop(prop, "value", text="")
        row_right.prop(prop, "type", text="", icon_only=True)  # Tipo pequenininho

        # Botão Debug (Info)
        icon_debug = 'INFO' if prop.show_debug else 'UGLYPACKAGE'  # Ícone muda se ativo
        row_right.prop(prop, "show_debug", text="", toggle=True, icon=icon_debug)

        # Coluna 3: Ações (Mover e Deletar)
        # Usamos um sub-row para agrupar
        row_actions = row_right.row(align=True)

        op_up = row_actions.operator("object.game_property_move", text="", icon='TRIA_UP')
        op_up.index = i
        op_up.direction = 'UP'

        op_down = row_actions.operator("object.game_property_move", text="", icon='TRIA_DOWN')
        op_down.index = i
        op_down.direction = 'DOWN'

        op_del = row_actions.operator("object.game_property_remove", text="", icon='X')
        op_del.index = i