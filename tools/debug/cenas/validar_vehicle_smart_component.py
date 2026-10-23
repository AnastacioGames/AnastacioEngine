"""Editor -b --factory-startup --python este.py -- pasta [componente_antigo.py].

Verifica migração de argumentos e gera veículo nativo com prova no player.
Não abre nem salva sobre arquivos do jogo. Resultados ficam na pasta informada.
"""
import ast
import json
import os
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector
import range_component_editor as editor


out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[3]
source = (root / 'source/release/demos/Vehicle/scripts/vehicle_player_component.py').read_text(encoding='utf-8')
args = sys.argv[sys.argv.index('--') + 2:]
legacy = Path(args[0]).read_text(encoding='utf-8') if args else source
checks = []


def check(condition, name):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def values(comp):
    return {prop.name: prop.value for prop in comp.properties}


def runtime_methods(code):
    cls = next(node for node in ast.parse(code).body
               if isinstance(node, ast.ClassDef) and node.name == 'VehiclePlayerComponent')
    return {node.name: ast.dump(node) for node in cls.body if isinstance(node, ast.FunctionDef)}


if args:
    check(runtime_methods(source) == runtime_methods(legacy), 'metodos de runtime preservados')
flow = (root / 'source/release/scripts/startup/flowmenu/custom_pt_physics.py').read_text(encoding='utf-8')
template = next(node for node in ast.parse(flow).body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'VEHICLE_COMPONENT_TEMPLATE'
                        for target in node.targets))
check(ast.literal_eval(template.value) == source, 'template do botao e demo identicos')
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 360
scene.game_settings.use_frame_rate = True
scene.game_settings.fps = 60
world = bpy.data.worlds.new('VehicleTestWorld')
world.mist_settings.use_mist = False
scene.world = world


def cube(name, location, scale, color, physics):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.game.physics_type = physics
    mat = bpy.data.materials.new(name + 'Material')
    mat.diffuse_color = color
    obj.data.materials.append(mat)
    return obj


cube('Ground', (0, 0, -0.2), (40, 40, 0.2), (0.12, 0.2, 0.3), 'STATIC')
chassis = cube('SmartChassis', (0, 0, 1.0), (0.7, 1.3, 0.2), (0.9, 0.25, 0.05), 'RIGID_BODY')
chassis.game.mass = 800
chassis.game.use_collision_bounds = True
chassis.game.collision_bounds_type = 'BOX'
chassis.game.is_vehicle = True
for index, (x, y) in enumerate(((-0.8, 0.9), (0.8, 0.9), (-0.8, -0.9), (0.8, -0.9))):
    wheel = bpy.data.objects.new('Wheel%d' % index, None)
    scene.objects.link(wheel)
    wheel.game.physics_type = 'NO_COLLISION'
    wheel.location = (x, y, 0.8)
    scene.update()
    world_matrix = wheel.matrix_world.copy()
    wheel.parent = chassis
    wheel.matrix_world = world_matrix
    bpy.ops.object.vehicle_wheel_add()
    config = chassis.vehicle_wheels[-1]
    config.object = wheel
    config.radius = 0.3
    config.suspension_rest_length = 0.3
    config.suspension_stiffness = 30
    config.suspension_damping = 2.3
    config.suspension_compression = 4.4
    config.friction = 2.0
    config.roll_influence = 0.1
    config.has_steering = y > 0
    config.has_drive = y < 0

text = bpy.data.texts.new('vehicle_player_component.py')
text.from_string(legacy)
comp = chassis.game.components.new('vehicle_player_component.VehiclePlayerComponent')
original = values(comp)
comp.properties['Engine Force'].value = 2345.0
comp.properties['Steering Sign'].value = -1.0
comp.properties['Throttle Key'].value = 'UPARROWKEY'
changed = values(comp)

