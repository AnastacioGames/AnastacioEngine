# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

"""Microfone no editor (plano-microfone-ui.md §2).

- sound.record_microphone: grava um WAV e cria o Sound; conforme o alvo, coloca no
  Sequencer, no atuador Sound, no nó Sound da Logic Tree ou troca o arquivo de um Sound.
- sound.adjust ("Ajustar Som"): corte, fades, normalizar e efeito de voz -> WAV novo.
- sound.preview_fx: toca a prévia (para a anterior).
- sequencer.bake_sound_strip: corte/volume/pitch do strip -> WAV novo num strip acima.

Tudo sem DNA novo: valores ficam nas propriedades dos operadores.
"""

import os
import tempfile
import time

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

try:
    import aud
except ImportError:  # build sem áudio
    aud = None

RATE = 44100
_preview = {"handle": None}


def _has_mic():
    return aud is not None and hasattr(aud, "Microphone")


_device_cache = []  # o Blender guarda ponteiros para os textos de um enum dinâmico


def _device_names():
    try:
        return list(aud.Microphone.devices()) if _has_mic() else []
    except Exception:
        return []


def _device_label(name):
    return name.replace("OpenAL Soft on ", "") if name else "Padrão do sistema"


def _device_items(self, context):
    items = [("DEFAULT", "Padrão do sistema", "Microfone padrão do Windows")]
    for i, name in enumerate(_device_names()):
        items.append(("D%d" % i, _device_label(name), name))
    _device_cache[:] = items
    return _device_cache


def _device_file():
    return os.path.join(bpy.utils.user_resource('CONFIG', create=True), "anastacio_microphone.txt")


