"""Falha de shader em material de NÓS no pré-voo. Sem bpy.

A falha é injetada pelo GLSL de usuário do material (`script_frag`/`script_vert`), que o codegen acrescenta ao
shader gerado a partir do grafo; a cena de teste é gerada por
`projects-teste/teste-editor-web/criar_m1c_nos.py`. O fixture `preflight-node-material.json` tem o formato que
`package-web.py` grava a partir de `Module.onDiagnostic` (origem = nome do ID, `MA` + nome do material); o log
é ilustrativo, não capturado de um navegador.
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import preflight  # noqa: E402

GPU = os.path.join(ROOT, "source", "source", "blender", "gpu", "intern")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "preflight-node-material.json")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def function_body(source, signature):
    """Do início da assinatura até o "}" na coluna 0 que fecha a função (estilo do código C do Blender)."""
    start = source.index(signature)
    return source[start:source.index("\n}\n", start) + 2]


class NodeMaterialReportTests(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, "r") as handle:
            self.found = preflight.check_preflight(json.load(handle))

    def test_fragment_compile_keeps_material_stage_and_log(self):
        first = self.found[0]
        self.assertEqual(first.rule_id, "WEB-GFX-002")
        self.assertIn("stage fragment", first.message)
        self.assertIn("MAMatNosQuebrado", first.message)
        self.assertEqual(first.location["source"], "MAMatNosQuebrado")
        self.assertEqual(first.fix, "ERROR: 0:412: ';' : syntax error")

    def test_same_log_in_different_materials_is_not_merged(self):
        self.assertEqual([f.rule_id for f in self.found], ["WEB-GFX-002", "WEB-GFX-002"])
        self.assertEqual([f.location["source"] for f in self.found], ["MAMatNosQuebrado", "MAOutroNos"])

    def test_vertex_and_link_of_node_material(self):
        for stage, operation in (("vertex", "compile"), ("", "link")):
            data = {"schema": preflight.PREFLIGHT_SCHEMA, "schema_version": preflight.PREFLIGHT_SCHEMA_VERSION,
                    "shader_errors": [{"material": "MAMatNosQuebrado", "stage": stage, "operation": operation,
                                       "log": "ERROR: m1c", "structured": True}]}
            found = preflight.check_preflight(data)
            self.assertEqual([f.rule_id for f in found], ["WEB-GFX-002"], operation)
            self.assertIn("MAMatNosQuebrado", found[0].message)
            self.assertEqual(found[0].fix, "ERROR: m1c")
            self.assertIn("did not link" if operation == "link" else "stage vertex", found[0].message)


class NodeMaterialInjectionPathTests(unittest.TestCase):
    """Guarda estática: o GLSL de usuário continua chegando ao shader gerado de material de nós.

    Se algum destes pontos mudar, `criar_m1c_nos.py` deixa de provocar a falha e o teste no navegador perde o
    sentido; revise a cena de teste junto com a mudança.
    """

    def test_node_materials_pass_user_code_to_generate_pass(self):
        src = read(os.path.join(GPU, "gpu_material.c"))
        construct_end = function_body(src, "static int gpu_material_construct_end(")
        self.assertIn("material->ma->fragcode", construct_end)
        self.assertIn("material->ma->vertcode", construct_end)
        self.assertRegex(construct_end, r"GPU_generate_pass\([^;]*fragcode, vertcode")
        from_blender = function_body(src, "GPUMaterial *GPU_material_from_blender(")
        nodes = from_blender.index("ntreeGPUMaterialNodes(ma->nodetree, mat, NODE_NEW_SHADING)")
        self.assertGreater(from_blender.index("gpu_material_construct_end(mat, ma->id.name)"), nodes)

    def test_codegen_appends_user_code_to_both_stages(self):
        src = read(os.path.join(GPU, "gpu_codegen.c"))
        for signature in ("static char *code_generate_fragment(", "static char *code_generate_vertex("):
            self.assertIn("BLI_dynstr_append(ds, usercode);", function_body(src, signature), signature)

    def test_shader_failures_report_the_pass_name(self):
        src = read(os.path.join(GPU, "gpu_shader.c"))
        for stage in ('"compile", "vertex"', '"compile", "fragment"', '"link", ""'):
            self.assertRegex(src, r"gpu_shader_web_diagnostic\(%s, diagnostic_name" % re.escape(stage))

    def test_test_scene_uses_rna_properties_that_exist(self):
        rna = read(os.path.join(ROOT, "source", "source", "blender", "makesrna", "intern", "rna_material.c"))
        scene = read(os.path.join(ROOT, "projects-teste", "teste-editor-web", "criar_m1c_nos.py"))
        for prop, field in (("script_frag", "fragcode"), ("script_vert", "vertcode")):
            self.assertIn('RNA_def_property(srna, "%s"' % prop, rna)
            self.assertIn('RNA_def_property_pointer_sdna(prop, NULL, "%s")' % field, rna)
            self.assertIn("mat.%s" % prop, scene)


if __name__ == "__main__":
    unittest.main()
