/*
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
 */

/** \file blender/makesrna/intern/rna_camera.c
 *  \ingroup RNA
 */

#include <stdlib.h>

#include "DNA_camera_types.h"

#include "BLI_math.h"

#include "RNA_define.h"

#include "rna_internal.h"

#include "WM_types.h"

#ifdef RNA_RUNTIME

#include "BKE_camera.h"
#include "BKE_depsgraph.h"
#include "BKE_object.h"
#include "BKE_sequencer.h"

#include "WM_api.h"

static float rna_Camera_draw_size_get(PointerRNA *ptr)
{
	Camera *cam = ptr->id.data;
	return cam->drawsize * 2.0f;
}

static void rna_Camera_draw_size_set(PointerRNA *ptr, float value)
{
	Camera *cam = ptr->id.data;
	cam->drawsize = value / 2.0f;
}

static float rna_Camera_angle_get(PointerRNA *ptr)
{
	Camera *cam = ptr->id.data;
	float sensor = BKE_camera_sensor_size(cam->sensor_fit, cam->sensor_x, cam->sensor_y);
	return focallength_to_fov(cam->lens, sensor);
}

static void rna_Camera_angle_set(PointerRNA *ptr, float value)
{
	Camera *cam = ptr->id.data;
	float sensor = BKE_camera_sensor_size(cam->sensor_fit, cam->sensor_x, cam->sensor_y);
	cam->lens = fov_to_focallength(value, sensor);
}

static float rna_Camera_angle_x_get(PointerRNA *ptr)
{
	Camera *cam = ptr->id.data;
	return focallength_to_fov(cam->lens, cam->sensor_x);
}

static void rna_Camera_angle_x_set(PointerRNA *ptr, float value)
{
	Camera *cam = ptr->id.data;
	cam->lens = fov_to_focallength(value, cam->sensor_x);
}

static float rna_Camera_angle_y_get(PointerRNA *ptr)
{
	Camera *cam = ptr->id.data;
	return focallength_to_fov(cam->lens, cam->sensor_y);
}

static void rna_Camera_angle_y_set(PointerRNA *ptr, float value)
{
	Camera *cam = ptr->id.data;
	cam->lens = fov_to_focallength(value, cam->sensor_y);
}

static void rna_Camera_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	Camera *camera = (Camera *)ptr->id.data;

	DAG_id_tag_update(&camera->id, 0);
}

static void rna_Camera_dependency_update(Main *bmain, Scene *UNUSED(scene), PointerRNA *ptr)
{
	Camera *camera = (Camera *)ptr->id.data;
	DAG_relations_tag_update(bmain);
	DAG_id_tag_update(&camera->id, 0);
}

static void rna_Camera_dof_update(Main *UNUSED(bmain), Scene *scene, PointerRNA *UNUSED(ptr))
{
	/* TODO(sergey): Can be more selective here. */
	BKE_sequencer_cache_cleanup();
	BKE_sequencer_preprocessed_cache_cleanup();
	WM_main_add_notifier(NC_SCENE | ND_SEQUENCER, scene);
}

#else