def saved_device():
    """Nome do microfone escolhido; "" = padrão, None = nunca escolheu."""
    try:
        with open(_device_file(), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def save_device(name):
    with open(_device_file(), "w", encoding="utf-8") as f:
        f.write(name)


def _preset_items(self, context):
    names = ["NONE"]
    if aud is not None and hasattr(aud, "voice_presets"):
        try:
            names = aud.voice_presets()
        except Exception:
            pass
    return [(n, n.title(), "") for n in names]


def _sounds_dir():
    """Pasta dos WAV gravados: //sounds ao lado do .range, ou temporária (o Sound é empacotado)."""
    if bpy.data.filepath:
        path = os.path.join(os.path.dirname(bpy.data.filepath), "sounds")
        os.makedirs(path, exist_ok=True)
        return path, True
    return tempfile.gettempdir(), False


def _free_name(folder, base):
    for i in range(1, 10000):
        name = "%s_%03d.wav" % (base, i)
        if not os.path.exists(os.path.join(folder, name)):
            return name
    return "%s_%d.wav" % (base, int(time.time()))


def _rel(path):
    """Caminho //relativo com barras normais (o .range também abre no Linux e na Web)."""
    return bpy.path.relpath(path).replace(chr(92), "/")


def _load_sound(path, saved):
    """Cria o datablock Sound; arquivo não salvo: empacota para não depender do temporário."""
    filepath = _rel(path) if saved else path
    snd = bpy.data.sounds.load(filepath, check_existing=False)
    if not saved:
        snd.pack()
    return snd


def _repoint(snd, path, saved):
    """Troca o arquivo de um Sound. Definir filepath recarrega o som."""
    if snd.packed_file:
        # 'REMOVE' nao solta o pacote do Sound; USE_ORIGINAL solta e nao apaga nada.
        snd.unpack(method='USE_ORIGINAL')
    snd.filepath = _rel(path) if saved else path
    if not saved:
        snd.pack()


def _aud_of(sound):
    """aud.Sound de um datablock Sound (arquivo ou empacotado)."""
    if sound.packed_file:
        ext = os.path.splitext(sound.filepath)[1] or ".wav"
        fd, tmp = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(sound.packed_file.data)
        return aud.Sound.file(tmp)
    path = bpy.path.abspath(sound.filepath, library=sound.library)
    if not os.path.exists(path):
        raise RuntimeError("Arquivo do som não encontrado: %s" % path)
    return aud.Sound.file(path)


def _fmt(seconds):
    seconds = int(seconds)
    return "%02d:%02d" % (seconds // 60, seconds % 60)


def _bar(level, width=20):
    n = max(0, min(width, int(round(min(level * 3.0, 1.0) * width))))
    return "|" * n + "." * (width - n)


def stop_preview():
    h = _preview["handle"]
    _preview["handle"] = None
    if h is not None:
        try:
            h.stop()
        except Exception:
            pass


def play_preview(snd):
    stop_preview()
    _preview["handle"] = aud.device().play(snd)


TARGETS = (
    ('NEW', "New Sound", "Só cria o Sound"),
    ('SEQUENCER', "Sequencer", "Cria um strip de som no frame atual"),
    ('ACTUATOR', "Actuator", "Coloca no atuador Sound (object + brick)"),
    ('NODE', "Node", "Coloca no nó Sound da Logic Tree (tree + node)"),
    ('REPLACE', "Replace", "Regravar: troca o arquivo do Sound (sound)"),
    ('DIALOG', "Cutscene Dialog", "Áudio de um evento Dialog da cutscene"),
)


def _dialog_event(scene, op):
    return scene.cutscene_settings.sequences[op.sequence_index].events[op.event_index]


def _assign(context, op, snd):
    """Leva o Sound novo para onde o botão foi clicado."""
    t = op.target
    if t == 'SEQUENCER':
        scene = context.scene
        sed = scene.sequence_editor_create()
        used = {s.channel for s in sed.sequences_all
                if s.frame_final_start <= scene.frame_current < s.frame_final_end}
        channel = next(c for c in range(1, 33) if c not in used) if len(used) < 32 else 32
        strip = sed.sequences.new_sound(snd.name, snd.filepath, channel, scene.frame_current)
        if strip.sound != snd:
            # new_sound cria outro Sound para o arquivo: usar o nosso (pode estar empacotado).
            old = strip.sound
            strip.sound = snd
            if old and old.users == 0:
                bpy.data.sounds.remove(old)
        for s in sed.sequences_all:
            s.select = False
        strip.select = True
        sed.active_strip = strip
    elif t == 'DIALOG':
        # A cutscene toca por caminho; arquivo salvo garantido no invoke.
        _dialog_event(context.scene, op).dialog_audio_path = snd.filepath
    elif t == 'ACTUATOR':
        ob = bpy.data.objects.get(op.object)
        act = ob.game.actuators.get(op.brick) if ob else None
        if act is None or not hasattr(act, "sound"):
            op.report({'WARNING'}, "Atuador não encontrado; o Sound '%s' foi criado" % snd.name)
            return
        act.sound = snd
    elif t == 'NODE':
        tree = bpy.data.node_groups.get(op.tree)
        node = tree.nodes.get(op.node) if tree else None
        if node is None or not hasattr(node, "sound"):
            op.report({'WARNING'}, "Nó não encontrado; o Sound '%s' foi criado" % snd.name)
            return
        node.sound = snd
        if hasattr(node, "update"):
            node.update()


class SOUND_OT_record_microphone(Operator):
    """Grava do microfone (Esc, Enter ou clique: salvar; botão direito: cancelar). Ctrl+clique: escolher o microfone"""
    bl_idname = "sound.record_microphone"
    bl_label = "Record Sound (Microphone)"
    bl_options = {'REGISTER', 'UNDO'}

    target = EnumProperty(name="Target", items=TARGETS, default='NEW')
    object = StringProperty(name="Object", options={'SKIP_SAVE'})
    brick = StringProperty(name="Actuator", options={'SKIP_SAVE'})
    tree = StringProperty(name="Node Tree", options={'SKIP_SAVE'})
    node = StringProperty(name="Node", options={'SKIP_SAVE'})
    sound = StringProperty(name="Sound", description="Sound a regravar (Replace)", options={'SKIP_SAVE'})
    sequence_index = IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})
    event_index = IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})
    countdown = IntProperty(name="Countdown", description="Contagem antes de gravar (s)",
                            default=0, min=0, max=5)
    max_seconds = FloatProperty(name="Max Seconds", default=120.0, min=1.0, max=600.0)

    @classmethod
    def poll(cls, context):
        return _has_mic()

    def _header(self, context, text):
        if self._area is not None:
            self._area.header_text_set(text)
            self._area.tag_redraw()

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)
        if self._area is not None:
            self._area.header_text_set()
            self._area.tag_redraw()

    def invoke(self, context, event):
        if self.target == 'DIALOG' and not bpy.data.filepath:
            self.report({'ERROR'}, "Salve o arquivo antes de gravar a fala da cutscene")
            return {'CANCELLED'}
        device = saved_device()
        names = _device_names()
        if event.ctrl or (device is None and len(names) > 1):
            bpy.ops.sound.select_microphone('INVOKE_DEFAULT')
            return {'CANCELLED'}
        if device and device not in names:
            self.report({'WARNING'}, "Microfone escolhido não encontrado; usando o padrão")
            device = ""
        self._device = device or ""
        device = device or None
        try:
            self._mic = aud.Microphone(device=device, rate=RATE, channels=1, seconds=2.0)
        except Exception as e:
            self.report({'ERROR'}, "Microfone: %s" % e)
            return {'CANCELLED'}
        if not self._mic.start():
            self.report({'ERROR'}, "Microfone: %s" % (self._mic.error or "não abriu"))
            return {'CANCELLED'}
        stop_preview()
        self._area = context.area
        self._begin = time.time() + self.countdown
        self._recording = False
        self._timer = context.window_manager.event_timer_add(0.05, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        mic = self._mic
        if event.type == 'TIMER':
            mic.poll()
            state = mic.state
            if state in {'denied', 'error'}:
                self._finish(context)
                mic.stop()
                msg = "Microfone bloqueado: libere nas configurações" if state == 'denied' else \
                    "Microfone: %s" % (mic.error or "erro")
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
            now = time.time()
            if state != 'granted':
                self._header(context, "Microfone: esperando permissão...  (botão direito: cancelar)")
                self._begin = max(self._begin, now)
                return {'RUNNING_MODAL'}
            if now < self._begin:
                self._header(context, "Gravando em %d...  %s" % (int(self._begin - now) + 1, _bar(mic.level)))
                return {'RUNNING_MODAL'}
            if not self._recording:
                mic.record_start()
                self._recording = True
            elapsed = now - self._begin
            self._header(context, "● REC  %s  %s  %s   Esc/Enter/clique: salvar   Botão direito: cancelar"
                         % (_fmt(elapsed), _bar(mic.level), _device_label(self._device)))
            if elapsed >= self.max_seconds:
                return self._save(context)
            return {'RUNNING_MODAL'}

        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}
        if event.type in {'RIGHTMOUSE'}:
            self._finish(context)
            if self._recording:
                mic.record_stop()
            mic.stop()
            self.report({'INFO'}, "Gravação cancelada")
            return {'CANCELLED'}
        if event.type in {'ESC', 'RET', 'NUMPAD_ENTER', 'LEFTMOUSE', 'SPACE'}:
            if not self._recording:
                self._finish(context)
                mic.stop()
                return {'CANCELLED'}
            return self._save(context)
        return {'RUNNING_MODAL'}

    def _save(self, context):
        mic = self._mic
        mic.poll()
        rec = mic.record_stop()
        mic.stop()
        self._finish(context)
        if aud.duration(rec) < 0.05:
            self.report({'WARNING'}, "Gravação vazia")
            return {'CANCELLED'}
        silent = aud.peak(rec) <= 0.0
        folder, saved = _sounds_dir()
        name = _free_name(folder, "rec")
        path = os.path.join(folder, name)
        try:
            aud.save_wav(rec, path)
        except Exception as e:
            self.report({'ERROR'}, "Não deu para salvar o WAV: %s" % e)
            return {'CANCELLED'}

        if self.target == 'REPLACE' and self.sound in bpy.data.sounds:
            snd = bpy.data.sounds[self.sound]
            _repoint(snd, path, saved)
        else:
            snd = _load_sound(path, saved)
            snd.name = os.path.splitext(name)[0]
            _assign(context, self, snd)
        if silent:
            self.report({'WARNING'}, "Gravou silêncio: Ctrl+clique no botão de gravar para trocar o microfone")
        else:
            self.report({'INFO'}, "Gravado %s (%s)" % (snd.name, _fmt(aud.duration(rec))))
        return {'FINISHED'}


