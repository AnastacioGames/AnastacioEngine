"""Inspecao somente leitura dos assets para o splash 0.6.0."""
import bpy
import json
import sys

dest = sys.argv[sys.argv.index('--') + 1]
report = {'scenes': [], 'groups': [], 'actions': list(bpy.data.actions.keys())}
for scene in bpy.data.scenes:
    report['scenes'].append({'name': scene.name, 'camera': scene.camera.name if scene.camera else None,
        'objects': [{'name': o.name, 'type': o.type, 'location': list(o.location),
                     'group': o.dupli_group.name if o.dupli_group else None}
                    for o in scene.objects if o.type in ('CAMERA', 'LAMP') or any(
                        w in o.name.lower() for w in ('start', 'spawn', 'largada', 'grid', 'seat', 'rolima', 'piloto'))]})
for group in bpy.data.groups:
    report['groups'].append({'name': group.name, 'offset': list(group.dupli_offset), 'objects': [
        {'name': o.name, 'type': o.type, 'location': list(o.location),
         'parent': o.parent.name if o.parent else None,
         'props': [p.name for p in o.game.properties]}
        for o in group.objects]})
with open(dest, 'w', encoding='utf8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print('SPLASH_INSPECTION_OK', dest)
