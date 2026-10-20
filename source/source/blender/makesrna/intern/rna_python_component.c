/**
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * Contributor(s): Mitchell Stokes, Diego Lopes, Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

#include <stdlib.h>
#include <float.h>
#include <limits.h>

#include "RNA_define.h"

#include "rna_internal.h"
#include "DNA_python_component_types.h"
#include "DNA_property_types.h"

#include "WM_types.h"

#ifdef RNA_RUNTIME

#include "BLI_listbase.h"
#include "BLI_string.h"

#include "BKE_global.h"
#include "BKE_main.h"

#include "DNA_object_types.h"
#include "DNA_scene_types.h"

static StructRNA* rna_PythonComponentProperty_refine(struct PointerRNA *ptr)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;

	switch(cprop->type) {
		case CPROP_TYPE_BOOLEAN:
			return &RNA_ComponentBooleanProperty;
		case CPROP_TYPE_INT:
			return &RNA_ComponentIntProperty;
		case CPROP_TYPE_FLOAT:
			return &RNA_ComponentFloatProperty;
		case CPROP_TYPE_STRING:
			return &RNA_ComponentStringProperty;
		case CPROP_TYPE_SET:
			return &RNA_ComponentSetProperty;
		case CPROP_TYPE_VEC2:
			return &RNA_ComponentVector2DProperty;
		case CPROP_TYPE_VEC3:
			return &RNA_ComponentVector3DProperty;
		case CPROP_TYPE_VEC4:
			return &RNA_ComponentVector4DProperty;
		case CPROP_TYPE_COL3:
			return &RNA_ComponentColor3Property;
		case CPROP_TYPE_COL4:
			return &RNA_ComponentColor4Property;
		case CPROP_TYPE_OBJECT:
			return &RNA_ComponentObjectProperty;
		case CPROP_TYPE_SCENE:
			return &RNA_ComponentSceneProperty;
		default:
			return &RNA_PythonComponentProperty;
	}
}

static void rna_ComponentIntProperty_range(PointerRNA *ptr, int *min, int *max, int *softmin, int *softmax)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;

	*min = (cprop->metaflag & CPROP_META_MIN) ? (int)cprop->min : INT_MIN;
	*max = (cprop->metaflag & CPROP_META_MAX) ? (int)cprop->max : INT_MAX;
	*softmin = *min;
	*softmax = *max;
}

static void rna_ComponentFloatProperty_range(PointerRNA *ptr, float *min, float *max, float *softmin, float *softmax)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;

	*min = (cprop->metaflag & CPROP_META_MIN) ? cprop->min : -FLT_MAX;
	*max = (cprop->metaflag & CPROP_META_MAX) ? cprop->max : FLT_MAX;
	*softmin = *min;
	*softmax = *max;
}

static bool rna_PythonComponentProperty_use_slider_get(PointerRNA *ptr)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;
	return (cprop->metaflag & (CPROP_META_MIN | CPROP_META_MAX)) == (CPROP_META_MIN | CPROP_META_MAX);
}

/* The object is kept by name (like the Track To actuator target in the game), so the
 * file stays readable by Range upstream and the runtime finds it in the scene. */
static PointerRNA rna_ComponentObjectProperty_value_get(PointerRNA *ptr)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;
	Object *ob = NULL;

	if (cprop->strval[0] && G_MAIN) {
		ob = BLI_findstring(&G_MAIN->object, cprop->strval, offsetof(ID, name) + 2);
	}

	return rna_pointer_inherit_refine(ptr, &RNA_Object, ob);
}

static void rna_ComponentObjectProperty_value_set(PointerRNA *ptr, PointerRNA value)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;
	Object *ob = (Object *)value.data;

	BLI_strncpy(cprop->strval, ob ? ob->id.name + 2 : "", sizeof(cprop->strval));
}

/* Scene kept by name too: in the game it is what logic.addScene() takes. */
static PointerRNA rna_ComponentSceneProperty_value_get(PointerRNA *ptr)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;
	Scene *scene = NULL;

	if (cprop->strval[0] && G_MAIN) {
		scene = BLI_findstring(&G_MAIN->scene, cprop->strval, offsetof(ID, name) + 2);
	}

	return rna_pointer_inherit_refine(ptr, &RNA_Scene, scene);
}

