"""Background regression/audit for Scene Doctor primitive collision suggestions.
Run AnastacioEngine -b --factory-startup --disable-autoexec --python-exit-code 1
    --python this.py -- worktree output_directory [--audit project.range ...]
"""
import hashlib
import importlib.util
import json
import os
import sys

import bpy

args = sys.argv[sys.argv.index('--') + 1:]
root, output = map(os.path.abspath, args[:2])
os.makedirs(output, exist_ok=True)
spec = importlib.util.spec_from_file_location('doctor_collision_validation', os.path.join(
    root, 'source/release/scripts/startup/bl_operators/anastacio_scene_doctor.py'))
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)
assert doctor.rule_collision_primitive in doctor.RULES


def snapshot():
    return [(ob.name, ob.game.physics_type, ob.game.use_collision_bounds,
             ob.game.collision_bounds_type, ob.game.radius, tuple(ob.scale))
            for ob in bpy.data.objects]


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            result.update(chunk)
    return result.hexdigest()


if '--audit' in args:
    reports = []
    for path in args[args.index('--audit') + 1:]:
        before_hash = digest(path)
        bpy.ops.wm.open_mainfile(filepath=path)
        before = snapshot()
        scenes = []
        for scene in bpy.data.scenes:
            issues = doctor.rule_collision_primitive(scene, list(scene.objects))
            assert before == snapshot(), 'Diagnosis changed scene settings'
            scenes.append({'scene': scene.name, 'objects': len(scene.objects), 'suggestions': [
                {'name': i.key, 'severity': i.severity, 'title': i.title} for i in issues]})
        assert digest(path) == before_hash, 'Source file changed'
        reports.append({'path': path, 'sha256': before_hash, 'unchanged': True, 'scenes': scenes})
    with open(os.path.join(output, 'rolima-audit.json'), 'w') as stream:
        json.dump(reports, stream, indent=2)
    print('COLLISION_PRIMITIVE_AUDIT_OK', len(reports))
