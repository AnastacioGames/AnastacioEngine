# -*- coding: utf-8 -*-
"""Controle por IA: deixa uma IA (MCP "anastacio-criador") ver e editar o editor que você já abriu.

Desligado por padrão. Você liga aqui, e começa em "só observar": a IA lê a cena e a tela, mas só altera
depois que você clicar em "Liberar edição". Código Python livre continua só por ANASTACIO_CRIADOR_PY=1.
"""
import bpy
from bpy.app.handlers import persistent

bl_info = {
    'name': 'Controle por IA', 'author': 'Anastacio Games',
    'version': (0, 1, 0), 'blender': (2, 79, 0),
    'location': 'Barra superior e Preferências > Add-ons',
    'description': 'Deixa uma IA (MCP anastacio-criador) conectar neste editor, começando só em modo observar',
    'category': 'Game Engine',
}

from . import nucleo_editor as nucleo, sessao  # noqa: E402


def _quadro_novo():
    for janela in bpy.context.window_manager.windows:
        for area in janela.screen.areas:
            area.tag_redraw()


class ANASTACIO_OT_ia_ligar(bpy.types.Operator):
    bl_idname = 'wm.anastacio_ia_ligar'
    bl_label = 'Controle por IA'
    bl_description = 'Liga ou desliga o controle por IA neste editor'

    def execute(self, context):
        if nucleo.CONFIG['ligado']:
            nucleo.desligar()
            self.report({'INFO'}, 'Controle por IA desligado')
        else:
            try:
                nucleo.ligar(sessao.sessao_usuario(), observar=True, dono='usuario')
                nucleo.iniciar_modal()
            except Exception as erro:
                nucleo.desligar()
                self.report({'ERROR'}, str(erro))
                return {'CANCELLED'}
            self.report({'INFO'}, 'Controle por IA ligado (só observar). Porta %s' % nucleo.porta())
        _quadro_novo()
        return {'FINISHED'}


class ANASTACIO_OT_ia_liberar(bpy.types.Operator):
    bl_idname = 'wm.anastacio_ia_liberar'
    bl_label = 'Liberar edição'
    bl_description = 'Alterna entre só observar e deixar a IA editar a cena'

    def execute(self, context):
        nucleo.CONFIG['observar'] = not nucleo.CONFIG['observar']
        if not nucleo.CONFIG['observar']:
            nucleo.responder_pedido(True)
        _quadro_novo()
        return {'FINISHED'}


class ANASTACIO_OT_ia_responder(bpy.types.Operator):
    bl_idname = 'wm.anastacio_ia_responder'
    bl_label = 'Responder pedido da IA'
    bl_description = 'Permite ou nega o pedido da IA para editar'
    permitir = bpy.props.BoolProperty(default=False)

    def execute(self, context):
        nucleo.responder_pedido(self.permitir)
        _quadro_novo()
        return {'FINISHED'}


def _estado():
    if not nucleo.CONFIG['ligado']:
        return 'Desligado'
    modo = 'só observar' if nucleo.CONFIG['observar'] else 'pode editar'
    return 'Ligado (%s), porta %s, %s' % (modo, nucleo.porta(),
                                          'IA conectada' if nucleo.conectado() else 'esperando a IA')


class ANASTACIO_AP_controle_ia(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        col = self.layout.column()
        box = col.box()
        box.label(_estado(), icon='RADIOBUT_ON' if nucleo.CONFIG['ligado'] else 'RADIOBUT_OFF')
        row = box.row()
        row.operator('wm.anastacio_ia_ligar', text='Desligar' if nucleo.CONFIG['ligado'] else 'Ligar')
        if nucleo.CONFIG['ligado']:
            row.operator('wm.anastacio_ia_liberar',
                         text='Voltar a só observar' if not nucleo.CONFIG['observar'] else 'Liberar edição')
        col.label('Arquivo de sessão: %s' % sessao.sessao_usuario())
        col.label('Código Python livre da IA: só com ANASTACIO_CRIADOR_PY=1 no ambiente (não há botão).')


def _cabecalho(self, context):
    if not nucleo.CONFIG['ligado']:  # fica no cabeçalho, desligado, até o addon ser desativado
        row = self.layout.row(align=True)
        row.label('IA: desligada', icon='RADIOBUT_OFF')
        row.operator('wm.anastacio_ia_ligar', text='Ligar')
        return
    pedido = nucleo.pedido_atual()
    if pedido:
        caixa = self.layout.row(align=True)
        caixa.alert = True
        caixa.label((pedido.get('cliente') or 'A IA') + ' pede para editar: ' + pedido['motivo'], icon='ERROR')
        caixa.operator('wm.anastacio_ia_responder', text='Permitir').permitir = True
        caixa.operator('wm.anastacio_ia_responder', text='Negar').permitir = False
        _quadro_novo()
    row = self.layout.row(align=True)
    row.alert = not nucleo.CONFIG['observar']
    quem = nucleo.clientes_conectados()
    row.label('IA' + (' (' + ', '.join(quem) + ')' if quem else '') + ': ' + ('observando' if nucleo.CONFIG['observar'] else 'pode editar'), icon='RADIOBUT_ON')
    row.operator('wm.anastacio_ia_liberar', text='Liberar' if nucleo.CONFIG['observar'] else 'Travar')
    row.operator('wm.anastacio_ia_ligar', text='Desligar')


@persistent
def _religar(_arquivo):
    """Carregar outro arquivo fecha as janelas e o laço modal: recomeça, o mesmo token continua valendo."""
    if nucleo.CONFIG['ligado'] and _retomar not in bpy.app.handlers.scene_update_post:
        _quadros[0] = 0
        bpy.app.handlers.scene_update_post.append(_retomar)


_quadros = [0]


def _retomar(_cena):
    _quadros[0] += 1
    if _quadros[0] < 3:
        return
    bpy.app.handlers.scene_update_post.remove(_retomar)
    if nucleo.CONFIG['ligado']:
        nucleo.iniciar_modal()


def register():
    nucleo.registrar()
    bpy.utils.register_class(ANASTACIO_OT_ia_ligar)
    bpy.utils.register_class(ANASTACIO_OT_ia_liberar)
    bpy.utils.register_class(ANASTACIO_OT_ia_responder)
    bpy.utils.register_class(ANASTACIO_AP_controle_ia)
    bpy.types.INFO_HT_header.append(_cabecalho)
    bpy.app.handlers.load_post.append(_religar)


def unregister():
    if _retomar in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(_retomar)
    if _religar in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_religar)
    bpy.types.INFO_HT_header.remove(_cabecalho)
    bpy.utils.unregister_class(ANASTACIO_AP_controle_ia)
    bpy.utils.unregister_class(ANASTACIO_OT_ia_responder)
    bpy.utils.unregister_class(ANASTACIO_OT_ia_liberar)
    bpy.utils.unregister_class(ANASTACIO_OT_ia_ligar)
    nucleo.desregistrar()
