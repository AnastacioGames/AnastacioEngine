# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Contributor(s): Campbell Barton
#
# ***** END GPL LICENSE BLOCK *****

# <pep8 compliant>

import bpy


def build_property_typemap(skip_classes, skip_typemap):

    property_typemap = {}

    for attr in dir(bpy.types):
        # Skip internal methods.
        if attr.startswith("_"):
            continue
        cls = getattr(bpy.types, attr)
        if issubclass(cls, skip_classes):
            continue
        bl_rna = getattr(cls, "bl_rna", None)
        # Needed to skip classes added to the modules `__dict__`.
        if bl_rna is None:
            continue

        # # to support skip-save we can't get all props
        # properties = cls.bl_rna.properties.keys()
        properties = []
        for prop_id, prop in bl_rna.properties.items():
            if not prop.is_skip_save:
                properties.append(prop_id)

        properties.remove("rna_type")
        property_typemap[attr] = properties

    if skip_typemap:
        for cls_name, properties_blacklist in skip_typemap.items():
            properties = property_typemap.get(cls_name)
            if properties is not None:
                for prop_id in properties_blacklist:
                    try:
                        properties.remove(prop_id)
                    except:
                        print("skip_typemap unknown prop_id '%s.%s'" % (cls_name, prop_id))
            else:
                print("skip_typemap unknown class '%s'" % cls_name)

    return property_typemap


def print_ln(data):
    print(data, end="")


