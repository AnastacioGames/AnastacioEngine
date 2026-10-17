"""Escreve um inventario tecnico da cena de agua revisada.

Uso:
  AnastacioEngine.exe -b <cena.range> --factory-startup --python inspecionar_agua_revisado.py -- <relatorio.txt>
"""

from __future__ import print_function

import bpy
import os
import sys


def material_lines(material):
    lines = ["  material: %s nodes=%s blend=%s diffuse=%s" % (
        material.name, material.use_nodes, material.blend_method, tuple(material.diffuse_color))]
    for index, slot in enumerate(material.texture_slots):
        if slot and slot.texture:
            texture = slot.texture
            image = getattr(texture, "image", None)
            lines.append("    slot %d: %s type=%s image=%s" % (
                index, texture.name, texture.type, image.filepath if image else "-"))
    return lines


def main():
    try:
        output = sys.argv[sys.argv.index("--") + 1]
    except (ValueError, IndexError):
        raise RuntimeError("Informe o arquivo de relatorio apos --")

    lines = ["scene: %s" % bpy.context.scene.name]
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type != 'MESH':
            continue
        lines.append("object: %s vertices=%d polygons=%d materials=%d" % (
            obj.name, len(obj.data.vertices), len(obj.data.polygons), len(obj.data.materials)))
        for material in obj.data.materials:
            if material:
                lines.extend(material_lines(material))
    lines.append("images:")
    for image in sorted(bpy.data.images, key=lambda item: item.name):
        lines.append("  %s: %s" % (image.name, image.filepath))
    with open(output, "w") as report:
        report.write("\n".join(lines) + "\n")


main()
