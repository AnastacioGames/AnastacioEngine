# Two-scene file for the "scene-change" scenario: "Arena1" holds the replicated "Ball", "Arena2" the replicated
# "Box" and the inactive replicated prototype "Shot" (layer 20).
# Usage: RangeEngine -b --python make_scene_change.py -- <out.range>
import bpy
import sys

OUT = sys.argv[sys.argv.index("--") + 1]

bpy.ops.wm.read_factory_settings(use_empty=True)
first = bpy.context.scene
first.name = "Arena1"
second = bpy.data.scenes.new("Arena2")
world = bpy.data.worlds.new("World")

mesh = bpy.data.meshes.new("Cube")
mesh.from_pydata([(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
                  (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)], [],
                 [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
mesh.update()


def add(scene, name, location, hidden=False):
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.game.physics_type = 'NO_COLLISION'
    scene.objects.link(obj)
    # link() gives the base the scene's layers, and Object.layers only updates the base in the context scene
    # (Arena1): set the base of this scene directly, or Shot stays visible (active) in Arena2.
    layers = [i == (19 if hidden else 0) for i in range(20)]
    obj.layers = layers
    scene.object_bases[obj.name].layers = layers
    obj.game.network.use_replicate = True
    return obj


for scene in (first, second):
    scene.render.engine = 'BLENDER_GAME'
    scene.world = world
    scene.layers = [i == 0 for i in range(20)]
    cam = bpy.data.objects.new("Cam" + scene.name, bpy.data.cameras.new("Cam" + scene.name))
    cam.location = (0, -20, 10)
    cam.rotation_euler = (1.1, 0, 0)
    scene.objects.link(cam)
    cam.layers = [i == 0 for i in range(20)]
    scene.camera = cam

add(first, "Ball", (4, 0, 1))
add(second, "Box", (0, 4, 2))
add(second, "Shot", (0, 0, 0), hidden=True)
ids = [o.game.network.net_id for o in bpy.data.objects if o.type == 'MESH']
print("NETCHANGE ids", ids)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("NETCHANGE SAVED" if all(ids) and len(set(ids)) == len(ids) else "NETCHANGE BAD IDS", OUT)