static void rna_def_camera_stereo_data(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem convergence_mode_items[] = {
		{CAM_S3D_OFFAXIS, "OFFAXIS", 0, "Off-Axis", "Off-axis frustums converging in a plane"},
		{CAM_S3D_PARALLEL, "PARALLEL", 0, "Parallel", "Parallel cameras with no convergence"},
		{CAM_S3D_TOE, "TOE", 0, "Toe-in", "Rotated cameras, looking at the convergence distance"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem pivot_items[] = {
		{CAM_S3D_PIVOT_LEFT, "LEFT", 0, "Left", ""},
		{CAM_S3D_PIVOT_RIGHT, "RIGHT", 0, "Right", ""},
		{CAM_S3D_PIVOT_CENTER, "CENTER", 0, "Center", ""},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "CameraStereoData", NULL);
	RNA_def_struct_sdna(srna, "CameraStereoSettings");
	RNA_def_struct_nested(brna, srna, "Camera");
	RNA_def_struct_ui_text(srna, "Stereo", "Stereoscopy settings for a Camera data-block");

	prop = RNA_def_property(srna, "convergence_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, convergence_mode_items);
	RNA_def_property_ui_text(prop, "Mode", "");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "pivot", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, pivot_items);
	RNA_def_property_ui_text(prop, "Pivot", "");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "interocular_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0f, 1e4f, 1, 3);
	RNA_def_property_ui_text(prop, "Interocular Distance",
	                         "Set the distance between the eyes - the stereo plane distance / 30 should be fine");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "convergence_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.00001f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.00001f, 15.f, 1, 3);
	RNA_def_property_ui_text(prop, "Convergence Plane Distance",
	                         "The converge point for the stereo cameras "
	                         "(often the distance between a projector and the projection screen)");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "use_spherical_stereo", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_S3D_SPHERICAL);
	RNA_def_property_ui_text(prop, "Spherical Stereo",
	                         "Render every pixel rotating the camera around the "
	                         "middle of the interocular distance");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "use_pole_merge", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_S3D_POLE_MERGE);
	RNA_def_property_ui_text(prop, "Use Pole Merge",
	                         "Fade interocular distance to 0 after the given cutoff angle");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "pole_merge_angle_from", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_range(prop, 0.0f, M_PI / 2.0);
	RNA_def_property_ui_text(prop, "Pole Merge Start Angle",
	                         "Angle at which interocular distance starts to fade to 0");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "pole_merge_angle_to", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_range(prop, 0.0f, M_PI / 2.0);
	RNA_def_property_ui_text(prop, "Pole Merge End Angle",
	                         "Angle at which interocular distance is 0");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);
}

static void rna_def_game_camera_viewport_data(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "GameCameraViewportData", NULL);
	RNA_def_struct_sdna(srna, "GameCameraViewportSettings");
	RNA_def_struct_nested(brna, srna, "Camera");
	RNA_def_struct_ui_text(srna, "Viewport", "Game custom camera viewport settings");

	prop = RNA_def_property(srna, "left_ratio", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "leftratio");
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Left Ratio", "Set camera viewport left to a ratio of the entire viewport width");

	prop = RNA_def_property(srna, "right_ratio", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "rightratio");
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_float_default(prop, 1.0f);
	RNA_def_property_ui_text(prop, "Right Ratio", "Set camera viewport right to a ratio of the entire viewport width");

	prop = RNA_def_property(srna, "bottom_ratio", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "bottomratio");
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Bottom Ratio", "Set camera viewport bottom to a ratio of the entire viewport height");

	prop = RNA_def_property(srna, "top_ratio", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "topratio");
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_float_default(prop, 1.0f);
	RNA_def_property_ui_text(prop, "Top Ratio", "Set camera viewport top to a ratio of the entire viewport height");
}

#define GFX_FLOAT(_id, _member, _min, _max, _smin, _smax, _name, _desc) \
	prop = RNA_def_property(srna, _id, PROP_FLOAT, PROP_NONE); \
	RNA_def_property_float_sdna(prop, NULL, _member); \
	RNA_def_property_range(prop, _min, _max); \
	RNA_def_property_ui_range(prop, _smin, _smax, 1, 3); \
	RNA_def_property_ui_text(prop, _name, _desc); \
	RNA_def_property_update(prop, NC_CAMERA, NULL)

#define GFX_FLAG(_id, _flag, _name, _desc) \
	prop = RNA_def_property(srna, _id, PROP_BOOLEAN, PROP_NONE); \
	RNA_def_property_boolean_sdna(prop, NULL, "flag", _flag); \
	RNA_def_property_ui_text(prop, _name, _desc); \
	RNA_def_property_update(prop, NC_CAMERA, NULL)

