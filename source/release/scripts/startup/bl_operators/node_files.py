# Node Groups and material presets as files of the GLSL Library (presets/glsl_nodes/*.json).
# A file holds a shader node tree (nodes, values, links, GLSL Script code, nested groups) so a group or
# a whole material can be shared like a .glsl node. See docs/shader-nodes.md.

import bpy
import hashlib
import json
import os
import re
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty

FORMAT = "range-nodes"
VERSION = 1
MAX_FILE_SIZE = 8 * 1024 * 1024
# Settings of the base material a Material node reads (kept with a material preset).
_BASE_PROPS = ("diffuse_color", "diffuse_intensity", "specular_color", "specular_intensity",
               "specular_hardness", "alpha", "emit", "ambient", "use_shadeless")

# Handled one by one (or never restored): identity, layout, sockets, links.
_NODE_SKIP = {p.identifier for p in bpy.types.Node.bl_rna.properties} | {
    "node_tree", "script", "color_ramp", "mapping", "material", "texture", "image",
}


def _value(v):
    """RNA value as JSON (arrays and sets become lists)."""
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    if isinstance(v, set):
        return sorted(v)
    try:
        return [_value(x) for x in v]
    except TypeError:
        return None


def _image_ref(image, warnings):
    if image is None:
        return None
    if image.packed_file is not None or not image.filepath:
        warnings.append("image '%s' is packed or generated: only its name is saved" % image.name)
    return {"name": image.name, "filepath": image.filepath}


# --- save ---------------------------------------------------------------------------------------

def _save_node(node, ctx):
    d = {
        "type": node.bl_idname, "name": node.name, "label": node.label,
        "location": list(node.location), "width": node.width,
        "parent": node.parent.name if node.parent else None,
        "hide": node.hide, "mute": node.mute, "props": {}, "inputs": [], "outputs": [],
    }
    for prop in node.bl_rna.properties:
        ident = prop.identifier
        if ident in _NODE_SKIP or prop.is_readonly or prop.type in {'POINTER', 'COLLECTION'}:
            continue
        v = _value(getattr(node, ident, None))
        if v is not None:
            d["props"][ident] = v
    # Pointers with a policy each.
    if node.bl_idname == "ShaderNodeGroup" and node.node_tree:
        d["group"] = _save_group_ref(node.node_tree, ctx)
    if getattr(node, "script", None) is not None and isinstance(node.script, bpy.types.Text):
        t = node.script
        d["script"] = {"name": t.name, "code": t.as_string(), "file": t.get("glsl_node_file", "")}
    if getattr(node, "image", None) is not None:
        d["image"] = _image_ref(node.image, ctx["warnings"])
    if hasattr(node, "material") and node.material is not None:
        # A material with nodes reads its base settings from another material ("<name> Base", made
        # by use_nodes): saved as "BASE" with those settings, rebuilt the same way on load.
        own = ctx.get("material")
        if own is not None and node.material in (own, bpy.data.materials.get(own.name + " Base")):
            d["material"] = "BASE"
            if node.material != own:
                d["base"] = {k: _value(getattr(node.material, k)) for k in _BASE_PROPS
                             if hasattr(node.material, k)}
        else:
            d["material"] = node.material.name
            ctx["warnings"].append("node '%s' uses material '%s': only its name is saved"
                                   % (node.name, node.material.name))
    if getattr(node, "texture", None) is not None:
        ctx["warnings"].append("node '%s' uses texture '%s': not saved" % (node.name, node.texture.name))
    if getattr(node, "color_ramp", None) is not None:
        r = node.color_ramp
        d["color_ramp"] = {"interpolation": r.interpolation, "color_mode": r.color_mode,
                           "elements": [[e.position, list(e.color)] for e in r.elements]}
    if getattr(node, "mapping", None) is not None and hasattr(node.mapping, "curves"):
        d["curves"] = [[[list(p.location), p.handle_type] for p in c.points] for c in node.mapping.curves]
    # ID properties (GLSL Script image params "img_<name>").
    idp = {}
    for k in node.keys():
        v = node[k]
        if isinstance(v, bpy.types.Image):
            idp[k] = {"image": _image_ref(v, ctx["warnings"])}
        elif isinstance(v, (int, float, str)):
            idp[k] = v
    if idp:
        d["idprops"] = idp
    for key, sockets in (("inputs", node.inputs), ("outputs", node.outputs)):
        for i, s in enumerate(sockets):
            entry = {"id": s.identifier, "index": i, "type": s.bl_idname}
            if hasattr(s, "default_value"):
                entry["value"] = _value(s.default_value)
            d[key].append(entry)
    return d


