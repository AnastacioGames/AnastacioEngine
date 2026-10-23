"""Editor -b jogo.range --python este.py -- relatorio.json; não salva a cena."""
import json
import os
import sys

import bpy


def plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "name"):
        return value.name
    try:
        return [plain(item) for item in value]
    except TypeError:
        return str(value)


def attributes(value, names):
    return {name: plain(getattr(value, name)) for name in names if hasattr(value, name)}


destination = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
assert os.path.normcase(destination) != os.path.normcase(os.path.abspath(bpy.data.filepath))
root = os.path.dirname(bpy.data.filepath)
vehicles = []
for obj in bpy.data.objects:
    components = [comp for comp in obj.game.components
                  if comp.name in {'NativeVehicle', 'NativeRolima', 'VehiclePlayerComponent'}]
    if not components and not obj.game.is_vehicle:
        continue
    groups = [group.name for group in obj.users_group]
    config_name = (groups[0] if groups else obj.name).split('.')[0].strip()
    config = os.path.join(root, 'Vehicle_data', config_name + '_config.json')
    entry = {
        'object': obj.name,
        'scenes': [scene.name for scene in obj.users_scene],
        'groups': groups,
        'location': plain(obj.location),
        'rotation': plain(obj.rotation_euler),
        'scale': plain(obj.scale),
        'game': attributes(obj.game, ('physics_type', 'mass', 'is_vehicle',
                                    'vehicle_com_offset', 'vehicle_max_torque',
                                    'vehicle_max_rpm', 'vehicle_gearbox_type')),
        'native': attributes(obj, ('vehicle_com_offset', 'vehicle_max_torque',
                                   'vehicle_max_rpm', 'vehicle_gearbox_type',
                                   'vehicle_steering_wheel')),
        'components': [{'module': comp.module, 'class': comp.name,
                        'args': {prop.name: plain(prop.value) for prop in comp.properties}}
                       for comp in components],
        'other_components': [comp.name for comp in obj.game.components if comp not in components],
        'native_wheels': [attributes(wheel, ('object', 'radius', 'suspension_rest_length',
                                           'has_steering', 'has_drive'))
                          for wheel in obj.vehicle_wheels],
        'config_candidate': config,
    }
    # O primeiro grupo é apenas candidato: instâncias podem resolver outro grupo no runtime.
    if os.path.isfile(config):
        with open(config, encoding='utf-8') as handle:
            entry['config'] = json.load(handle)
    marked = []
    pending = list(obj.children)
    while pending:
        child = pending.pop()
        pending.extend(child.children)
        properties = {prop.name: plain(prop.value) for prop in child.game.properties}
        if 'Wheel' in properties:
            marked.append({'object': child.name, 'wheel': properties['Wheel'],
                           'position': plain(child.matrix_world.translation),
                           'physics_type': child.game.physics_type})
    entry['script_wheels'] = sorted(marked, key=lambda item: item['object'])
    vehicles.append(entry)

with open(destination, 'w', encoding='utf-8') as handle:
    json.dump({'source': bpy.data.filepath, 'vehicles': vehicles}, handle,
              ensure_ascii=False, indent=2, sort_keys=True)
print('VEHICLE_INSPECTION_OK', len(vehicles), destination)