def rna2xml(
        fw=print_ln,
        root_node="",
        root_rna=None,  # must be set
        root_rna_skip=set(),
        root_ident="",
        ident_val="  ",
        skip_classes=(
            bpy.types.Operator,
            bpy.types.Panel,
            bpy.types.KeyingSet,
            bpy.types.Header,
            bpy.types.PropertyGroup,
        ),
        skip_typemap=None,
        property_typemap=None,
        pretty_format=True,
        method='DATA',
):

    from xml.sax.saxutils import quoteattr
    if property_typemap is None:
        property_typemap = build_property_typemap(skip_classes, skip_typemap)

    # don't follow properties of this type, just reference them by name
    # they MUST have a unique 'name' property.
    # 'ID' covers most types
    referenced_classes = (
        bpy.types.ID,
        bpy.types.Bone,
        bpy.types.ActionGroup,
        bpy.types.PoseBone,
        bpy.types.Node,
        bpy.types.Sequence,
    )

    def number_to_str(val, val_type):
        if val_type == int:
            return "%d" % val
        elif val_type == float:
            return "%.6g" % val
        elif val_type == bool:
            return "TRUE" if val else "FALSE"
        else:
            raise NotImplementedError("this type is not a number %s" % val_type)

    def rna2xml_node(ident, value, parent):
        ident_next = ident + ident_val

        # divide into attrs and nodes.
        node_attrs = []
        nodes_items = []
        nodes_lists = []

        value_type = type(value)

        if issubclass(value_type, skip_classes):
            return

        # XXX, fixme, pointcache has eternal nested pointer to its self.
        if value == parent:
            return

        value_type_name = value_type.__name__
        # Some legacy RNA wrappers can expose internal Python values (such as
        # a module) rather than an RNA struct.  They have no XML schema and
        # must not be recursed into.
        if value_type_name not in property_typemap:
            return
        for prop in property_typemap[value_type_name]:
            subvalue = getattr(value, prop)
            subvalue_type = type(subvalue)

            if subvalue_type in {int, bool, float}:
                node_attrs.append("%s=\"%s\"" % (prop, number_to_str(subvalue, subvalue_type)))
            elif subvalue_type is str:
                node_attrs.append("%s=%s" % (prop, quoteattr(subvalue)))
            elif subvalue_type is set:
                node_attrs.append("%s=%s" % (prop, quoteattr("{" + ",".join(list(subvalue)) + "}")))
            elif subvalue is None:
                node_attrs.append("%s=\"NONE\"" % prop)
            elif issubclass(subvalue_type, referenced_classes):
                # special case, ID's are always referenced.
                subvalue_name = getattr(subvalue, "name", None)
                if subvalue_name is not None:
                    node_attrs.append("%s=%s" % (prop, quoteattr(subvalue_type.__name__ + "::" + subvalue_name)))
            else:
                # RNA arrays and collections are C-backed wrappers.  Calling
                # list() on them first makes CPython 3.11 attempt a sequence
                # conversion which can receive an invalid item from the
                # legacy RNA iterator.  Process their native interfaces
                # directly instead.
                subvalue_type_name = subvalue_type.__name__
                if subvalue_type_name == "bpy_prop_array":
                    # The embedded legacy RNA wrapper implements ``for`` by
                    # materializing a Python sequence.  On CPython 3.11 this
                    # can fail for a color vector after its final element.
                    # Indexed reads use RNA's bounded array accessor instead.
                    subvalue_items = [subvalue[index] for index in range(len(subvalue))]

                    # check if this is a 0-1 color (rgb, rgba)
                    # in that case write as a hexadecimal
                    prop_rna = value.bl_rna.properties[prop]
                    if (prop_rna.subtype == 'COLOR_GAMMA' and
                            prop_rna.hard_min == 0.0 and
                            prop_rna.hard_max == 1.0 and
                            prop_rna.array_length in {3, 4}):
                        # -----
                        # color
                        array_value = "#" + "".join(
                            "%.2x" % int(item * 255) for item in subvalue_items
                        )

                    else:
                        # default
                        def str_recursive(s):
                            subsubvalue_type = type(s)
                            if subsubvalue_type in {int, float, bool}:
                                return number_to_str(s, subsubvalue_type)
                            else:
                                return " ".join(
                                    str_recursive(s[index]) for index in range(len(s))
                                )

                        array_value = " ".join(str_recursive(item) for item in subvalue_items)

                    node_attrs.append("%s=\"%s\"" % (prop, array_value))
                elif subvalue_type_name == "bpy_prop_collection":
                    # The legacy C iterator for fixed-size collections can
                    # return an invalid object while checking for its end on
                    # CPython 3.11.  Indexing uses the collection's verified
                    # RNA length and never enters that termination path.
                    subvalue_ls = [subvalue[index] for index in range(len(subvalue))]
                    if subvalue_ls and type(subvalue_ls[0]) in {int, float, bool}:
                        array_value = " ".join(
                            number_to_str(item, type(item)) for item in subvalue_ls
                        )
                        node_attrs.append("%s=\"%s\"" % (prop, array_value))
                    else:
                        nodes_lists.append((prop, subvalue_ls, subvalue_type))
                elif subvalue_type_name.startswith("bpy_prop_"):
                    # Do not call list() on an unknown C-backed RNA wrapper.
                    # Its iterator may be unsafe with the embedded Python
                    # version and its data cannot be represented reliably.
                    continue
                else:
                    try:
                        # Mathutils colors/vectors also use a legacy iterator
                        # in this build.  Prefer their bounded index API for
                        # the same reason as RNA arrays above.
                        subvalue_ls = [subvalue[index] for index in range(len(subvalue))]
                    except:
                        subvalue_ls = None

                    if subvalue_ls is None:
                        nodes_items.append((prop, subvalue, subvalue_type))
                    elif subvalue_ls and all(type(item) in {int, float, bool} for item in subvalue_ls):
                        # Some legacy RNA wrappers don't advertise
                        # ``bpy_prop_array`` as their Python type.  Their
                        # values are still native scalars, so encode them as
                        # an attribute instead of recursing into ``float``.
                        def str_recursive(s):
                            subsubvalue_type = type(s)
                            if subsubvalue_type in {int, float, bool}:
                                return number_to_str(s, subsubvalue_type)
                            else:
                                return " ".join(
                                    str_recursive(s[index]) for index in range(len(s))
                                )

                        array_value = " ".join(str_recursive(item) for item in subvalue_ls)
                        node_attrs.append("%s=\"%s\"" % (prop, array_value))
                    else:
                        nodes_lists.append((prop, subvalue_ls, subvalue_type))

        # declare + attributes
        if pretty_format:
            if node_attrs:
                fw("%s<%s\n" % (ident, value_type_name))
                for node_attr in node_attrs:
                    fw("%s%s\n" % (ident_next, node_attr))
                fw("%s>\n" % (ident_next,))
            else:
                fw("%s<%s>\n" % (ident, value_type_name))
        else:
            fw("%s<%s %s>\n" % (ident, value_type_name, " ".join(node_attrs)))

        # unique members
        for prop, subvalue, subvalue_type in nodes_items:
            fw("%s<%s>\n" % (ident_next, prop))  # XXX, this is awkward, how best to solve?
            rna2xml_node(ident_next + ident_val, subvalue, value)
            fw("%s</%s>\n" % (ident_next, prop))  # XXX, need to check on this.

        # list members
        for prop, subvalue, subvalue_type in nodes_lists:
            fw("%s<%s>\n" % (ident_next, prop))
            for subvalue_item in subvalue:
                if subvalue_item is not None:
                    rna2xml_node(ident_next + ident_val, subvalue_item, value)
            fw("%s</%s>\n" % (ident_next, prop))

        fw("%s</%s>\n" % (ident, value_type_name))

    # -------------------------------------------------------------------------
    # needs re-working to be generic

    if root_node:
        fw("%s<%s>\n" % (root_ident, root_node))

    # bpy.data
    if method == 'DATA':
        ident = root_ident + ident_val
        for attr in dir(root_rna):

            # exceptions
            if attr.startswith("_"):
                continue
            elif attr in root_rna_skip:
                continue

            value = getattr(root_rna, attr)
            try:
                ls = value[:]
            except:
                ls = None

            if type(ls) == list:
                fw("%s<%s>\n" % (ident, attr))
                for blend_id in ls:
                    rna2xml_node(ident + ident_val, blend_id, None)
                fw("%s</%s>\n" % (ident_val, attr))
    # any attribute
    elif method == 'ATTR':
        rna2xml_node(root_ident, root_rna, None)

    if root_node:
        fw("%s</%s>\n" % (root_ident, root_node))


