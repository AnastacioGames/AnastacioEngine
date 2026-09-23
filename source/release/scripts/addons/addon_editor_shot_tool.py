"""
ADDON DE EDIÇÃO (roda no Blender/Range, NÃO é um componente de jogo).

Instalação: Preferences > Add-ons > Install... > selecione este arquivo >
marque a caixinha para ativar. Depois disso ele carrega sozinho toda vez
que o Blender/Range abrir, sem precisar rodar nada manualmente.

Ele registra um painel "Cutscene" na barra lateral da Viewport 3D (tecla N)
e uma seção "Empty to Cutscene" em Properties > Object Data, com botões
para criar e configurar os Empties de tomada de câmera lidos pelo
CutsceneCameraManager (scripts/cutscenes/cutscene_camera.py).

Por que isso existe:
Cada Empty de tomada aceita até 13 propriedades de jogo (order, target,
duration, transition, fov, transition_speed, pan_target, follow, shake,
noise, slowmo_scale, filter_on, filter_off) que o
CutsceneCameraManager.parse_shot_data() lê
como override do plano. Adicionar isso manualmente ("+ Add Game Property"
uma por uma) é o trabalho chato que esse painel elimina.

Os valores default abaixo espelham os defaults do componente
CutsceneCameraManager (ShotDuration, Transition, FOV, TransitionSpeed,
EnableNoiseSway, SlowMotionScale). Se você mudar os defaults do
componente na cena, ajuste aqui também para manter os dois em sincronia.
"""

bl_info = {
    "name": "Cutscene Shot Tool",
    "author": "Anastacio Games",
    "version": (1, 0, 1),
    "blender": (2, 79, 0),
    "location": "View3D > Sidebar (N) > Cutscene  |  Properties > Object Data > Empty to Cutscene",
    "description": "Cria e edita os Empties de tomada de câmera lidos pelo CutsceneCameraManager",
    "category": "Object",
}

import bpy

# Nome, tipo (Blender Game Property), valor default.
# 'order' é tratado à parte (auto-incrementado), por isso não está aqui.
SHOT_PROPERTY_SCHEMA = [
    ("target", 'STRING', ""),           # nome do objeto para olhar; "" = detecta jogador mais próximo
    ("duration", 'FLOAT', 3.5),         # duração do plano em segundos
    ("transition", 'STRING', "SMOOTH"), # "SMOOTH" ou "CUT"
    ("fov", 'FLOAT', 45.0),
    ("transition_speed", 'FLOAT', 0.7), # velocidade de interpolação deste plano; "" numérico = usa TransitionSpeed do manager
    ("pan_target", 'STRING', ""),       # alvo secundário: câmera interpola a posição até ele durante o plano
    ("follow", 'STRING', ""),           # chase-cam: câmera acompanha este objeto continuamente, mantendo o enquadramento inicial
    ("shake", 'FLOAT', 0.0),            # tremor deste plano (multiplicado por GlobalShakeIntensity do manager)
    ("noise", 'BOOL', True),            # balanço orgânico (noise sway) ligado/desligado neste plano
    ("slowmo_scale", 'FLOAT', 1.0),     # escala de tempo do plano (1.0 = normal, <1.0 = câmera lenta)
    ("filter_on", 'STRING', ""),
    ("filter_off", 'STRING', ""),
]

ORDER_PROP_ALIASES = ("index", "order", "step", "ordem", "shot_index")


def get_shot_order(obj):
    """Lê a propriedade de ordem do Empty (mesma prioridade de alias do cutscene_camera.py)."""
    if not hasattr(obj, "game"):
        return None
    props = {p.name.strip().lower(): p for p in obj.game.properties}
    for alias in ORDER_PROP_ALIASES:
        if alias in props:
            try:
                return float(props[alias].value)
            except (TypeError, ValueError):
                return None
    return None


SHOT_OBJECT_TYPES = ('EMPTY', 'CAMERA')


def is_shot_empty(obj):
    return obj.type in SHOT_OBJECT_TYPES and get_shot_order(obj) is not None


def next_free_order(scene):
    orders = [get_shot_order(o) for o in scene.objects]
    orders = [o for o in orders if o is not None]
    return int(max(orders)) + 1 if orders else 1


def add_or_get_prop(obj, name, prop_type):
    """Retorna a game property já existente ou cria via operador (API do Blender exige objeto ativo)."""
    for p in obj.game.properties:
        if p.name == name:
            return p
    bpy.context.scene.objects.active = obj
    bpy.ops.object.game_property_new(type=prop_type, name=name)
    return obj.game.properties[name]