else:
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    def setup(ob, name, physics='STATIC', bounds='TRIANGLE_MESH'):
        ob.name = name
        ob.game.physics_type = physics
        ob.game.use_collision_bounds = True
        ob.game.collision_bounds_type = bounds
        return ob

    def cube(name, physics='STATIC', bounds='TRIANGLE_MESH'):
        bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 0))
        return setup(scene.objects.active, name, physics, bounds)

    box = cube('box')
    moving = cube('moving', 'DYNAMIC', 'CONVEX_HULL')
    rigid = cube('rigid', 'RIGID_BODY')
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=24, size=1, location=(0, 0, 0))
    sphere = setup(scene.objects.active, 'sphere')
    sphere.game.radius = 1
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1, depth=4, location=(0, 0, 0))
    cylinder = setup(scene.objects.active, 'cylinder')
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=24, size=1, location=(0, 0, 0))
    capsule = setup(scene.objects.active, 'capsule')
    for v in capsule.data.vertices:
        v.co.z += 1 if v.co.z >= 0 else -1
    capsule.data.update()
    # Concave L occupies 75% of its box and cannot fit the round alternatives.
    polygon = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
    vertices = [(x, y, z) for z in (-1, 1) for x, y in polygon]
    faces = [tuple(reversed(range(6))), tuple(range(6, 12))]
    faces += [(i, (i + 1) % 6, (i + 1) % 6 + 6, i + 6) for i in range(6)]
    mesh = bpy.data.meshes.new('L')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    l_shape = bpy.data.objects.new('L', mesh)
    scene.objects.link(l_shape)
    setup(l_shape, 'L')
    vehicle = cube('vehicle')
    vehicle.game.is_vehicle = True
    child = cube('vehicle_child')
    child.parent = vehicle
    wheel = cube('vehicle_wheel')
    scene.objects.active = vehicle
    bpy.ops.object.vehicle_wheel_add()
    ref = vehicle.vehicle_wheels[-1]
    ref.object = wheel
    destructible = cube('destructible')
    destructible.game.use_destruction = True
    character = cube('character', 'CHARACTER', 'CONVEX_HULL')
    soft = cube('soft', 'SOFT_BODY')
    disabled = cube('disabled')
    disabled.game.use_collision_bounds = False
    open_mesh = cube('open')
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(open_mesh.data)
    bmesh.ops.delete(bm, geom=[next(iter(bm.faces))], context=5)
    bm.to_mesh(open_mesh.data)
    bm.free()
    scaled = cube('scaled')
    scaled.scale = (2, .5, 3)
    scaled.rotation_euler = (.2, .7, .4)
    mirrored = cube('mirrored')
    mirrored.scale = (-2, 1, 1)
    flat = cube('flat')
    flat.scale.z = 0
    compound = cube('compound')
    compound.game.use_collision_compound = True
    compound_child = cube('compound_child')
    compound_child.parent = compound
    proxy = cube('proxy')
    proxy.game.collision_bound = box
    separate = cube('disconnected')
    bm = bmesh.new()
    bm.from_mesh(separate.data)
    extra = bmesh.ops.create_cube(bm, size=2)['verts']
    for v in extra:
        v.co.x += 3
    bm.to_mesh(separate.data)
    bm.free()
    modified = cube('modified')
    modified.modifiers.new('Bevel', 'BEVEL')
    wrong_radius = sphere.copy()
    wrong_radius.data = sphere.data.copy()
    scene.objects.link(wrong_radius)
    wrong_radius.name = 'wrong_radius'
    wrong_radius.game.radius = .1
    shifted_sphere = sphere.copy()
    shifted_sphere.data = sphere.data.copy()
    scene.objects.link(shifted_sphere)
    shifted_sphere.name = 'shifted_sphere'
    for v in shifted_sphere.data.vertices:
        v.co.x += 3
    shifted_sphere.data.update()
    # Capsule can be shifted by Bullet, unlike Sphere.
    shifted_box = cube('shifted_box')
    for v in shifted_box.data.vertices:
        v.co.x += 3
    scene.update()
    # Wrapper detection also covers projects that have not enabled the native marker.
    from types import SimpleNamespace
    wrapper = SimpleNamespace(type='MESH', data=box.data, library=None, mode='OBJECT',
                              modifiers=[], parent=None)
    wrapper.game = SimpleNamespace(physics_type='STATIC', use_collision_bounds=True,
        collision_bounds_type='TRIANGLE_MESH', use_collision_compound=False,
        components=[SimpleNamespace(module='scripts.VehicleSystem.NativeVehicleComponent',
                                    name='NativeVehicle')], controllers=[])
    assert doctor._collision_primitive_excluded(wrapper)
    before = snapshot()
    issues = doctor.rule_collision_primitive(scene, list(scene.objects))
    assert snapshot() == before
    actual = {i.key: doctor._collision_primitive_fit(i.objects[0])[0] for i in issues}
    expected = {'box': 'BOX', 'moving': 'BOX', 'rigid': 'BOX', 'sphere': 'SPHERE',
                'cylinder': 'CYLINDER', 'capsule': 'CAPSULE', 'scaled': 'BOX',
                'mirrored': 'BOX', 'shifted_box': 'BOX'}
    assert actual == expected, (actual, expected)
    diagnosed = doctor.diagnose(scene)
    assert not [i for i in diagnosed if i.key == 'error'], [(i.rule, i.title) for i in diagnosed]
    assert {i.key for i in diagnosed if i.rule == 'collision_primitive'} == set(expected)
    for issue in issues:
        ob = issue.objects[0]
        previous = snapshot()
        revert = issue.fix()
        assert ob.game.collision_bounds_type == expected[ob.name]
        assert issue.severity == ('LOW' if ob.game.physics_type == 'STATIC' else 'MEDIUM')
        revert()
        assert snapshot() == previous, ob.name
    # The older moving-trimesh fix may run first; revert must restore actual pre-fix type.
    box.game.collision_bounds_type = 'CONVEX_HULL'
    issue = next(i for i in issues if i.key == 'box')
    revert = issue.fix()
    revert()
    assert box.game.collision_bounds_type == 'CONVEX_HULL'
    box.game.collision_bounds_type = 'TRIANGLE_MESH'
    box.game.use_destruction = True
    try:
        issue.fix()
    except ValueError:
        pass
    else:
        raise AssertionError('Stale destructive-object fix was accepted')
    box.game.use_destruction = False
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(output, 'collision-primitives.range'))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(output, 'collision-primitives.range'))
    reopened = doctor.rule_collision_primitive(bpy.context.scene, list(bpy.context.scene.objects))
    assert {i.key for i in reopened} == set(expected)
    with open(os.path.join(output, 'synthetic-results.json'), 'w') as stream:
        json.dump({'ok': True, 'suggestions': actual, 'objects': len(bpy.data.objects),
                   'fix_revert': True, 'reopened': True}, stream, indent=2)
    print('COLLISION_PRIMITIVE_TESTS_OK', len(expected))