# O mesmo texto/módulo é atualizado como num projeto existente.
text.clear()
text.from_string(source)
scene.objects.active = chassis
result = bpy.ops.logic.python_component_reload(index=0)
check(result == {'FINISHED'}, 'reload de componente legado')
comp = chassis.game.components[0]
check(values(comp) == changed, 'valores e chaves preservados no reload')
# O cache de importação do editor checa mudanças no texto a cada segundo.
time.sleep(1.1)
meta = editor.meta_of(comp)
check(len(meta) == 42, '42 campos tipados encontrados pelo editor')
check(meta['Joystick Deadzone']['max'] == 0.99, 'limites de zona morta')
check(meta['Engine Force']['tip'], 'dicas de campo disponiveis')
check(not editor.is_visible(comp, 'Max Lean (deg)'), 'opcoes de moto ocultas no carro')
comp.properties['Motorcycle'].value = True
check(editor.is_visible(comp, 'Max Lean (deg)'), 'opcoes de moto visiveis quando ativadas')
comp.properties['Motorcycle'].value = False
check(not editor.is_visible(comp, 'Engine Volume'), 'audio oculto sem arquivo')
comp.properties['Use Joystick'].value = False
check(not editor.is_visible(comp, 'Joystick Index'), 'joystick oculto quando desligado')

entry = editor.editor_of(comp)()
entry.args = values(comp)
check(not list(entry.warnings(chassis, comp)), 'configuracao valida sem avisos')
snapshot = values(comp)
chassis.game.is_vehicle = False
check(any('Ative Vehicle' in message for message in entry.warnings(chassis, comp)), 'aviso de veiculo desativado')
chassis.game.is_vehicle = True
chassis.vehicle_wheels[0].object = None
check(any('escolha' in message for message in entry.warnings(chassis, comp)), 'aviso de roda sem objeto')
chassis.vehicle_wheels[0].object = bpy.data.objects['Wheel0']
chassis.vehicle_wheels[0].radius = 0
check(any('raio' in message for message in entry.warnings(chassis, comp)), 'aviso de raio zero')
chassis.vehicle_wheels[0].radius = 0.3
second = chassis.game.components.new('vehicle_player_component.VehiclePlayerComponent')
check(any('Outro controlador' in message for message in entry.warnings(chassis, comp)), 'aviso de controlador duplicado')
chassis.game.components.remove(second)
check(values(comp) == snapshot, 'diagnosticos nao alteram argumentos')
entry.args['Downshift RPM'] = 6000
check(entry.on_change(chassis, 'Downshift RPM', 6000), 'aviso de limites de troca invertidos')
entry.args = values(comp)


class GeometryProbe:
    def __init__(self):
        self.lines = []
        self.circles = []
        self.center = None

    def line(self, start, end, color):
        self.lines.append((start.copy(), end.copy()))

    def circle(self, center, radius, color, axis):
        self.circles.append((center.copy(), radius))

    def sphere(self, center, radius, color):
        self.center = center.copy()

    def text(self, position, label):
        pass


scene.update()
probe = GeometryProbe()
entry.draw_gizmo(chassis, values(comp), probe, True)
check(len(probe.lines) == 4 and len(probe.circles) == 4, 'guias de quatro rodas')
check(all(abs((a - b).length - 0.3) < 1e-5 for a, b in probe.lines), 'guias com comprimento de suspensao correto')
check((probe.center - chassis.matrix_world.translation).length < 1e-5, 'guia do centro de massa')
chassis.rotation_euler = (0.2, -0.1, 0.7)
chassis.vehicle_com_offset = (0.1, -0.2, -0.3)
scene.update()
rotated = GeometryProbe()
entry.draw_gizmo(chassis, values(comp), rotated, True)
expected = chassis.matrix_world.translation + chassis.matrix_world.to_quaternion() * Vector(chassis.vehicle_com_offset)
check((rotated.center - expected).length < 1e-5, 'COM deslocado em chassi rotacionado')
check(all(abs((a - b).length - 0.3) < 1e-5 for a, b in rotated.lines), 'suspensao em chassi rotacionado')
chassis.rotation_euler = (0, 0, 0)
chassis.vehicle_com_offset = (0, 0, 0)

# Restabelece os padrões de condução; valores especiais já foram testados no reload.
for name, value in original.items():
    comp.properties[name].value = value
comp.properties['Use Joystick'].value = False
saved_values = values(comp)