def xml2rna(
        root_xml, *,
        root_rna=None,  # must be set
):

    def rna2xml_node(xml_node, value):
        # print("evaluating:", xml_node.nodeName)

        # ---------------------------------------------------------------------
        # Simple attributes

        for attr in xml_node.attributes.keys():
            # print("  ", attr)
            subvalue = getattr(value, attr, Ellipsis)

            if subvalue is Ellipsis:
                print("%s.%s not found" % (type(value).__name__, attr))
            else:
                value_xml = xml_node.attributes[attr].value

                subvalue_type = type(subvalue)
                tp_name = 'UNKNOWN'
                if subvalue_type == float:
                    value_xml_coerce = float(value_xml)
                    tp_name = 'FLOAT'
                elif subvalue_type == int:
                    value_xml_coerce = int(value_xml)
                    tp_name = 'INT'
                elif subvalue_type == bool:
                    value_xml_coerce = {'TRUE': True, 'FALSE': False}[value_xml]
                    tp_name = 'BOOL'
                elif subvalue_type == str:
                    value_xml_coerce = value_xml
                    tp_name = 'STR'
                elif hasattr(subvalue, "__len__"):
                    if value_xml.startswith("#"):
                        # read hexadecimal value as float array
                        value_xml_split = value_xml[1:]
                        value_xml_coerce = [int(value_xml_split[i:i + 2], 16) /
                                            255 for i in range(0, len(value_xml_split), 2)]
                        del value_xml_split
                    else:
                        value_xml_split = value_xml.split()
                        try:
                            value_xml_coerce = [int(v) for v in value_xml_split]
                        except ValueError:
                            try:
                                value_xml_coerce = [float(v) for v in value_xml_split]
                            except ValueError:  # bool vector property
                                value_xml_coerce = [{'TRUE': True, 'FALSE': False}[v] for v in value_xml_split]
                        del value_xml_split
                    tp_name = 'ARRAY'