def _save_tree(tree, ctx):
    data = {"nodes": [_save_node(n, ctx) for n in tree.nodes], "links": []}
    index = {}
    for n in tree.nodes:
        index[n.name] = (list(n.inputs), list(n.outputs))
    for link in tree.links:
        fn, tn = link.from_node, link.to_node
        data["links"].append({
            "from": fn.name, "from_id": link.from_socket.identifier,
            "from_index": list(fn.outputs).index(link.from_socket),
            "to": tn.name, "to_id": link.to_socket.identifier,
            "to_index": list(tn.inputs).index(link.to_socket),
        })
    return data


def _save_group_ref(group, ctx):
    groups = ctx["groups"]
    if group.name in groups:
        return group.name
    if group.name in ctx["visiting"]:
        raise ValueError("node group '%s' contains itself" % group.name)
    ctx["visiting"].add(group.name)
    g = _save_tree(group, ctx)
    g["interface"] = {
        key: [{"type": s.bl_socket_idname, "name": s.name,
               "value": _value(getattr(s, "default_value", None)),
               "min": getattr(s, "min_value", None), "max": getattr(s, "max_value", None)}
              for s in sockets]
        for key, sockets in (("inputs", group.inputs), ("outputs", group.outputs))
    }
    ctx["visiting"].discard(group.name)
    groups[group.name] = g
    return group.name