static void rna_ComponentSceneProperty_value_set(PointerRNA *ptr, PointerRNA value)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)ptr->data;
	Scene *scene = (Scene *)value.data;

	BLI_strncpy(cprop->strval, scene ? scene->id.name + 2 : "", sizeof(cprop->strval));
}

static int rna_ComponentSetProperty_get(struct PointerRNA *ptr)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)(ptr->data);
	return cprop->itemval;
}

static void rna_ComponentSetProperty_set(struct PointerRNA *ptr, int value)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)(ptr->data);
	cprop->itemval = value;
}

static const EnumPropertyItem *rna_ComponentSetProperty_itemf(bContext *UNUSED(C), PointerRNA *ptr, PropertyRNA *UNUSED(prop), bool *r_free)
{
	PythonComponentProperty *cprop = (PythonComponentProperty *)(ptr->data);
	EnumPropertyItem *items = NULL;
	int totitem = 0;
	int j = 0;

	for (LinkData *link = cprop->enumval.first; link; link = link->next, ++j) {
		EnumPropertyItem item = {0, "", 0, "", ""};
		item.value = j;
		item.identifier = link->data;
		item.icon = 0;
		item.name = link->data;
		item.description = "";
		RNA_enum_item_add(&items, &totitem, &item);
	}

	RNA_enum_item_end(&items, &totitem);
	*r_free = true;

	return items;
}
#else

static void rna_def_py_component(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	/* Python Component */
	srna = RNA_def_struct(brna, "PythonComponent", NULL);
	RNA_def_struct_sdna(srna, "PythonComponent");
	RNA_def_struct_ui_text(srna, "Python Component", "");

	prop = RNA_def_property(srna, "name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "name");
	RNA_def_property_ui_text(prop, "Name", "");
	RNA_def_struct_name_property(srna, prop);
	RNA_def_property_clear_flag(prop, PROP_EDITABLE);
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "module", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "module");
	RNA_def_property_ui_text(prop, "Module", "");
	RNA_def_struct_name_property(srna, prop);
	RNA_def_property_clear_flag(prop, PROP_EDITABLE);
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "show_expanded", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", COMPONENT_SHOW);
	RNA_def_property_ui_text(prop, "Expanded", "Set sensor expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_TRIA_RIGHT, 1);
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "toggle_execution", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag_toggle_exec", COMPONENT_SHOW);
	RNA_def_property_ui_text(prop, "Toggle Active", "Enable/Disable component execution in the user interface");
	RNA_def_property_ui_icon(prop, ICON_CHECKBOX_DEHLT, 1);
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "properties", PROP_COLLECTION, PROP_NONE);
	RNA_def_property_collection_sdna(prop, NULL, "properties", NULL);
	RNA_def_property_struct_type(prop, "PythonComponentProperty");
	RNA_def_property_ui_text(prop, "Properties", "Component properties");
}