static void rna_def_camera_game_fx(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem focus_mode_items[] = {
		{CAM_FOCUS_MANUAL, "MANUAL", 0, "Manual", "Focus at a fixed distance"},
		{CAM_FOCUS_OBJECT, "OBJECT", 0, "Object", "Focus on the DOF Object"},
		{CAM_FOCUS_PROPERTY, "PROPERTY", 0, "Property",
		 "Focus on the nearest object whose property is true (or non-zero)"},
		{CAM_FOCUS_AUTO, "AUTO", 0, "Auto", "Focus on whatever is under the aim point of the screen"},
		{0, NULL, 0, NULL, NULL}
	};
	static const EnumPropertyItem track_mode_items[] = {
		{CAM_TRACK_OFF, "OFF", 0, "Off", "The camera does not turn by itself"},
		{CAM_TRACK_LOOK_AT, "LOOK_AT", 0, "Look At", "The camera turns on its own axis to follow the focus"},
		{CAM_TRACK_DRONE, "DRONE", 0, "Drone", "Look At with smooth target changes, hover and banking"},
		{0, NULL, 0, NULL, NULL}
	};
	static const EnumPropertyItem dof_quality_items[] = {
		{0, "LOW", 0, "Low", "Fewer samples, fastest"},
		{1, "MEDIUM", 0, "Medium", ""},
		{2, "HIGH", 0, "High", "More samples, smoother bokeh"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "CameraGameFXData", NULL);
	RNA_def_struct_sdna(srna, "CameraGameFX");
	RNA_def_struct_nested(brna, srna, "Camera");
	RNA_def_struct_ui_text(srna, "Camera Game FX", "Game engine focus, tracking, effects and shake");

	/* Focus */
	prop = RNA_def_property(srna, "focus_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "focus_mode");
	RNA_def_property_enum_items(prop, focus_mode_items);
	RNA_def_property_ui_text(prop, "Focus", "How the camera finds its focus");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	prop = RNA_def_property(srna, "focus_property", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "focus_prop");
	RNA_def_property_ui_text(prop, "Focus Property", "Game property that marks the focus target when true");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	GFX_FLOAT("focus_smooth", "focus_smooth", 0.0f, 10.0f, 0.0f, 2.0f, "Focus Smooth",
	          "Seconds the focus takes to reach a new distance");
	GFX_FLOAT("focus_range", "focus_range", 0.0f, 10000.0f, 0.0f, 50.0f, "Focus Range",
	          "Depth around the focus distance that stays sharp, in meters");

	prop = RNA_def_property(srna, "focus_screen", PROP_FLOAT, PROP_XYZ);
	RNA_def_property_float_sdna(prop, NULL, "focus_screen");
	RNA_def_property_array(prop, 2);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Aim Point", "Screen point (0..1, top-down) used by Auto focus");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	/* Tracking */
	prop = RNA_def_property(srna, "track_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "track_mode");
	RNA_def_property_enum_items(prop, track_mode_items);
	RNA_def_property_ui_text(prop, "Tracking", "Turn the camera on its own axis to follow the focus");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	GFX_FLOAT("track_speed", "track_speed", 0.0f, 10.0f, 0.0f, 2.0f, "Track Smooth",
	          "Seconds the camera takes to turn toward the focus (0 = instant)");
	prop = RNA_def_property(srna, "track_limit", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_float_sdna(prop, NULL, "track_limit");
	RNA_def_property_range(prop, 0.0f, M_PI);
	RNA_def_property_ui_text(prop, "Angle Limit", "Max turn away from the base orientation (0 = no limit)");
	RNA_def_property_update(prop, NC_CAMERA, NULL);
	GFX_FLOAT("track_deadzone", "track_deadzone", 0.0f, 0.5f, 0.0f, 0.5f, "Dead Zone",
	          "Screen fraction around the aim point where the camera does not turn");

	prop = RNA_def_property(srna, "track_screen_offset", PROP_FLOAT, PROP_XYZ);
	RNA_def_property_float_sdna(prop, NULL, "track_screen_offset");
	RNA_def_property_array(prop, 2);
	RNA_def_property_range(prop, -0.5f, 0.5f);
	RNA_def_property_ui_text(prop, "Framing Offset", "Where the target sits on screen (0,0 = center)");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	GFX_FLAG("use_track_up_lock", CAM_GFX_TRACK_UPLOCK, "Keep Horizon", "Never roll while tracking");
	GFX_FLOAT("drone_amplitude", "drone_amplitude", 0.0f, 20.0f, 0.0f, 5.0f, "Hover Amplitude",
	          "Drone hover strength (1 = the Rolima Racer drone)");
	GFX_FLOAT("drone_frequency", "drone_frequency", 0.0f, 20.0f, 0.0f, 5.0f, "Hover Speed", "Drone hover speed");
	GFX_FLOAT("track_bank", "track_bank", 0.0f, 5.0f, 0.0f, 2.0f, "Bank", "Drone roll into the turn");

	/* Effects */
	GFX_FLAG("use_dof", CAM_GFX_DOF, "Depth of Field", "Bokeh blur outside the focus range");
	prop = RNA_def_property(srna, "dof_quality", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "dof_quality");
	RNA_def_property_enum_items(prop, dof_quality_items);
	RNA_def_property_ui_text(prop, "Quality", "Bokeh sample count");
	RNA_def_property_update(prop, NC_CAMERA, NULL);
	GFX_FLOAT("dof_blur", "dof_blur", 0.0f, 32.0f, 0.0f, 16.0f, "Blur Size", "Max bokeh radius in pixels");

	GFX_FLAG("use_speed_blur", CAM_GFX_SPEEDBLUR, "Speed Blur", "Radial blur centered on the focus, grows with speed");
	GFX_FLOAT("speed_blur_strength", "speedblur_strength", 0.0f, 2.0f, 0.0f, 1.0f, "Strength", "");
	GFX_FLOAT("speed_blur_max_speed", "speedblur_max_speed", 0.1f, 1000.0f, 1.0f, 200.0f, "Full Speed",
	          "Camera speed (m/s) that gives the full blur");

	GFX_FLAG("use_directional_blur", CAM_GFX_DIRBLUR, "Directional Blur", "Blur along the camera turn");
	GFX_FLOAT("directional_blur_strength", "dirblur_strength", 0.0f, 2.0f, 0.0f, 1.0f, "Strength", "");
	GFX_FLOAT("directional_blur_max", "dirblur_max", 0.0f, 0.2f, 0.0f, 0.1f, "Max", "Max blur length (screen fraction)");

	GFX_FLAG("use_blur_protect", CAM_GFX_BLUR_PROTECT, "Protect Focus",
	         "Keep the focus range sharp under Speed and Directional Blur");

	GFX_FLAG("use_cat_eye", CAM_GFX_CATEYE_BOKEH, "Cat Eye Bokeh", "Bokeh squeezes toward the frame edges");
	GFX_FLOAT("cat_eye_strength", "cateye_strength", 0.0f, 1.0f, 0.0f, 1.0f, "Cat Eye", "");
	GFX_FLAG("use_chromatic", CAM_GFX_CHROMA, "Chromatic Aberration", "Color fringes toward the frame edges");
	GFX_FLOAT("chromatic_strength", "chroma_strength", 0.0f, 5.0f, 0.0f, 2.0f, "Strength", "");
	GFX_FLAG("use_chromatic_speed", CAM_GFX_CHROMA_SPEED, "Grow With Speed", "Stronger aberration at speed");
	GFX_FLAG("use_vignette", CAM_GFX_VIGNETTE, "Vignette / Fisheye", "Darkened corners and barrel lens");
	GFX_FLOAT("vignette_strength", "vignette_strength", 0.0f, 1.0f, 0.0f, 1.0f, "Vignette", "");
	GFX_FLOAT("vignette_radius", "vignette_radius", 0.0f, 2.0f, 0.0f, 1.5f, "Radius", "");
	GFX_FLOAT("fisheye_strength", "fisheye_strength", -1.0f, 1.0f, -0.5f, 0.5f, "Fisheye",
	          "Barrel (positive) or pincushion (negative) distortion");
	GFX_FLAG("use_grain", CAM_GFX_GRAIN, "Film Grain", "Animated noise, stronger on the mid tones");
	GFX_FLOAT("grain_strength", "grain_strength", 0.0f, 1.0f, 0.0f, 0.2f, "Grain", "");

	/* Shake */
	GFX_FLOAT("shake_amplitude", "shake_amplitude", 0.0f, 0.5f, 0.0f, 0.1f, "Shake Amplitude",
	          "Max lens shift of cam.shake() at full trauma");
	GFX_FLOAT("shake_frequency", "shake_frequency", 0.0f, 60.0f, 0.0f, 30.0f, "Shake Frequency", "");
	GFX_FLOAT("shake_decay", "shake_decay", 0.0f, 20.0f, 0.0f, 5.0f, "Shake Decay", "Trauma lost per second");
	GFX_FLAG("use_shake_roll", CAM_GFX_SHAKE_ROLL, "Shake Roll", "Also roll the camera a little while shaking");
}

#undef GFX_FLOAT
#undef GFX_FLAG

void RNA_def_camera(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;
	static const EnumPropertyItem prop_type_items[] = {
		{CAM_PERSP, "PERSP", 0, "Perspective", ""},
		{CAM_ORTHO, "ORTHO", 0, "Orthographic", ""},
		{CAM_PANO, "PANO", 0, "Panoramic", ""},
		{0, NULL, 0, NULL, NULL}
	};
	static const EnumPropertyItem prop_draw_type_extra_items[] = {
		{CAM_DTX_CENTER, "CENTER", 0, "Center", ""},
		{CAM_DTX_CENTER_DIAG, "CENTER_DIAGONAL", 0, "Center Diagonal", ""},
		{CAM_DTX_THIRDS, "THIRDS", 0, "Thirds", ""},
		{CAM_DTX_GOLDEN, "GOLDEN", 0, "Golden", ""},
		{CAM_DTX_GOLDEN_TRI_A, "GOLDEN_TRIANGLE_A", 0, "Golden Triangle A", ""},
		{CAM_DTX_GOLDEN_TRI_B, "GOLDEN_TRIANGLE_B", 0, "Golden Triangle B", ""},
		{CAM_DTX_HARMONY_TRI_A, "HARMONY_TRIANGLE_A", 0, "Harmonious Triangle A", ""},
		{CAM_DTX_HARMONY_TRI_B, "HARMONY_TRIANGLE_B", 0, "Harmonious Triangle B", ""},
		{0, NULL, 0, NULL, NULL}
	};
	static const EnumPropertyItem prop_lens_unit_items[] = {
		{0, "MILLIMETERS", 0, "Millimeters", "Specify the lens in millimeters"},
		{CAM_ANGLETOGGLE, "FOV", 0, "Field of View", "Specify the lens as the field of view's angle"},
		{0, NULL, 0, NULL, NULL}
	};
	static const EnumPropertyItem sensor_fit_items[] = {
		{CAMERA_SENSOR_FIT_AUTO, "AUTO", 0, "Auto", "Fit to the sensor width or height depending on image resolution"},
		{CAMERA_SENSOR_FIT_HOR, "HORIZONTAL", 0, "Horizontal", "Fit to the sensor width"},
		{CAMERA_SENSOR_FIT_VERT, "VERTICAL", 0, "Vertical", "Fit to the sensor height"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "Camera", "ID");
	RNA_def_struct_ui_text(srna, "Camera", "Camera data-block for storing camera settings");
	RNA_def_struct_ui_icon(srna, ICON_CAMERA_DATA);

	/* Enums */
	prop = RNA_def_property(srna, "type", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, prop_type_items);
	RNA_def_property_ui_text(prop, "Type", "Camera types");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "show_guide", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "dtx");
	RNA_def_property_enum_items(prop, prop_draw_type_extra_items);
	RNA_def_property_flag(prop, PROP_ENUM_FLAG);
	RNA_def_property_ui_text(prop, "Composition Guides",  "Draw overlay");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "sensor_fit", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "sensor_fit");
	RNA_def_property_enum_items(prop, sensor_fit_items);
	RNA_def_property_ui_text(prop, "Sensor Fit", "Method to fit image and field of view angle inside the sensor");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	/* Number values */

	prop = RNA_def_property(srna, "passepartout_alpha", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "passepartalpha");
	RNA_def_property_ui_text(prop, "Passepartout Alpha", "Opacity (alpha) of the darkened overlay in Camera view");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "angle_x", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_range(prop, DEG2RAD(0.367), DEG2RAD(172.847));
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Horizontal FOV", "Camera lens horizontal field of view");
	RNA_def_property_float_funcs(prop, "rna_Camera_angle_x_get", "rna_Camera_angle_x_set", NULL);
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "angle_y", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_range(prop, DEG2RAD(0.367), DEG2RAD(172.847));
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Vertical FOV", "Camera lens vertical field of view");
	RNA_def_property_float_funcs(prop, "rna_Camera_angle_y_get", "rna_Camera_angle_y_set", NULL);
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "angle", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_range(prop, DEG2RAD(0.367), DEG2RAD(172.847));
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Field of View", "Camera lens field of view");
	RNA_def_property_float_funcs(prop, "rna_Camera_angle_get", "rna_Camera_angle_set", NULL);
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "clip_start", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "clipsta");
	RNA_def_property_range(prop, 1e-6f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.001f, FLT_MAX, 10, 3);
	RNA_def_property_ui_text(prop, "Clip Start", "Camera near clipping distance");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "clip_end", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "clipend");
	RNA_def_property_range(prop, 1e-6f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.001f, FLT_MAX, 10, 3);
	RNA_def_property_ui_text(prop, "Clip End", "Camera far clipping distance");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "lens", PROP_FLOAT, PROP_DISTANCE_CAMERA);
	RNA_def_property_float_sdna(prop, NULL, "lens");
	RNA_def_property_range(prop, 1.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 1.0f, 5000.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Focal Length", "Perspective Camera lens value in millimeters");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "sensor_width", PROP_FLOAT, PROP_DISTANCE_CAMERA);
	RNA_def_property_float_sdna(prop, NULL, "sensor_x");
	RNA_def_property_range(prop, 1.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 1.0f, 100.f, 1, 2);
	RNA_def_property_ui_text(prop, "Sensor Width", "Horizontal size of the image sensor area in millimeters");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "sensor_height", PROP_FLOAT, PROP_DISTANCE_CAMERA);
	RNA_def_property_float_sdna(prop, NULL, "sensor_y");
	RNA_def_property_range(prop, 1.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 1.0f, 100.f, 1, 2);
	RNA_def_property_ui_text(prop, "Sensor Height", "Vertical size of the image sensor area in millimeters");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "ortho_scale", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "ortho_scale");
	RNA_def_property_range(prop, FLT_MIN, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.001f, 10000.0f, 10, 3);
	RNA_def_property_ui_text(prop, "Orthographic Scale", "Orthographic Camera scale (similar to zoom)");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "draw_size", PROP_FLOAT, PROP_DISTANCE);
