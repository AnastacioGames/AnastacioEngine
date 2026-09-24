"""
Testes de regressao (nao de overflow real) para GPU-001 e MOD-001: confirmam
que o caminho normal continua funcionando depois das correcoes de aritmetica.
Nao tentam reproduzir os cenarios extremos (textura >2^31 pixels, malha com
bilhoes de vertices) porque isso exigiria alocacoes de dezenas de GB so para
provocar o overflow original - impraticavel de automatizar com seguranca.

Rodar em background, sem GUI:
    RangeEngine.exe --background --python tools/tests/bugfix_regression/test_regression_smoke.py
"""
import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s %s" % (status, label, detail))
    if not condition:
        FAILURES.append(label)


def test_gpu001_float_texture_upload():
    # imagem float (equivalente a abrir um EXR/HDR) forca o caminho de
    # GPU_texture_convert_pixels() ao ser usada num material e carregada na GPU.
    # img.gl_load() precisa de um contexto OpenGL real: em --background nao
    # existe um, e a chamada trava esperando um contexto que nunca aparece
    # (confirmado empiricamente). So roda quando ha janela de verdade.
    if bpy.app.background:
        print("[SKIP] GPU-001 float image GPU upload/free (precisa rodar sem --background)")
        return

    img = bpy.data.images.new("GPU001TestImg", width=512, height=512, float_buffer=True)
    ok = True
    try:
        img.gl_load()
        img.gl_free()
    except Exception as exc:
        ok = False
        print("  excecao:", exc)
    check("GPU-001 float image GPU upload/free (normal size)", ok)
    bpy.data.images.remove(img)


def test_mod001_meshdeform_bind_normal_case():
    # malha alvo simples + objeto-gaiola (cage) simples: bind normal do
    # Mesh Deform, mesmo caminho de modifier_mdef_compact_influences().
    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(0, 0, 0))
    target = bpy.context.active_object
    target.name = "MOD001Target"

    bpy.ops.mesh.primitive_cube_add(radius=1.0, location=(0, 0, 0))
    cage = bpy.context.active_object
    cage.name = "MOD001Cage"

    mod = target.modifiers.new(name="MeshDeformTest", type='MESH_DEFORM')
    mod.object = cage

    ok = True
    try:
        bpy.ops.object.meshdeform_bind({"object": target, "active_object": target}, modifier=mod.name)
    except Exception as exc:
        ok = False
        print("  excecao:", exc)

    check(
        "MOD-001 mesh deform bind (normal-size cage/target)",
        ok and mod.is_bound,
        "(is_bound=%s)" % getattr(mod, "is_bound", None),
    )

    bpy.data.objects.remove(target, do_unlink=True)
    bpy.data.objects.remove(cage, do_unlink=True)


def main():
    test_gpu001_float_texture_upload()
    test_mod001_meshdeform_bind_normal_case()
    print("\n%d falha(s)" % len(FAILURES) if FAILURES else "\nTodos os testes passaram.")
    if not bpy.app.background:
        bpy.ops.wm.quit_blender()


main()