def save_file(path, kind, name, category, description, tree=None, group=None, material=None):
    """Writes a group (group=) or a material tree (material=). Returns the warnings."""
    ctx = {"groups": {}, "visiting": set(), "warnings": [], "material": material}
    doc = {"format": FORMAT, "version": VERSION, "kind": kind, "name": name,
           "category": category or "Custom", "description": description or ""}
    if kind == "group":
        doc["root"] = _save_group_ref(group, ctx)
    else:
        doc["tree"] = _save_tree(material.node_tree, ctx)
        doc["material"] = {"alpha_blend": material.game_settings.alpha_blend,
                           "use_backface_culling": material.game_settings.use_backface_culling}
    doc["groups"] = ctx["groups"]
    text = json.dumps(doc, indent=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return ctx["warnings"]


# --- load ---------------------------------------------------------------------------------------

def read_file(path):
    if os.path.getsize(path) > MAX_FILE_SIZE:
        raise ValueError("file too large")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError("not a node file of the GLSL Library")
    if doc.get("version", 0) > VERSION:
        raise ValueError("made by a newer engine (version %s)" % doc.get("version"))
    if doc.get("kind") not in {"group", "material"}:
        raise ValueError("unknown kind %r" % doc.get("kind"))
    return doc


def _check_tree(data, doc):
    """Before touching the file data: every node type exists and every group is in the file."""
    for n in data.get("nodes", []):
        if not hasattr(bpy.types, n["type"]):
            raise ValueError("node type %s does not exist in this engine" % n["type"])
        if "group" in n and n["group"] not in doc.get("groups", {}):
            raise ValueError("group '%s' missing in the file" % n["group"])


def _hash(data):
    return hashlib.sha1(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def _state_hash(group):
    """The group as it is now: an edit after loading changes it, so the group is not reused."""
    ctx = {"groups": {}, "visiting": {group.name}, "warnings": [], "material": None}
    try:
        return _hash(_save_tree(group, ctx))
    except Exception:
        return None


def _find_image(ref, warnings):
    if not ref:
        return None
    image = bpy.data.images.get(ref["name"])
    if image is None and ref.get("filepath"):
        try:
            image = bpy.data.images.load(ref["filepath"], check_existing=True)
        except RuntimeError:
            image = None
    if image is None:
        warnings.append("image '%s' not found" % ref["name"])
    return image


def _find_text(script):
    for t in bpy.data.texts:
        if t.as_string() == script["code"]:
            return t
    t = bpy.data.texts.new(script["name"])
    t.from_string(script["code"])
    if script.get("file"):
        t["glsl_node_file"] = script["file"]
    return t


def _socket(sockets, sid, index, warnings, what):
    same = [s for s in sockets if s.identifier == sid]
    if len(same) == 1:
        return same[0]
    if 0 <= index < len(sockets) and (not same or sockets[index] in same):
        return sockets[index]
    warnings.append("%s: socket %s not found" % (what, sid))
    return None


def _set(obj, attr, value, warnings, what):
    try:
        setattr(obj, attr, value)
    except (AttributeError, TypeError, ValueError):
        warnings.append("%s: %s not restored" % (what, attr))


def _build_tree(tree, data, doc, ctx, context):
    warnings = ctx["warnings"]
    nodes = {}
    # 1) nodes, with the properties and pointers that change sockets
    for d in data["nodes"]:
        node = tree.nodes.new(d["type"])
        node.name = d["name"]
        nodes[d["name"]] = node
        what = "node '%s'" % d["name"]
        for k, v in d.get("props", {}).items():
            if isinstance(v, list) and k in {p.identifier for p in node.bl_rna.properties
                                             if p.type == 'ENUM' and p.is_enum_flag}:
                v = set(v)
            _set(node, k, v, warnings, what)
        if "group" in d:
            node.node_tree = _load_group(d["group"], doc, ctx, context)
        if "script" in d:
            node.script = _find_text(d["script"])
        if "image" in d:
            node.image = _find_image(d["image"], warnings)
        if "material" in d:
            if d["material"] in {"BASE", "SELF"}:
                # Never the material itself (it would read itself: black): the base made by use_nodes.
                mat = ctx.get("base")
                if mat is not None:
                    for k, v in d.get("base", {}).items():
                        _set(mat, k, v, warnings, what)
            else:
                mat = bpy.data.materials.get(d["material"])
            if mat is None:
                warnings.append("%s: material '%s' not found" % (what, d["material"]))
            else:
                node.material = mat
        for k, v in d.get("idprops", {}).items():
            if isinstance(v, dict) and "image" in v:
                img = _find_image(v["image"], warnings)
                if img is not None:
                    node[k] = img
            else:
                node[k] = v
        if "color_ramp" in d:
            r, cr = node.color_ramp, d["color_ramp"]
            _set(r, "interpolation", cr["interpolation"], warnings, what)
            _set(r, "color_mode", cr["color_mode"], warnings, what)
            while len(r.elements) > max(1, len(cr["elements"])):
                r.elements.remove(r.elements[-1])
            while len(r.elements) < len(cr["elements"]):
                r.elements.new(0.5)
            for e, (pos, col) in zip(r.elements, cr["elements"]):
                e.position = pos
                e.color = col
        if "curves" in d:
            for c, pts in zip(node.mapping.curves, d["curves"]):
                while len(c.points) < len(pts):
                    c.points.new(0.5, 0.5)
                if len(c.points) > len(pts):
                    warnings.append("%s: curve has extra points" % what)
                for p, (loc, handle) in zip(c.points, pts):
                    p.location = loc
                    _set(p, "handle_type", handle, warnings, what)
            if hasattr(node.mapping, "update"):
                node.mapping.update()
    # 2) GLSL Script sockets come from the code: build them before the values and links
    tree.interface_update(context)
    # 3) layout and socket values
    for d in data["nodes"]:
        node = nodes[d["name"]]
        if d.get("parent") in nodes:
            node.parent = nodes[d["parent"]]
        node.location = d["location"]
        node.width = d.get("width", node.width)
        node.label = d.get("label", "")
        node.hide = d.get("hide", False)
        node.mute = d.get("mute", False)
        # Material nodes: writing a socket copies every socket into the material, whose own values
        # (restored above) are the real ones; the saved socket values may be stale.
        sockets = [] if "material" in d else d.get("inputs", [])
        for s in sockets:
            if "value" not in s or s["value"] is None:
                continue
            sock = _socket(node.inputs, s["id"], s["index"], warnings, "node '%s'" % d["name"])
            if sock is not None and hasattr(sock, "default_value"):
                _set(sock, "default_value", s["value"], warnings, "node '%s'" % d["name"])
    # 4) links
    for l in data["links"]:
        a, b = nodes.get(l["from"]), nodes.get(l["to"])
        what = "link %s -> %s" % (l["from"], l["to"])
        if a is None or b is None:
            warnings.append(what + ": node missing")
            continue
        out = _socket(a.outputs, l["from_id"], l["from_index"], warnings, what)
        inp = _socket(b.inputs, l["to_id"], l["to_index"], warnings, what)
        if out is not None and inp is not None:
            tree.links.new(out, inp)
    return nodes


def _load_group(name, doc, ctx, context):
    if name in ctx["built"]:
        return ctx["built"][name]
    data = doc["groups"][name]
    digest = _hash(data)
    # Same name and same content: reuse (a group with that name but other content is left alone).
    for g in bpy.data.node_groups:
        if (g.bl_idname == 'ShaderNodeTree' and g.get("range_nodes_hash") == digest and
                g.get("range_nodes_state") == _state_hash(g)):
            ctx["built"][name] = g
            return g
    if name in ctx["visiting"]:
        raise ValueError("node group '%s' contains itself" % name)
    ctx["visiting"].add(name)
    _check_tree(data, doc)
    group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    try:
        for key, sockets in (("inputs", group.inputs), ("outputs", group.outputs)):
            for s in data["interface"][key]:
                sock = sockets.new(s["type"], s["name"])
                for attr, k in (("default_value", "value"), ("min_value", "min"), ("max_value", "max")):
                    if s.get(k) is not None and hasattr(sock, attr):
                        _set(sock, attr, s[k], ctx["warnings"], "group '%s'" % name)
        _build_tree(group, data, doc, ctx, context)
    except Exception:
        bpy.data.node_groups.remove(group)
        raise
    group["range_nodes_hash"] = digest
    group["range_nodes_state"] = _state_hash(group)
    ctx["visiting"].discard(name)
    ctx["built"][name] = group
    return group


def load_group(doc, context):
    ctx = {"built": {}, "visiting": set(), "warnings": []}
    return _load_group(doc["root"], doc, ctx, context), ctx["warnings"]


def load_material(doc, context, name):
    """A new material (the current one is not touched): built fully before it is returned."""
    _check_tree(doc["tree"], doc)
    mat = bpy.data.materials.new(name)
    ctx = {"built": {}, "visiting": set(), "warnings": [], "material": mat}
    try:
        mat.use_nodes = True
        tree = mat.node_tree
        for n in tree.nodes:
            if getattr(n, "material", None) is not None and n.material != mat:
                ctx["base"] = n.material
        if ctx.get("base") is None:
            ctx["base"] = bpy.data.materials.new(name + " Base")
        for n in list(tree.nodes):
            tree.nodes.remove(n)
        _build_tree(tree, doc["tree"], doc, ctx, context)
        for k, v in doc.get("material", {}).items():
            _set(mat.game_settings, k, v, ctx["warnings"], "material")
    except Exception:
        bpy.data.materials.remove(mat)
        raise
    return mat, ctx["warnings"]


# --- library ------------------------------------------------------------------------------------

def node_file_library():
    """Node group and material files: (path, kind, name, category, description)."""
    found = []
    for folder in bpy.utils.preset_paths("glsl_nodes"):
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith(".json"):
                continue
            path = os.path.join(folder, fname)
            try:
                doc = read_file(path)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            found.append((path, doc["kind"], doc.get("name") or fname[:-5],
                          doc.get("category") or "Custom", doc.get("description", "")))
    return found


def _report_warnings(op, warnings):
    for w in warnings[:10]:
        print("Node file:", w)
    if warnings:
        op.report({'WARNING'}, "%d item(s) not restored (see the console): %s" % (len(warnings), warnings[0]))


def _description(path):
    for p, _kind, _name, _cat, desc in node_file_library():
        if p == path and desc:
            return desc
    return None


def _node_editor_poll(context):
    space = context.space_data
    return (space is not None and space.type == 'NODE_EDITOR' and
            space.tree_type == 'ShaderNodeTree' and space.edit_tree is not None)


class NODE_OT_glsl_group_add(Operator):
    """Add a node group from a file of the GLSL Library (game engine)"""
    bl_idname = "node.glsl_group_add"
    bl_label = "Add Node Group File"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(name="File", subtype='FILE_PATH')

    @classmethod
    def poll(cls, context):
        return _node_editor_poll(context)

    @classmethod
    def description(cls, context, properties):
        return _description(properties.filepath) or cls.__doc__

    def execute(self, context):
        try:
            doc = read_file(self.filepath)
            if doc["kind"] != "group":
                raise ValueError("this file is a material preset")
            group, warnings = load_group(doc, context)
        except Exception as ex:  # a bad or foreign file: a message, not a traceback
            self.report({'ERROR'}, "Cannot load %s: %s" % (os.path.basename(self.filepath), ex))
            return {'CANCELLED'}
        space = context.space_data
        tree = space.edit_tree
        if group == tree:
            self.report({'ERROR'}, "A group can not contain itself")
            return {'CANCELLED'}
        for n in tree.nodes:
            n.select = False
        node = tree.nodes.new("ShaderNodeGroup")
        node.node_tree = group
        node.location = space.cursor_location
        node.select = True
        tree.nodes.active = node
        _report_warnings(self, warnings)
        return {'FINISHED'}


class NODE_OT_glsl_material_preset_load(Operator):
    """Make a new material from a preset file of the GLSL Library and put it in the active slot (the old
material is kept in the file)"""
    bl_idname = "node.glsl_material_preset_load"
    bl_label = "Load Material Preset"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(name="File", subtype='FILE_PATH')

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}

    @classmethod
    def description(cls, context, properties):
        return _description(properties.filepath) or cls.__doc__

    def execute(self, context):
        try:
            doc = read_file(self.filepath)
            if doc["kind"] != "material":
                raise ValueError("this file is a node group")
            mat, warnings = load_material(doc, context, doc.get("name") or "Preset")
        except Exception as ex:  # a bad or foreign file: a message, not a traceback
            self.report({'ERROR'}, "Cannot load %s: %s" % (os.path.basename(self.filepath), ex))
            return {'CANCELLED'}
        ob = context.object
        if ob.material_slots:
            ob.material_slots[ob.active_material_index].material = mat
        else:
            ob.data.materials.append(mat)
        _report_warnings(self, warnings)
        return {'FINISHED'}


def _safe_name(name):
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip() or "node_file"


def _save_props(cls):
    """The dialog fields, on each class (annotations of a mixin are not registered)."""
    cls.__annotations__ = dict(getattr(cls, "__annotations__", {}), **{
        "name": StringProperty(name="Name"),
        "category": StringProperty(name="Category", default="Custom"),
        "desc": StringProperty(name="Description"),
        "overwrite": BoolProperty(name="Overwrite", description="Replace a library file with the same name"),
    })
    return cls


class _SaveBase:
    def invoke(self, context, event):
        self.name = self.default_name(context)
        return context.window_manager.invoke_props_dialog(self)

    def target(self):
        folder = bpy.utils.user_resource('SCRIPTS', "presets/glsl_nodes", create=True)
        return os.path.join(folder, _safe_name(self.name) + ".json")

    def write(self, **kw):
        path = self.target()
        if os.path.exists(path) and not self.overwrite:
            self.report({'ERROR'}, "%s exists: turn on Overwrite" % path)
            return {'CANCELLED'}
        try:
            warnings = save_file(path, name=self.name, category=self.category,
                                 description=self.desc, **kw)
        except (OSError, ValueError) as ex:
            self.report({'ERROR'}, "Cannot save: %s" % ex)
            return {'CANCELLED'}
        _report_warnings(self, warnings)
        if not warnings:
            self.report({'INFO'}, "Saved %s" % path)
        return {'FINISHED'}


@_save_props
class NODE_OT_glsl_group_save(_SaveBase, Operator):
    """Save the node group of the active node as a file of the GLSL Library"""
    bl_idname = "node.glsl_group_save"
    bl_label = "Save Group to Library"

    @classmethod
    def poll(cls, context):
        if not _node_editor_poll(context):
            return False
        node = context.space_data.edit_tree.nodes.active
        return node is not None and node.bl_idname == "ShaderNodeGroup" and node.node_tree is not None

    def default_name(self, context):
        return context.space_data.edit_tree.nodes.active.node_tree.name

    def execute(self, context):
        group = context.space_data.edit_tree.nodes.active.node_tree
        return self.write(kind="group", group=group)


@_save_props
class NODE_OT_glsl_material_preset_save(_SaveBase, Operator):
    """Save the node tree of the active material as a material preset of the GLSL Library"""
    bl_idname = "node.glsl_material_preset_save"
    bl_label = "Save Material as Preset"

    @classmethod
    def poll(cls, context):
        mat = getattr(context, "material", None) or (context.object and context.object.active_material)
        return mat is not None and mat.use_nodes and mat.node_tree is not None

    def _mat(self, context):
        return getattr(context, "material", None) or context.object.active_material

    def default_name(self, context):
        return self._mat(context).name

    def execute(self, context):
        return self.write(kind="material", material=self._mat(context))


classes = (
    NODE_OT_glsl_group_add,
    NODE_OT_glsl_material_preset_load,
    NODE_OT_glsl_group_save,
    NODE_OT_glsl_material_preset_save,
)