static void rna_def_py_component_property(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static EnumPropertyItem empty_items[] = {
		{0, "EMPTY", 0, "Empty", ""},
		{0, NULL, 0, NULL, NULL}
	};

	/* Base Python Component Property */
	srna = RNA_def_struct(brna, "PythonComponentProperty", NULL);
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Property", "A property of a Python Component");
	RNA_def_struct_refine_func(srna, "rna_PythonComponentProperty_refine");

	prop = RNA_def_property(srna, "name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "name");
	RNA_def_property_ui_text(prop, "Name", "");
	RNA_def_struct_name_property(srna, prop);
	RNA_def_property_clear_flag(prop, PROP_EDITABLE);
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "description", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "tip");
	RNA_def_property_ui_text(prop, "Description", "Tooltip declared in the component args (tip=...)");
	RNA_def_property_clear_flag(prop, PROP_EDITABLE);

	prop = RNA_def_property(srna, "use_slider", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_funcs(prop, "rna_PythonComponentProperty_use_slider_get", NULL);
	RNA_def_property_ui_text(prop, "Use Slider", "The component args declare both min and max for this value");
	RNA_def_property_clear_flag(prop, PROP_EDITABLE);

	/* Boolean */
	srna = RNA_def_struct(brna, "ComponentBooleanProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Boolean Property", "A boolean property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "boolval", 1);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Int */
	srna = RNA_def_struct(brna, "ComponentIntProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Integer Property", "An integer property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "intval");
	RNA_def_property_int_funcs(prop, NULL, NULL, "rna_ComponentIntProperty_range");
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Float */
	srna = RNA_def_struct(brna, "ComponentFloatProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Float Property", "A float property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "floatval");
	RNA_def_property_float_funcs(prop, NULL, NULL, "rna_ComponentFloatProperty_range");
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* String */
	srna = RNA_def_struct(brna, "ComponentStringProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component String Property", "A string property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "strval");
	RNA_def_property_string_maxlength(prop, MAX_PROPSTRING);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Set */
	srna = RNA_def_struct(brna, "ComponentSetProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Set Property", "A set property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, empty_items);
	RNA_def_property_enum_funcs(prop, "rna_ComponentSetProperty_get", "rna_ComponentSetProperty_set", "rna_ComponentSetProperty_itemf");
	RNA_def_property_enum_default(prop, 0);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Vector 2D */
	srna = RNA_def_struct(brna, "ComponentVector2DProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Vector 2D Property", "A 2D vector property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_FLOAT, PROP_COORDS);
	RNA_def_property_float_sdna(prop, NULL, "vec");
	RNA_def_property_array(prop, 2);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Vector 3D */
	srna = RNA_def_struct(brna, "ComponentVector3DProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Vector 3D Property", "A 3D vector property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_FLOAT, PROP_COORDS);
	RNA_def_property_float_sdna(prop, NULL, "vec");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Vector 4D */
	srna = RNA_def_struct(brna, "ComponentVector4DProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Vector 4D Property", "A 4D vector property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_FLOAT, PROP_COORDS);
	RNA_def_property_float_sdna(prop, NULL, "vec");
	RNA_def_property_array(prop, 4);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Color 3 */
	srna = RNA_def_struct(brna, "ComponentColor3Property", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Color 3 Property", "A 3 channels color property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "vec");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Color 4 */
	srna = RNA_def_struct(brna, "ComponentColor4Property", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Color 4 Property", "A 4 channels color property of a Python Component");

	prop = RNA_def_property(srna, "value", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "vec");
	RNA_def_property_array(prop, 4);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Object */
	srna = RNA_def_struct(brna, "ComponentObjectProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Object Property", "An object picked in the editor (arrives as KX_GameObject in the game)");

	prop = RNA_def_property(srna, "value", PROP_POINTER, PROP_NONE);
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_pointer_funcs(prop, "rna_ComponentObjectProperty_value_get", "rna_ComponentObjectProperty_value_set", NULL, NULL);
	RNA_def_property_flag(prop, PROP_EDITABLE);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "object_name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "strval");
	RNA_def_property_string_maxlength(prop, MAX_PROPSTRING);
	RNA_def_property_ui_text(prop, "Object Name", "Name of the picked object (the game looks it up by this name)");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	/* Scene */
	srna = RNA_def_struct(brna, "ComponentSceneProperty", "PythonComponentProperty");
	RNA_def_struct_sdna(srna, "PythonComponentProperty");
	RNA_def_struct_ui_text(srna, "Python Component Scene Property", "A scene picked in the editor (arrives as the scene name in the game)");

	prop = RNA_def_property(srna, "value", PROP_POINTER, PROP_NONE);
	RNA_def_property_struct_type(prop, "Scene");
	RNA_def_property_pointer_funcs(prop, "rna_ComponentSceneProperty_value_get", "rna_ComponentSceneProperty_value_set", NULL, NULL);
	RNA_def_property_flag(prop, PROP_EDITABLE);
	RNA_def_property_ui_text(prop, "Value", "Property value");
	RNA_def_property_update(prop, NC_LOGIC, NULL);

	prop = RNA_def_property(srna, "scene_name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "strval");
	RNA_def_property_string_maxlength(prop, MAX_PROPSTRING);
	RNA_def_property_ui_text(prop, "Scene Name", "Name of the picked scene");
	RNA_def_property_update(prop, NC_LOGIC, NULL);
}

void RNA_def_py_component(BlenderRNA *brna)
{
	rna_def_py_component(brna);
	rna_def_py_component_property(brna);
}

#endif /* RNA_RUNTIME */