class SOUND_OT_select_microphone(Operator):
    """Escolhe o microfone usado pelos botões de gravar do editor"""
    bl_idname = "sound.select_microphone"
    bl_label = "Select Microphone"

    device = EnumProperty(name="Microfone", items=_device_items)

    @classmethod
    def poll(cls, context):
        return _has_mic()

    def invoke(self, context, event):
        names = _device_names()
        current = saved_device()
        if current in names:
            self.device = "D%d" % names.index(current)
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        self.layout.prop(self, "device")
        self.layout.label(text="Depois clique em gravar. Ctrl+clique troca de novo.", icon='INFO')

    def execute(self, context):
        name = ""
        if self.device != 'DEFAULT':
            name = _device_names()[int(self.device[1:])]
        save_device(name)
        self.report({'INFO'}, "Microfone: %s" % _device_label(name))
        return {'FINISHED'}


class _FxProps:
    sound = StringProperty(name="Sound", options={'SKIP_SAVE'})
    start = FloatProperty(name="Start", description="Início (s)", default=0.0, min=0.0)
    end = FloatProperty(name="End", description="Fim (s); 0 = até o fim", default=0.0, min=0.0)
    fade_in = FloatProperty(name="Fade In", default=0.0, min=0.0, max=30.0)
    fade_out = FloatProperty(name="Fade Out", default=0.0, min=0.0, max=30.0)
    normalize = BoolProperty(name="Normalize", description="Volume pelo pico", default=False)
    effect = EnumProperty(name="Effect", items=_preset_items)
    amount = FloatProperty(name="Amount", default=1.0, min=0.0, max=1.0, subtype='FACTOR')

    def build(self):
        snd = bpy.data.sounds.get(self.sound)
        if snd is None:
            raise RuntimeError("Sound '%s' não existe" % self.sound)
        a = _aud_of(snd)
        end = self.end if self.end > self.start else -1.0
        a = aud.edit(a, self.start, end, self.fade_in, self.fade_out, self.normalize)
        if self.effect and self.effect != 'NONE':
            a = aud.voice_fx(a, self.effect, self.amount)
        return snd, a