#if 0
	RNA_def_property_float_sdna(prop, NULL, "drawsize");
#else
	RNA_def_property_float_funcs(prop, "rna_Camera_draw_size_get", "rna_Camera_draw_size_set", NULL);
#endif
	RNA_def_property_range(prop, 0.01f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.01, 100, 1, 2);
	RNA_def_property_ui_text(prop, "Draw Size", "Apparent size of the Camera object in the 3D View");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "shift_x", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "shiftx");
	RNA_def_property_range(prop, -10.0f, 10.0f);
	RNA_def_property_ui_range(prop, -2.0, 2.0, 1, 3);
	RNA_def_property_ui_text(prop, "Shift X", "Camera horizontal shift");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "shift_y", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "shifty");
	RNA_def_property_range(prop, -10.0f, 10.0f);
	RNA_def_property_ui_range(prop, -2.0, 2.0, 1, 3);
	RNA_def_property_ui_text(prop, "Shift Y", "Camera vertical shift");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_update");

	prop = RNA_def_property(srna, "dof_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "YF_dofdist");
	RNA_def_property_range(prop, 0.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0f, 5000.0f, 1, 2);
	RNA_def_property_ui_text(prop, "DOF Distance", "Distance to the focus point for depth of field");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_dof_update");

	prop = RNA_def_property(srna, "lod_factor", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "lodfactor");
	RNA_def_property_range(prop, 0.0f, FLT_MAX);
	RNA_def_property_float_default(prop, 1.0f);
	RNA_def_property_ui_text(prop, "Level of Detail Distance Factor", "The factor applied to distance computed in Lod");
	RNA_def_property_update(prop, NC_OBJECT | ND_LOD, NULL);

	prop = RNA_def_property(srna, "csm_cache_max_stale_frames", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "csmCacheMaxStaleFrames");
	RNA_def_property_range(prop, 0, 2);
	RNA_def_property_int_default(prop, 1);
	RNA_def_property_ui_text(prop, "Shadow Cascade Cache Tolerance",
	                          "Reuse this frame's shadow cascade matrices instead of recomputing them: "
	                          "Off always recomputes, Exact only reuses them while this camera hasn't moved "
	                          "at all, Tolerant also allows one frame of small movement before recomputing");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	/* Stereo Settings */
	prop = RNA_def_property(srna, "stereo", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_pointer_sdna(prop, NULL, "stereo");
	RNA_def_property_struct_type(prop, "CameraStereoData");
	RNA_def_property_ui_text(prop, "Stereo", "");

	/* Stereo Settings */
	prop = RNA_def_property(srna, "viewport", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_pointer_sdna(prop, NULL, "gameviewport");
	RNA_def_property_struct_type(prop, "GameCameraViewportData");

	prop = RNA_def_property(srna, "game_fx", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_pointer_sdna(prop, NULL, "gamefx");
	RNA_def_property_struct_type(prop, "CameraGameFXData");
	RNA_def_property_ui_text(prop, "Game FX", "Game engine focus, tracking, effects and shake");

	/* flag */
	prop = RNA_def_property(srna, "override_culling", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "gameflag", GAME_CAM_OVERRIDE_CULLING);
	RNA_def_property_ui_text(prop, "Override Culling", "Use only this camera for scene culling in Game Engine");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	prop = RNA_def_property(srna, "show_frustum", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "gameflag", GAME_CAM_SHOW_FRUSTUM);
	RNA_def_property_ui_text(prop, "Show Frustum", "Show a visualization of frustum in Game Engine");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	prop = RNA_def_property(srna, "show_culling_box", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "gameflag", GAME_CAM_SHOW_CULLING_BOX);
	RNA_def_property_ui_text(prop, "Show Culling Box", "Draw the camera culling volume in the 3D view");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "use_viewport", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "gameflag", GAME_CAM_VIEWPORT);
	RNA_def_property_ui_text(prop, "Use Custom Viewport",
	                         "Render this camera into its own region of the window, even when it is not the active camera");
	RNA_def_property_update(prop, NC_CAMERA, NULL);

	prop = RNA_def_property(srna, "use_object_activity_culling", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "gameflag", GAME_CAM_OBJECT_ACTIVITY_CULLING);
	RNA_def_property_ui_text(prop, "Activity Culling", "Enable object activity culling with this camera");

	prop = RNA_def_property(srna, "show_limits", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOWLIMITS);
	RNA_def_property_ui_text(prop, "Show Limits", "Draw the clipping range and focus point on the camera");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "show_mist", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOWMIST);
	RNA_def_property_ui_text(prop, "Show Mist", "Draw a line from the Camera to indicate the mist area");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "show_passepartout", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOWPASSEPARTOUT);
	RNA_def_property_ui_text(prop, "Show Passepartout",
	                         "Show a darkened overlay outside the image area in Camera view");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "show_safe_areas", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOW_SAFE_MARGINS);
	RNA_def_property_ui_text(prop, "Show Safe Areas", "Show TV title safe and action safe areas in Camera view");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "show_safe_center", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOW_SAFE_CENTER);
	RNA_def_property_ui_text(prop, "Show Center-cut safe areas",
	                         "Show safe areas to fit content in a different aspect ratio");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "show_name", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOWNAME);
	RNA_def_property_ui_text(prop, "Show Name", "Show the active Camera's name in Camera view");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "show_sensor", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", CAM_SHOWSENSOR);
	RNA_def_property_ui_text(prop, "Show Sensor Size", "Show sensor size (film gate) in Camera view");
	RNA_def_property_update(prop, NC_CAMERA | ND_DRAW_RENDER_VIEWPORT, NULL);

	prop = RNA_def_property(srna, "lens_unit", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_bitflag_sdna(prop, NULL, "flag");
	RNA_def_property_enum_items(prop, prop_lens_unit_items);
	RNA_def_property_ui_text(prop, "Lens Unit", "Unit to edit lens in for the user interface");

	/* pointers */
	prop = RNA_def_property(srna, "dof_object", PROP_POINTER, PROP_NONE);
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_pointer_sdna(prop, NULL, "dof_ob");
	RNA_def_property_flag(prop, PROP_EDITABLE);
	RNA_def_property_ui_text(prop, "DOF Object", "Use this object to define the depth of field focal point");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Camera_dependency_update");

	prop = RNA_def_property(srna, "gpu_dof", PROP_POINTER, PROP_NONE);
	RNA_def_property_struct_type(prop, "GPUDOFSettings");
	RNA_def_property_ui_text(prop, "GPU Depth Of Field", "");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	rna_def_animdata_common(srna);

	/* Nested Data  */
	RNA_define_animate_sdna(true);

	/* *** Animated *** */
	rna_def_camera_stereo_data(brna);

	/* Game Data */
	rna_def_game_camera_viewport_data(brna);
	rna_def_camera_game_fx(brna);

	/* Camera API */
	RNA_api_camera(srna);
}

#endif