#                print("  %s.%s (%s) --- %s" % (type(value).__name__, attr, tp_name, subvalue_type))
                try:
                    setattr(value, attr, value_xml_coerce)
                except ValueError:
                    # size mismatch
                    val = getattr(value, attr)
                    if len(val) < len(value_xml_coerce):
                        setattr(value, attr, value_xml_coerce[:len(val)])
                    else:
                        setattr(value, attr, list(value_xml_coerce) + list(val)[len(value_xml_coerce):])

        # ---------------------------------------------------------------------
        # Complex attributes
        for child_xml in xml_node.childNodes:
            if child_xml.nodeType == child_xml.ELEMENT_NODE:
                # print()
                # print(child_xml.nodeName)
                subvalue = getattr(value, child_xml.nodeName, None)
                if subvalue is not None:

                    elems = []
                    for child_xml_real in child_xml.childNodes:
                        if child_xml_real.nodeType == child_xml_real.ELEMENT_NODE:
                            elems.append(child_xml_real)
                    del child_xml_real

                    if hasattr(subvalue, "__len__"):
                        # Collection
                        if len(elems) != len(subvalue):
                            print("Size Mismatch! collection:", child_xml.nodeName)
                        else:
                            for i in range(len(elems)):
                                child_xml_real = elems[i]
                                subsubvalue = subvalue[i]

                                if child_xml_real is None or subsubvalue is None:
                                    print("None found %s - %d collection:", (child_xml.nodeName, i))
                                else:
                                    rna2xml_node(child_xml_real, subsubvalue)

                    else:
                        # print(elems)

                        if len(elems) == 1:
                            # sub node named by its type
                            child_xml_real, = elems

                            # print(child_xml_real, subvalue)
                            rna2xml_node(child_xml_real, subvalue)
                        else:
                            # empty is valid too
                            pass

    rna2xml_node(root_xml, root_rna)


# -----------------------------------------------------------------------------
# Utility function used by presets.
# The idea is you can run a preset like a script with a few args.
#
# This roughly matches the operator 'bpy.ops.script.python_file_run'


def _get_context_val(context, path):
    path_full = "context." + path
    try:
        value = eval(path_full)
    except:
        import traceback
        traceback.print_exc()
        print("Error: %r could not be found" % path_full)

        value = Ellipsis

    return value


def xml_file_run(context, filepath, rna_map):

    import xml.dom.minidom

    xml_nodes = xml.dom.minidom.parse(filepath)
    bpy_xml = xml_nodes.getElementsByTagName("bpy")[0]

    for rna_path, xml_tag in rna_map:

        # first get xml
        # TODO, error check
        xml_node = bpy_xml.getElementsByTagName(xml_tag)[0]

        value = _get_context_val(context, rna_path)

        if value is not Ellipsis and value is not None:
            print("  loading XML: %r -> %r" % (filepath, rna_path))
            xml2rna(xml_node, root_rna=value)


def xml_file_write(context, filepath, rna_map, *, skip_typemap=None):
    """Write an RNA XML file without ever leaving a partial preset behind.

    Serializing an RNA property may raise an exception.  Writing directly to
    ``filepath`` meant that exception corrupted an existing preset (or left a
    new one half-written).  Build and validate the document in the destination
    directory, then atomically replace the final file only on success.
    """
    import os
    import tempfile
    import xml.etree.ElementTree as ElementTree

    filepath_dir = os.path.dirname(os.path.abspath(filepath))
    filepath_name = os.path.basename(filepath)
    skip_classes = (
        bpy.types.Operator,
        bpy.types.Panel,
        bpy.types.KeyingSet,
        bpy.types.Header,
        bpy.types.PropertyGroup,
    )
    property_typemap = build_property_typemap(skip_classes, skip_typemap)
    file_descriptor, filepath_tmp = tempfile.mkstemp(
        prefix=".%s." % filepath_name,
        suffix=".tmp",
        dir=filepath_dir,
        text=True,
    )

    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            # Keep serialization in Python memory and perform one write.  The
            # embedded Python 3.11 runtime can access-violate after hundreds
            # of small bound-method calls into its legacy file wrapper.
            # This also avoids any partially emitted XML before validation.
            document_parts = []
            fw = document_parts.append
            fw("<bpy>\n")

            for rna_path, xml_tag in rna_map:
                # xml_tag is ignored, we get this from the rna.
                value = _get_context_val(context, rna_path)
                rna2xml(fw,
                        root_rna=value,
                        method='ATTR',
                        root_ident="  ",
                        ident_val="  ",
                        skip_classes=skip_classes,
                        skip_typemap=skip_typemap,
                        property_typemap=property_typemap,
                        )

            fw("</bpy>\n")
            file.write("".join(document_parts))
            file.flush()
            os.fsync(file.fileno())

        # Do not publish a file that was not completed by the serializer.
        ElementTree.parse(filepath_tmp)
        os.replace(filepath_tmp, filepath)
        filepath_tmp = None
    finally:
        if filepath_tmp is not None:
            try:
                os.remove(filepath_tmp)
            except OSError:
                pass