class SOUND_OT_preview_fx(_FxProps, Operator):
    """Ouve o som com o corte e o efeito (clique de novo para parar)"""
    bl_idname = "sound.preview_fx"
    bl_label = "Preview"

    stop = BoolProperty(name="Stop", options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return aud is not None and hasattr(aud, "voice_fx")

    def execute(self, context):
        if self.stop:
            stop_preview()
            return {'FINISHED'}
        try:
            _snd, a = self.build()
            play_preview(a)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class SOUND_OT_adjust(_FxProps, Operator):
    """Ajustar Som: corte, fades, normalizar e efeito de voz, gravados num WAV novo"""
    bl_idname = "sound.adjust"
    bl_label = "Adjust Sound"
    bl_options = {'REGISTER', 'UNDO'}

    sequence_index = IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})
    event_index = IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return aud is not None and hasattr(aud, "voice_fx")

    def invoke(self, context, event):
        if self.event_index >= 0:
            if not bpy.data.filepath:
                self.report({'ERROR'}, "Salve o arquivo antes de ajustar a fala")
                return {'CANCELLED'}
            path = _dialog_event(context.scene, self).dialog_audio_path
            abspath = bpy.path.abspath(path)
            if not os.path.exists(abspath):
                self.report({'ERROR'}, "Arquivo do áudio não encontrado: %s" % path)
                return {'CANCELLED'}
            self.sound = bpy.data.sounds.load(path, check_existing=True).name
        if not self.sound:
            snd = getattr(getattr(context.scene.sequence_editor, "active_strip", None), "sound", None)
            if snd is None:
                self.report({'ERROR'}, "Escolha um Sound")
                return {'CANCELLED'}
            self.sound = snd.name
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        snd = bpy.data.sounds.get(self.sound)
        layout.label(text=self.sound, icon='SOUND')
        if snd is not None and aud is not None:
            try:
                layout.label(text="Duração: %.2f s" % aud.duration(_aud_of(snd)))
            except Exception:
                pass
        row = layout.row(align=True)
        row.prop(self, "start")
        row.prop(self, "end")
        row = layout.row(align=True)
        row.prop(self, "fade_in")
        row.prop(self, "fade_out")
        layout.prop(self, "normalize")
        row = layout.row(align=True)
        row.prop(self, "effect", text="")
        row.prop(self, "amount")
        row = layout.row(align=True)
        op = row.operator("sound.preview_fx", text="Preview", icon='PLAY_AUDIO')
        for k in ("sound", "start", "end", "fade_in", "fade_out", "normalize", "effect", "amount"):
            setattr(op, k, getattr(self, k))
        row.operator("sound.preview_fx", text="", icon='PAUSE').stop = True
        layout.label(text="OK grava um WAV novo e troca o arquivo do Sound", icon='INFO')

    def execute(self, context):
        stop_preview()
        try:
            snd, a = self.build()
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        folder, saved = _sounds_dir()
        base = os.path.splitext(os.path.basename(snd.filepath))[0] or snd.name
        if base.endswith("_edit") is False:
            base += "_edit"
        path = os.path.join(folder, _free_name(folder, base))
        try:
            aud.save_wav(a, path)
        except Exception as e:
            self.report({'ERROR'}, "Não deu para salvar o WAV: %s" % e)
            return {'CANCELLED'}
        # O arquivo antigo fica no disco; só o Sound passa a apontar para o novo.
        _repoint(snd, path, saved)
        if self.event_index >= 0:
            _dialog_event(context.scene, self).dialog_audio_path = snd.filepath
        self.report({'INFO'}, "Som ajustado: %s" % os.path.basename(path))
        return {'FINISHED'}


