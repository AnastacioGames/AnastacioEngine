"""Abre cena V1, troca somente o controlador em cÃ³pia e testa curva arcade.

Editor -b vehicle-smart.range --python este.py -- pasta_saida
"""
import json
import ast
from pathlib import Path
import sys
import bpy
import range_component_editor as editor

out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[3]
name = 'anastacio_vehicle_arcade'
text = bpy.data.texts.get(name + '.py') or bpy.data.texts.new(name + '.py')
text.clear()
text.from_string((root / 'source/release/demos/Vehicle/scripts' / (name + '.py')).read_text(encoding='utf-8'))
panel = ast.parse((root / 'source/release/scripts/startup/flowmenu/custom_pt_physics.py').read_text(encoding='utf-8'))
templates = {node.targets[0].id: ast.literal_eval(node.value) for node in panel.body
             if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
             and node.targets[0].id in ('VEHICLE_ARCADE_TEMPLATE', 'VEHICLE_COMPONENT_TEMPLATE')}
assert templates['VEHICLE_ARCADE_TEMPLATE'] == text.as_string()
basic = root / 'source/release/demos/Vehicle/scripts/vehicle_player_component.py'
assert templates['VEHICLE_COMPONENT_TEMPLATE'] == basic.read_text(encoding='utf-8')
chassis = bpy.data.objects['SmartChassis']
bpy.context.scene.objects.active = chassis
old = chassis.game.components[0]
values = {p.name: p.value for p in old.properties}
chassis.game.components.remove(old)
bpy.ops.logic.python_component_register(component_name=name + '.AnastacioVehicleArcade')
comp = chassis.game.components[0]
for key, value in values.items():
    comp.properties[key].value = value
assert len(editor.meta_of(comp)) == 43
assert comp.properties['Engine Force'].value == values['Engine Force']

probe = bpy.data.texts['anastacio_vehicle_probe.py']
source = probe.as_string().replace("obj.components['VehiclePlayerComponent']", "obj.components['AnastacioVehicleArcade']")
source = source.replace('component._read_input = lambda: (1.0, 0.0, 0.0, 0.0)', 'component.set_commands(throttle=1.0)')
source = source.replace('component._gas_input = lambda: 1.0', 'assert component._gas_input() == 1.0')
source = source.replace('component._back_input = lambda: 0.0', 'assert component._back_input() == 0.0')
source = source.replace('component._read_input = lambda: (0.0, 0.0, 120.0, 0.0)', 'component.set_commands(brake=1.0)')
source = source.replace('component._gas_input = lambda: 0.0', 'assert component._gas_input() == 0.0')
source = source.replace("        if frame == 60:", '''        if frame == 60:
            # Curva idÃªntica Ã  LUT do Rolima: patamar atÃ© 20 e saturaÃ§Ã£o em 120.
            expected = [(0, 1.0), (20, 1.0), (70, 0.65), (120, 0.3), (249, 0.3)]
            for speed, factor in expected:
                assert abs(component._arcade_steer_lut[speed] - factor) < 1e-6
            lut = component._arcade_steer_lut
            component.update_args({'Throttle Key': 'WKEY'})
            assert component._arcade_steer_lut is lut
            component.update_args({'Arcade Steering Reduction': 0.5})
            assert component._arcade_steer_lut is not lut
            assert abs(component._arcade_steer_lut[120] - 0.5) < 1e-6
            component.update_args({'Arcade Steering Reduction': 0.7})
            assert abs(component._compute_steer_value(1.0)) > 0
            component._args['Speed-Sensitive Steering'] = False
            import math
            assert abs(component._compute_steer_value(1.0) - math.radians(26)) < 1e-6
            component._args['Speed-Sensitive Steering'] = True
            component.set_commands(-2, 2, 2, True)
            assert component._back_input() == 1 and component._gas_input() == 0
            assert component._read_input() == (-1.0, 1.0, 120.0, 250.0)
            try:
                component.set_commands(float('nan'))
                raise AssertionError('accepted NaN')
            except ValueError:
                pass
            assert component._commands[0] == -1
            component.clear_commands()
            assert component._commands is None
            state['checks'].append('arcade LUT, live invalidation and steering switch')
''')
probe.clear()
probe.from_string(source)
destination = str(out / 'vehicle-arcade.range')
bpy.ops.wm.save_as_mainfile(filepath=destination)
bpy.ops.wm.open_mainfile(filepath=destination)
assert bpy.data.objects['SmartChassis'].game.components[0].name == 'AnastacioVehicleArcade'
# Variante com motor torque; mesma interface externa de pedais, sem segunda força.
chassis = bpy.data.objects['SmartChassis']
chassis.vehicle_max_torque = 175.0
chassis.vehicle_max_rpm = 6000.0
bpy.context.scene.objects.active = chassis
for ratio in (-3.2, 3.4, 2.2):
    bpy.ops.object.vehicle_gear_add()
    chassis.vehicle_gears[-1].ratio = ratio
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'vehicle-arcade-torque.range'), copy=True)
bpy.context.scene.objects.unlink(bpy.data.objects['VehicleProbe'])
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'vehicle-arcade-stationary.range'), copy=True)
# Exercita o botão real da instalação e impede dois controladores no chassi.
chassis.game.components.remove(chassis.game.components[0])
result = bpy.ops.object.vehicle_add_player_component(controller='ARCADE')
assert result == {'FINISHED'}
assert chassis.game.components[0].name == 'AnastacioVehicleArcade'
assert (out / 'scripts/anastacio_vehicle_arcade.py').read_text(encoding='utf-8') == templates['VEHICLE_ARCADE_TEMPLATE']
assert bpy.ops.object.vehicle_add_player_component() == {'CANCELLED'}
assert len(chassis.game.components) == 1
with open(str(out / 'editor-result.json'), 'w') as handle:
    json.dump({'ok': True, 'fields': 43, 'saved_and_reopened': True}, handle)
print('VEHICLE_ARCADE_EDITOR_PASS')