def apply_schema(obj, schema, overwrite=False):
    added = []
    for name, prop_type, default in schema:
        existed = any(p.name == name for p in obj.game.properties)
        prop = add_or_get_prop(obj, name, prop_type)
        if not existed or overwrite:
            prop.value = default
            added.append(name)
    return added


class CUTSCENE_OT_add_shot_empty(bpy.types.Operator):
    bl_idname = "cutscene.add_shot_empty"
    bl_label = "Criar Nova Tomada"
    bl_description = "Cria um Empty no cursor 3D com todas as propriedades de tomada já configuradas"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        order = next_free_order(scene)

        bpy.ops.object.add(type='EMPTY', location=scene.cursor_location)
        empty = context.object
        empty.name = f"CamShot_{order:02d}"
        empty.empty_draw_type = 'CONE'
        empty.empty_draw_size = 0.6

        add_or_get_prop(empty, "order", 'INT').value = order
        apply_schema(empty, SHOT_PROPERTY_SCHEMA, overwrite=True)

        self.report({'INFO'}, f"'{empty.name}' criado com order={order} e {len(SHOT_PROPERTY_SCHEMA) + 1} propriedades.")
        return {'FINISHED'}


class CUTSCENE_OT_sync_shot_properties(bpy.types.Operator):
    bl_idname = "cutscene.sync_shot_properties"
    bl_label = "Sincronizar Propriedades"
    bl_description = "Adiciona nos Empties/Câmeras selecionados as propriedades de tomada que estiverem faltando (não sobrescreve valores existentes)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        targets = [o for o in context.selected_objects if o.type in SHOT_OBJECT_TYPES]
        if not targets:
            self.report({'WARNING'}, "Selecione ao menos um Empty ou Câmera.")
            return {'CANCELLED'}

        touched = 0
        for obj in targets:
            if get_shot_order(obj) is None:
                add_or_get_prop(obj, "order", 'INT').value = next_free_order(context.scene)
            added = apply_schema(obj, SHOT_PROPERTY_SCHEMA, overwrite=False)
            if added:
                touched += 1

        self.report({'INFO'}, f"{touched}/{len(targets)} Empties atualizados.")
        return {'FINISHED'}


class CUTSCENE_OT_delete_shot(bpy.types.Operator):
    bl_idname = "cutscene.delete_shot"
    bl_label = "Remover Tomada"
    bl_description = "Apaga o Empty/Câmera desta tomada da cena"
    bl_options = {'REGISTER', 'UNDO'}

    obj_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.scene.objects.get(self.obj_name)
        if not obj:
            self.report({'WARNING'}, f"Objeto '{self.obj_name}' não encontrado.")
            return {'CANCELLED'}

        name = obj.name
        bpy.ops.object.select_all(action='DESELECT')
        obj.select = True
        context.scene.objects.active = obj
        bpy.ops.object.delete()

        self.report({'INFO'}, f"'{name}' removido.")
        return {'FINISHED'}


class CUTSCENE_OT_strip_shot_properties(bpy.types.Operator):
    bl_idname = "cutscene.strip_shot_properties"
    bl_label = "Remover Propriedades de Tomada"
    bl_description = "Remove as propriedades de tomada deste objeto (ele deixa de ser uma Tomada de Cutscene, mas não é apagado)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if not obj:
            return {'CANCELLED'}

        names_to_remove = set(ORDER_PROP_ALIASES) | {n for n, _, _ in SHOT_PROPERTY_SCHEMA}
        for p in list(obj.game.properties):
            if p.name.strip().lower() in names_to_remove or p.name in names_to_remove:
                bpy.context.scene.objects.active = obj
                idx = list(obj.game.properties).index(p)
                obj.game.properties.active_index = idx if hasattr(obj.game.properties, "active_index") else 0
                bpy.ops.object.game_property_remove(index=list(obj.game.properties).index(p))

        self.report({'INFO'}, f"Propriedades de tomada removidas de '{obj.name}'.")
        return {'FINISHED'}


class CUTSCENE_OT_renumber_shots(bpy.types.Operator):
    bl_idname = "cutscene.renumber_shots"
    bl_label = "Renumerar Ordem"
    bl_description = "Renumera sequencialmente (1, 2, 3...) todas as tomadas da cena, respeitando a ordem atual"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        shots = [o for o in context.scene.objects if is_shot_empty(o)]
        shots.sort(key=lambda o: (get_shot_order(o), o.name))

        for idx, obj in enumerate(shots, start=1):
            for p in obj.game.properties:
                if p.name.strip().lower() in ORDER_PROP_ALIASES:
                    p.value = idx
                    break

        self.report({'INFO'}, f"{len(shots)} tomadas renumeradas.")
        return {'FINISHED'}