class SEQUENCER_OT_bake_sound_strip(Operator):
    """Aplica corte, volume e pitch do strip num WAV novo (strip novo no canal de cima, o antigo fica mudo)"""
    bl_idname = "sequencer.bake_sound_strip"
    bl_label = "Apply Edit to Sound"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        sed = context.scene.sequence_editor
        strip = sed.active_strip if sed else None
        return aud is not None and hasattr(aud, "edit") and strip is not None and strip.type == 'SOUND' \
            and strip.sound is not None

    def execute(self, context):
        scene = context.scene
        sed = scene.sequence_editor
        strip = sed.active_strip
        fps = scene.render.fps / scene.render.fps_base
        try:
            a = _aud_of(strip.sound)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        start = (strip.animation_offset_start + strip.frame_offset_start) / fps
        end = start + strip.frame_final_duration / fps
        a = aud.edit(a, start, end)
        if abs(strip.pitch - 1.0) > 1e-4:
            a = a.pitch(strip.pitch)
        if abs(strip.volume - 1.0) > 1e-4:
            a = a.volume(strip.volume)

        folder, saved = _sounds_dir()
        base = os.path.splitext(os.path.basename(strip.sound.filepath))[0] or strip.sound.name
        name = _free_name(folder, base + "_edit")
        path = os.path.join(folder, name)
        try:
            aud.save_wav(a, path)
        except Exception as e:
            self.report({'ERROR'}, "Não deu para salvar o WAV: %s" % e)
            return {'CANCELLED'}
        snd = _load_sound(path, saved)
        snd.name = os.path.splitext(name)[0]
        channel = min(strip.channel + 1, 32)
        new = sed.sequences.new_sound(snd.name, snd.filepath, channel, strip.frame_final_start)
        if new.sound != snd:
            old = new.sound
            new.sound = snd
            if old and old.users == 0:
                bpy.data.sounds.remove(old)
        strip.mute = True
        strip.select = False
        new.select = True
        sed.active_strip = new
        self.report({'INFO'}, "Novo strip %s (o original ficou mudo)" % new.name)
        return {'FINISHED'}



classes = (
    SOUND_OT_select_microphone,
    SOUND_OT_record_microphone,
    SOUND_OT_preview_fx,
    SOUND_OT_adjust,
    SEQUENCER_OT_bake_sound_strip,
)
