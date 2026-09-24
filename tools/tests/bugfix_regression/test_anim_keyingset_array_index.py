"""
ANIM-001 - valida que BKE_keyingset_add_path() rejeita array_index fora do
intervalo da propriedade RNA, caindo para -1 (whole array) em vez de manter
um indice invalido silenciosamente.

Rodar em background, sem GUI:
    RangeEngine.exe --background --python tools/tests/bugfix_regression/test_anim_keyingset_array_index.py

Ou dentro do Text Editor da Range (Alt+P) com uma cena qualquer aberta.
"""
import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s %s" % (status, label, detail))
    if not condition:
        FAILURES.append(label)


def main():
    scene = bpy.context.scene
    obj = bpy.data.objects.new("KSTestObj", None)
    scene.objects.link(obj)

    ks = scene.keying_sets.new(idname="ks_test_array_index")

    # "location" tem 3 componentes (0,1,2); pedir o indice 50 deve cair para -1.
    ksp_out_of_range = ks.paths.add(obj, "location", index=50)
    check(
        "ANIM-001 out-of-range index clamps to -1",
        ksp_out_of_range.array_index == -1,
        "(got %d)" % ksp_out_of_range.array_index,
    )

    # indice valido (1 = eixo Y) deve ser preservado normalmente.
    ksp_in_range = ks.paths.add(obj, "location", index=1)
    check(
        "ANIM-001 in-range index is preserved",
        ksp_in_range.array_index == 1,
        "(got %d)" % ksp_in_range.array_index,
    )

    # index=-1 explicito (todo o array) continua funcionando como antes.
    ksp_whole = ks.paths.add(obj, "location", index=-1)
    check(
        "ANIM-001 whole-array path still works",
        ksp_whole.array_index == 0,
        "(got %d)" % ksp_whole.array_index,
    )

    bpy.data.objects.remove(obj, do_unlink=True)

    print("\n%d falha(s)" % len(FAILURES) if FAILURES else "\nTodos os testes passaram.")


main()