class CUTSCENE_PT_shot_tool(bpy.types.Panel):
    bl_label = "Cutscene - Tomadas de Câmera"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Cutscene"

    def draw(self, context):
        layout = self.layout
        shots = [o for o in context.scene.objects if is_shot_empty(o)]

        layout.label(text=f"{len(shots)} tomada(s) detectada(s) na cena")
        layout.operator("cutscene.add_shot_empty", icon='EMPTY_DATA')
        layout.operator("cutscene.sync_shot_properties", icon='FILE_REFRESH')
        layout.operator("cutscene.renumber_shots", icon='LINENUMBERS_ON')

        if shots:
            box = layout.box()
            for obj in sorted(shots, key=lambda o: (get_shot_order(o), o.name)):
                row = box.row()
                row.label(text=f"{int(get_shot_order(obj))}: {obj.name}")
                op = row.operator("cutscene.delete_shot", text="", icon='X')
                op.obj_name = obj.name


FIELD_LABELS = {
    "target": "Alvo (Look At)",
    "duration": "Duração (s)",
    "transition": "Transição",
    "fov": "FOV",
    "transition_speed": "Velocidade da Transição",
    "pan_target": "Alvo do Pan",
    "follow": "Seguir (Chase-Cam)",
    "shake": "Tremor (Shake)",
    "noise": "Balanço Orgânico (Noise)",
    "slowmo_scale": "Escala Slow-Motion",
    "filter_on": "Ativar Filtro",
    "filter_off": "Desativar Filtro",
}

FIELD_GROUPS = (
    ("Enquadramento", ("duration", "transition", "fov", "transition_speed")),
    ("Foco de Câmera", ("target", "pan_target", "follow")),
    ("Efeitos", ("shake", "noise", "slowmo_scale")),
    ("Filtros de Pós-Processamento", ("filter_on", "filter_off")),
)


def draw_labeled_prop(layout, prop, label):
    try:
        split = layout.split(factor=0.45)
    except TypeError:
        split = layout.split(percentage=0.45)
    split.label(text=label)
    split.prop(prop, "value", text="")


class CUTSCENE_PT_empty_shot_data(bpy.types.Panel):
    """Painel próprio (com seta de recolher) em Properties > Object Data, ao lado de 'Empty'/'Camera'."""
    bl_label = "Empty/Câmera to Cutscene"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in SHOT_OBJECT_TYPES

    def draw(self, context):
        ob = context.object
        layout = self.layout

        order = get_shot_order(ob)
        if order is None:
            layout.label(text="Este objeto ainda não é uma Tomada de Cutscene.", icon='INFO')
            layout.operator("cutscene.sync_shot_properties", text="Transformar em Tomada de Câmera", icon='CAMERA_DATA')
            return

        props_by_name = {p.name: p for p in ob.game.properties}

        row = layout.row()
        row.label(text="Ordem da Tomada", icon='CAMERA_DATA')
        for alias in ORDER_PROP_ALIASES:
            if alias in props_by_name:
                row.prop(props_by_name[alias], "value", text="")
                break

        for group_title, field_names in FIELD_GROUPS:
            group_fields = [(n, props_by_name[n]) for n in field_names if n in props_by_name]
            if not group_fields:
                continue
            box = layout.box()
            box.label(text=group_title)
            col = box.column(align=True)
            for name, prop in group_fields:
                draw_labeled_prop(col, prop, FIELD_LABELS.get(name, name))

        layout.separator()
        layout.operator("cutscene.sync_shot_properties", text="Adicionar Propriedades Faltantes", icon='FILE_REFRESH')
        layout.operator("cutscene.strip_shot_properties", text="Remover Propriedades de Tomada", icon='X')


CLASSES = (
    CUTSCENE_OT_add_shot_empty,
    CUTSCENE_OT_sync_shot_properties,
    CUTSCENE_OT_delete_shot,
    CUTSCENE_OT_strip_shot_properties,
    CUTSCENE_OT_renumber_shots,
    CUTSCENE_PT_shot_tool,
    CUTSCENE_PT_empty_shot_data,
)


def register():
    for cls in CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in CLASSES:
        bpy.utils.unregister_class(cls)


# Como addon instalado (Preferences > Add-ons), Blender chama register()/unregister()
# sozinho ao (des)ativar a caixinha. O bloco abaixo só roda se você ainda executar
# este arquivo direto pelo "Run Script" no editor de textos (útil durante o desenvolvimento).
if __name__ == "__main__":
    register()
    print("[CutsceneShotTool] Painel 'Cutscene' (barra lateral N) e secao de Tomada (Properties > Data > Empty) registrados.")
