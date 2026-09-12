"""
RND-001 - gera um arquivo .bvox sintetico (header VoxelDataHeader: resolX,
resolY, resolZ, frames + dados float) e forca o motor a le-lo de verdade via
render interno (BLENDER_RENDER), exercitando load_frame_blendervoxel().
Cobre tanto o caminho normal (arquivo bem formado) quanto os dois casos de
corrupcao que RND-001 corrigiu: resolucao com overflow de int e leitura
truncada (arquivo menor que o esperado pelo header).

Rodar em background, sem GUI:
    RangeEngine.exe --background --python tools/tests/bugfix_regression/test_rnd001_voxeldata_bvox.py
"""
import bpy
import os
import struct
import tempfile

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s %s" % (status, label, detail))
    if not condition:
        FAILURES.append(label)


def write_bvox(path, resol, frames, fill_fraction=1.0):
    """Escreve um .bvox valido; fill_fraction < 1.0 escreve menos floats do
    que o header promete, simulando um arquivo truncado/corrompido."""
    resx, resy, resz = resol
    total = resx * resy * resz * frames
    to_write = int(total * fill_fraction)
    with open(path, "wb") as f:
        f.write(struct.pack("<4i", resx, resy, resz, frames))
        f.write(struct.pack("<%df" % to_write, *[i / 64.0 for i in range(to_write)]))


def setup_voxel_scene(bvox_path):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_RENDER'
    scene.render.resolution_x = 16
    scene.render.resolution_y = 16
    scene.render.resolution_percentage = 100

    tex = bpy.data.textures.new("RND001VoxelTex", type='VOXEL_DATA')
    tex.voxel_data.file_format = 'BLENDER_VOXEL'
    tex.voxel_data.filepath = bvox_path

    mat = bpy.data.materials.new("RND001Mat")
    mtex = mat.texture_slots.add()
    mtex.texture = tex

    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.data.materials.append(mat)

    if scene.camera is None:
        bpy.ops.object.camera_add(location=(0, -3, 0), rotation=(1.5708, 0, 0))
        scene.camera = bpy.context.active_object

    if not any(o.type == 'LAMP' for o in scene.objects):
        bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 5))

    return tex, mat, obj


def cleanup(tex, mat, obj):
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.materials.remove(mat)
    bpy.data.textures.remove(tex)


def test_well_formed_bvox():
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, "rnd001_test_ok.bvox")
    write_bvox(path, (4, 4, 4), 1, fill_fraction=1.0)

    tex, mat, obj = setup_voxel_scene(path)
    ok = True
    try:
        bpy.ops.render.render(write_still=False)
    except Exception as exc:
        ok = False
        print("  excecao:", exc)

    res = tuple(tex.voxel_data.resolution)
    check(
        "RND-001 well-formed .bvox renders and header round-trips",
        ok and res == (4, 4, 4),
        "(resolution=%s)" % (res,),
    )

    cleanup(tex, mat, obj)
    os.remove(path)


def test_truncated_bvox_does_not_crash():
    # header promete 8x8x8 floats, mas o arquivo so tem metade -> antes da
    # correcao o fread parcial deixava o dataset com lixo; agora
    # load_frame_blendervoxel detecta e libera o dataset (vd->ok fica 0).
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, "rnd001_test_truncated.bvox")
    write_bvox(path, (8, 8, 8), 1, fill_fraction=0.5)

    tex, mat, obj = setup_voxel_scene(path)
    ok = True
    try:
        bpy.ops.render.render(write_still=False)
    except Exception as exc:
        ok = False
        print("  excecao:", exc)

    check("RND-001 truncated .bvox does not crash the render", ok)

    cleanup(tex, mat, obj)
    os.remove(path)


def main():
    test_well_formed_bvox()
    test_truncated_bvox_does_not_crash()
    print("\n%d falha(s)" % len(FAILURES) if FAILURES else "\nTodos os testes passaram.")


main()