lamp = bpy.data.objects.new('Sun', bpy.data.lamps.new('Sun', 'SUN'))
lamp.rotation_euler = (0.6, -0.4, 0.4)
scene.objects.link(lamp)
cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
cam.location = (8, -12, 8)
cam.data.lens = 16
cam.rotation_euler = (Vector((0, 3, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# O controlador não lê teclado: comanda etapas determinísticas e verifica dados no jogo.
driver = bpy.data.objects.new('VehicleProbe', None)
scene.objects.link(driver)
scene.objects.active = driver
bpy.ops.logic.sensor_add(type='ALWAYS', object=driver.name)
sensor = driver.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=driver.name)
controller = driver.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'anastacio_vehicle_probe.tick'
controller.link(sensor=sensor)
runtime = bpy.data.texts.new('anastacio_vehicle_probe.py')
runtime.from_string('''import json, os, traceback
import Range
state = {'frame': 0, 'checks': []}

def tick(cont):
    state['frame'] += 1
    frame = state['frame']
    try:
        obj = cont.owner.scene.objects['SmartChassis']
        vehicle = obj.getVehicle()
        component = obj.components['VehiclePlayerComponent']
        if frame == 60:
            assert vehicle is not None and vehicle.getNumWheels() == 4
            assert all(vehicle.getWheelState(i)['isInContact'] for i in range(4))
            assert type(component._args['Engine Force']) is float
            assert type(component._args['Use Joystick']) is bool
            assert 'bpy' not in __import__('vehicle_player_component').__dict__
            state['checks'].append('vehicle contact, plain args and no bpy')
            state['origin'] = list(obj.worldPosition)
            component._read_input = lambda: (1.0, 0.0, 0.0, 0.0)
            # O motor por torque também consulta os pedais separados para freio/ré.
            component._gas_input = lambda: 1.0
            component._back_input = lambda: 0.0
        if frame == 180:
            assert abs(vehicle.getCurrentSpeedKmh()) > 3
            assert (obj.worldPosition - __import__('mathutils').Vector(state['origin'])).length > 1
            state['checks'].append('accelerates with native vehicle')
            state['speed'] = abs(vehicle.getCurrentSpeedKmh())
            component._read_input = lambda: (0.0, 0.0, 120.0, 0.0)
            component._gas_input = lambda: 0.0
        if frame == 120:
            component.update_args({'Throttle Key': 'UPARROWKEY'})
            assert component._throttle_key == Range.events.UPARROWKEY
            state['checks'].append('live args preserved')
        if frame == 240:
            assert abs(vehicle.getCurrentSpeedKmh()) < state['speed']
            assert 'vehicle_speed_kmh' in obj
            state['checks'].append('brakes and publishes telemetry')
            state['ok'] = True
            finish()
    except Exception:
        state['error'] = traceback.format_exc()
        state['ok'] = False
        finish()

def finish():
    with open(os.environ['ANASTACIO_VEHICLE_TEST_RESULT'], 'w') as handle:
        json.dump(state, handle, indent=2)
    Range.logic.endGame()
''')
destination = str(out / 'vehicle-smart.range')
bpy.ops.wm.save_as_mainfile(filepath=destination)
bpy.ops.wm.open_mainfile(filepath=destination)
reopened = bpy.data.objects['SmartChassis'].game.components[0]
check(values(reopened) == saved_values, 'valores preservados ao salvar e reabrir')
check(len(editor.meta_of(reopened)) == 42, 'metadados recuperados ao reabrir')
chassis = bpy.data.objects['SmartChassis']
chassis.vehicle_max_torque = 175.0
chassis.vehicle_max_rpm = 6000.0
bpy.context.scene.objects.active = chassis
for ratio in (-3.2, 3.4, 2.2):
    bpy.ops.object.vehicle_gear_add()
    chassis.vehicle_gears[-1].ratio = ratio
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'vehicle-smart-torque.range'), copy=True)
# Variante sem comandos automatizados para o detector existente de trabalho repetido.
bpy.context.scene.objects.unlink(bpy.data.objects['VehicleProbe'])
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'vehicle-smart-stationary.range'), copy=True)
with open(str(out / 'editor-result.json'), 'w', encoding='utf-8') as handle:
    json.dump({'ok': True, 'checks': checks, 'scene': destination}, handle, indent=2)
print('VEHICLE_SMART_EDITOR_PASS', len(checks))
