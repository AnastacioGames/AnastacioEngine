/*
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
 * Contributor(s): Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Launcher/LA_BlenderLauncher.cpp
 *  \ingroup launcher
 */

#include "LA_BlenderLauncher.h"

#include "KX_BlenderCanvas.h"

#include "KX_PythonInit.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"
#include "KX_GameObject.h"
#include "DEV_EventConsumer.h"
#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IVehicle.h"
#include "KX_PythonComponent.h"

#include "EXP_BoolValue.h"
#include "EXP_IntValue.h"
#include "EXP_FloatValue.h"
#include "EXP_StringValue.h"

#include <cstring>

extern "C" {
#  include "BKE_context.h"
#  include "BKE_camera.h"
#  include "BKE_main.h"

// avoid c++ conflict with 'new'
#  define new _new
#  include "BKE_screen.h"
#  undef new

#  include "DNA_scene_types.h"
#  include "DNA_screen_types.h"
#  include "DNA_object_types.h"
#  include "DNA_view3d_types.h"
#  include "DNA_property_types.h"
#  include "DNA_python_component_types.h"

#  include "WM_types.h"
#  include "WM_api.h"
#  include "wm_event_system.h"
#  include "wm_window.h"

#  include "BLI_rect.h"
#  include "BLI_listbase.h"
}

LA_BlenderLauncher::LA_BlenderLauncher(GHOST_ISystem *system, Main *maggie, Scene *scene, GlobalSettings *gs, RAS_Rasterizer::StereoMode stereoMode,
                                       int argc, char **argv, bContext *context, rcti *camframe, ARegion *ar, int alwaysUseExpandFraming)
	:LA_Launcher(system, maggie, scene, gs, stereoMode, scene->gm.aasamples, alwaysUseExpandFraming, argc, argv),
	m_context(context),
	m_ar(ar),
	m_camFrame(camframe),
	m_drawLetterBox(false),
	m_liveUI(false)
{
	m_windowManager = CTX_wm_manager(m_context);
	m_window = CTX_wm_window(m_context);
	m_view3d = CTX_wm_view3d(m_context);

	m_areaRect.SetLeft(m_camFrame->xmin);
	m_areaRect.SetBottom(m_camFrame->ymin);
	m_areaRect.SetRight(m_camFrame->xmax);
	m_areaRect.SetTop(m_camFrame->ymax);
}

LA_BlenderLauncher::~LA_BlenderLauncher()
{
}

RAS_ICanvas *LA_BlenderLauncher::CreateCanvas(RAS_Rasterizer *rasty, const RAS_OffScreen::AttachmentList& attachments, int numSamples)
{
	return (new KX_BlenderCanvas(rasty, attachments, m_windowManager, m_window, m_areaRect, numSamples));
}

RAS_Rasterizer::DrawType LA_BlenderLauncher::GetRasterizerDrawMode()
{
	View3D *v3d = CTX_wm_view3d(m_context);

	RAS_Rasterizer::DrawType drawmode = RAS_Rasterizer::RAS_TEXTURED;
	switch (v3d->drawtype) {
		case OB_BOUNDBOX:
		case OB_WIRE:
		{
			drawmode = RAS_Rasterizer::RAS_WIREFRAME;
			break;
		}
		case OB_MATERIAL:
		{
			drawmode = RAS_Rasterizer::RAS_TEXTURED;
			break;
		}
	}
	return drawmode;
}

void LA_BlenderLauncher::InitCamera()
{
	RegionView3D *rv3d = CTX_wm_region_view3d(m_context);
	if (rv3d->persp == RV3D_CAMOB) {
		if (m_startScene->gm.framing.type == SCE_GAMEFRAMING_BARS) { /* Letterbox */
			m_drawLetterBox = true;
		}
		else {
			m_camZoom = 1.0f / BKE_screen_view3d_zoom_to_fac(rv3d->camzoom);
		}
	}

	if (rv3d->persp != RV3D_CAMOB) {
		CameraParams params;
		BKE_camera_params_init(&params);
		BKE_camera_params_from_view3d(&params, m_view3d, rv3d);

		RAS_CameraData camdata = RAS_CameraData(params.lens, params.ortho_scale, params.sensor_x, params.sensor_y,
				params.sensor_fit, params.shiftx, params.shifty, params.clipsta, params.clipend, !params.is_ortho,
				3.0f, params.zoom);

		const mt::mat4 viewinv(rv3d->viewinv);

		m_ketsjiEngine->EnableCameraOverride(m_startSceneName, viewinv.RotationMatrix(), viewinv.TranslationVector3D(), camdata);
	}
}

void LA_BlenderLauncher::SetWindowOrder(short order)
{
	wm_window_set_order(m_window, order);
}

void LA_BlenderLauncher::InitEngine()
{
	// Lock frame and camera enabled - storing global values.
	m_savedBlenderData.sceneLayer = m_startScene->lay;
	m_savedBlenderData.camera = m_startScene->camera;

	if (m_view3d->scenelock == 0) {
		m_startScene->lay = m_view3d->lay;
		m_startScene->camera = m_view3d->camera;
	}

	LA_Launcher::InitEngine();

	// Outro .blend carregado pelo jogo (Game Actuator) não é o que o editor mostra: sem UI ao vivo.
	m_liveUI = (m_startScene->gm.flag & GAME_LIVE_UI) && (m_maggie == CTX_data_main(m_context));
	if (m_liveUI) {
		for (Object *ob = (Object *)m_maggie->object.first; ob; ob = (Object *)ob->id.next) {
			LiveSnapshotTake(ob, m_liveSnapshots[ob]);
		}
		m_eventConsumer->SetFocusGate(true);
		WM_game_live_ui_begin(m_ar);
	}
}

void LA_BlenderLauncher::ExitEngine()
{
	if (m_liveUI) {
		WM_game_live_ui_end();
		m_liveUI = false;
		m_liveSnapshots.clear();
	}

	LA_Launcher::ExitEngine();

	// Lock frame and camera enabled - restoring global values.
	if (m_view3d->scenelock == 0) {
		m_startScene->lay = m_savedBlenderData.sceneLayer;
		m_startScene->camera = m_savedBlenderData.camera;
	}

	// Free all window manager events unused.
	wm_event_free_all(m_window);
}

void LA_BlenderLauncher::RenderEngine()
{
	if (m_drawLetterBox) {
		// Clear screen to border color
		// We do this here since we set the canvas to be within the frames. This means the engine
		// itself is unaware of the extra space, so we clear the whole region for it.
		m_rasterizer->SetClearColor(m_startScene->gm.framing.col[0], m_startScene->gm.framing.col[1], m_startScene->gm.framing.col[2]);
		m_rasterizer->SetViewport(m_ar->winrct.xmin, m_ar->winrct.ymin,
		                          BLI_rcti_size_x(&m_ar->winrct) + 1, BLI_rcti_size_y(&m_ar->winrct) + 1);
		m_rasterizer->SetScissor(m_ar->winrct.xmin, m_ar->winrct.ymin,
		                         BLI_rcti_size_x(&m_ar->winrct) + 1, BLI_rcti_size_y(&m_ar->winrct) + 1);
		m_rasterizer->Clear(RAS_Rasterizer::RAS_COLOR_BUFFER_BIT);
	}
	LA_Launcher::RenderEngine();
}

// Valores de todas as propriedades de um componente, para comparar quadro a quadro.
static std::string live_component_signature(PythonComponent *pc)
{
	std::string sig;
	for (PythonComponentProperty *cprop = (PythonComponentProperty *)pc->properties.first; cprop; cprop = cprop->next) {
		sig.append(cprop->name);
		sig.push_back('\0');
		sig.append((const char *)&cprop->type, sizeof(cprop->type));
		sig.append((const char *)&cprop->boolval, sizeof(cprop->boolval));
		sig.append((const char *)&cprop->intval, sizeof(cprop->intval));
		sig.append((const char *)&cprop->floatval, sizeof(cprop->floatval));
		sig.append((const char *)&cprop->itemval, sizeof(cprop->itemval));
		sig.append((const char *)cprop->vec, sizeof(cprop->vec));
		sig.append(cprop->strval);
		sig.push_back('\0');
	}
	return sig;
}

void LA_BlenderLauncher::LiveSnapshotTake(Object *ob, LiveObjectSnapshot &snap)
{
	snap.gpuParticles = ob->gpu_particles;
	snap.gpuParticlesMix = ob->gpu_particles_mix;
	snap.wheels.clear();
	for (bWheelSettings *wheel = (bWheelSettings *)ob->vehicle_wheels.first; wheel; wheel = wheel->next) {
		snap.wheels.push_back(*wheel);
	}
	snap.gears.clear();
	for (bGearRatio *gear = (bGearRatio *)ob->vehicle_gears.first; gear; gear = gear->next) {
		snap.gears.push_back(gear->ratio);
	}
	snap.vehicleMaxTorque = ob->vehicle_max_torque;
	snap.vehicleMaxRPM = ob->vehicle_max_rpm;
	snap.gearboxType = ob->gearbox_type;
	snap.vehicleRayCastMask = ob->vehicle_ray_cast_mask;
	snap.steeringWheel = ob->vehicle_steering_wheel;
	snap.componentArgs.clear();
	for (PythonComponent *pc = (PythonComponent *)ob->components.first; pc; pc = pc->next) {
		snap.componentArgs.push_back(live_component_signature(pc));
	}
	snap.props.clear();
	for (bProperty *prop = (bProperty *)ob->prop.first; prop; prop = prop->next) {
		LivePropSnapshot ps;
		ps.name = prop->name;
		ps.type = prop->type;
		ps.data = prop->data;
		if (prop->type == GPROP_STRING && prop->poin) {
			ps.str = (const char *)prop->poin;
		}
		snap.props.push_back(ps);
	}
}

static EXP_Value *live_create_property_value(bProperty *prop)
{
	switch (prop->type) {
		case GPROP_BOOL:
			return new EXP_BoolValue(prop->data != 0);
		case GPROP_INT:
			return new EXP_IntValue((int)prop->data);
		case GPROP_FLOAT:
		case GPROP_TIME:
			return new EXP_FloatValue(*((float *)&prop->data));
		case GPROP_STRING:
			return new EXP_StringValue(prop->poin ? (const char *)prop->poin : "", "");
		default:
			return nullptr;
	}
}

static bool live_wheel_equal(const bWheelSettings &a, const bWheelSettings &b)
{
	return a.radius == b.radius && a.suspension_rest_length == b.suspension_rest_length &&
	       a.has_steering == b.has_steering && a.has_drive == b.has_drive &&
	       a.suspension_stiffness == b.suspension_stiffness && a.suspension_damping == b.suspension_damping &&
	       a.suspension_compression == b.suspension_compression && a.friction == b.friction &&
	       a.roll_influence == b.roll_influence && a.max_suspension_travel_cm == b.max_suspension_travel_cm &&
	       a.max_suspension_force == b.max_suspension_force;
}

static bool live_vehicle_changed(Object *ob, const std::vector<bWheelSettings> &wheels, const std::vector<float> &gears,
                                 float maxTorque, float maxRPM, short gearboxType, short rayMask)
{
	if (ob->vehicle_max_torque != maxTorque || ob->vehicle_max_rpm != maxRPM ||
	    ob->gearbox_type != gearboxType || ob->vehicle_ray_cast_mask != rayMask)
	{
		return true;
	}
	size_t i = 0;
	for (bWheelSettings *wheel = (bWheelSettings *)ob->vehicle_wheels.first; wheel; wheel = wheel->next, ++i) {
		if (i >= wheels.size() || !live_wheel_equal(*wheel, wheels[i])) {
			return true;
		}
	}
	if (i != wheels.size()) {
		return true;
	}
	i = 0;
	for (bGearRatio *gear = (bGearRatio *)ob->vehicle_gears.first; gear; gear = gear->next, ++i) {
		if (i >= gears.size() || gear->ratio != gears[i]) {
			return true;
		}
	}
	return i != gears.size();
}

void LA_BlenderLauncher::LiveSyncVehicle(KX_GameObject *gameobj, Object *ob, const LiveObjectSnapshot &old)
{
	const int constraintId = gameobj->GetVehicleConstraintId();
	KX_Scene *scene = gameobj->GetScene();
	if (constraintId < 0 || !scene || !scene->GetPhysicsEnvironment()) {
		return;
	}
	PHY_IVehicle *vehicle = scene->GetPhysicsEnvironment()->GetVehicleConstraint(constraintId);
	if (!vehicle) {
		return;
	}

	// Mesma ordem da conversão (BL_BlenderDataConversion): roda N do veículo = N-ésima bWheelSettings.
	// Valores 0 ("padrão do Bullet") não são reenviados: o valor atual fica.
	int index = 0;
	for (bWheelSettings *wheel = (bWheelSettings *)ob->vehicle_wheels.first;
	     wheel && index < vehicle->GetNumWheels(); wheel = wheel->next, ++index)
	{
		const bWheelSettings *prev = (index < (int)old.wheels.size()) ? &old.wheels[index] : nullptr;
		if (prev && live_wheel_equal(*wheel, *prev)) {
			continue;
		}
		auto queue = [&](PHY_VehicleParameterId id, float value) {
			PHY_VehicleParameterCommand cmd;
			cmd.id = id;
			cmd.wheelIndex = index;
			cmd.value = value;
			vehicle->QueueParameterCommand(cmd);
		};
		queue(PHY_VEHICLE_PARAM_WHEEL_RADIUS, (wheel->radius > 0.0f) ? wheel->radius : 0.3f);
		queue(PHY_VEHICLE_PARAM_SUSPENSION_REST_LENGTH,
		      (wheel->suspension_rest_length > 0.0f) ? wheel->suspension_rest_length : 0.3f);
		queue(PHY_VEHICLE_PARAM_WHEEL_HAS_STEERING, wheel->has_steering ? 1.0f : 0.0f);
		const std::pair<PHY_VehicleParameterId, float> tunables[] = {
			{PHY_VEHICLE_PARAM_SUSPENSION_STIFFNESS, wheel->suspension_stiffness},
			{PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_RELAXATION, wheel->suspension_damping},
			{PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_COMPRESSION, wheel->suspension_compression},
			{PHY_VEHICLE_PARAM_WHEEL_FRICTION, wheel->friction},
			{PHY_VEHICLE_PARAM_ROLL_INFLUENCE, wheel->roll_influence},
			{PHY_VEHICLE_PARAM_MAX_SUSPENSION_TRAVEL, wheel->max_suspension_travel_cm},
			{PHY_VEHICLE_PARAM_MAX_SUSPENSION_FORCE, wheel->max_suspension_force},
		};
		for (const auto &t : tunables) {
			if (t.second > 0.0f) {
				queue(t.first, t.second);
			}
		}
		vehicle->SetWheelIsDriveWheel(index, wheel->has_drive != 0);
	}

	if (ob->vehicle_ray_cast_mask > 0) {
		vehicle->SetRayCastMask(ob->vehicle_ray_cast_mask);
	}
	gameobj->SetVehicleMaxTorque(ob->vehicle_max_torque);
	gameobj->SetVehicleMaxRPM(ob->vehicle_max_rpm);
	gameobj->SetVehicleGearboxType(ob->gearbox_type);
	std::vector<float> gearRatios;
	for (bGearRatio *gear = (bGearRatio *)ob->vehicle_gears.first; gear; gear = gear->next) {
		gearRatios.push_back(gear->ratio);
	}
	gameobj->SetVehicleGearRatios(gearRatios);
}

void LA_BlenderLauncher::LiveSyncFromBlender()
{
	// Compara o DNA de cada objeto com a cópia do último quadro; só o que o usuário mudou no
	// painel é empurrado para o jogo (valores que a lógica do jogo alterou não são sobrescritos).
	std::map<Object *, std::vector<KX_GameObject *> > users;
	bool usersBuilt = false;
	auto gameObjectsOf = [&](Object *ob) -> std::vector<KX_GameObject *> & {
		if (!usersBuilt) {
			for (KX_Scene *scene : *m_ketsjiEngine->CurrentScenes()) {
				for (KX_GameObject *gameobj : *scene->GetObjectList()) {
					if (gameobj->GetBlenderObject()) {
						users[gameobj->GetBlenderObject()].push_back(gameobj);
					}
				}
			}
			usersBuilt = true;
		}
		return users[ob];
	};

	for (Object *ob = (Object *)m_maggie->object.first; ob; ob = (Object *)ob->id.next) {
		LiveObjectSnapshot &snap = m_liveSnapshots[ob];
		bool changed = false;

		if (memcmp(&snap.gpuParticles, &ob->gpu_particles, sizeof(RangeGPUParticleSettings)) != 0) {
			for (KX_GameObject *gameobj : gameObjectsOf(ob)) {
				gameobj->ApplyGPUParticlesLive(snap.gpuParticles, ob->gpu_particles, false);
			}
			changed = true;
		}
		if (memcmp(&snap.gpuParticlesMix, &ob->gpu_particles_mix, sizeof(RangeGPUParticleSettings)) != 0) {
			for (KX_GameObject *gameobj : gameObjectsOf(ob)) {
				gameobj->ApplyGPUParticlesLive(snap.gpuParticlesMix, ob->gpu_particles_mix, true);
			}
			changed = true;
		}

		if ((ob->gameflag2 & OB_VEHICLE) &&
		    live_vehicle_changed(ob, snap.wheels, snap.gears, snap.vehicleMaxTorque, snap.vehicleMaxRPM,
		                         snap.gearboxType, snap.vehicleRayCastMask))
		{
			for (KX_GameObject *gameobj : gameObjectsOf(ob)) {
				LiveSyncVehicle(gameobj, ob, snap);
			}
			changed = true;
		}

		if (ob->vehicle_steering_wheel != snap.steeringWheel) {
			for (KX_GameObject *gameobj : gameObjectsOf(ob)) {
				gameobj->SetVehicleSteeringWheelName(ob->vehicle_steering_wheel ? ob->vehicle_steering_wheel->id.name + 2 : "");
			}
			changed = true;
		}

		size_t compIndex = 0;
		for (PythonComponent *pc = (PythonComponent *)ob->components.first; pc; pc = pc->next, ++compIndex) {
			if (compIndex < snap.componentArgs.size() && snap.componentArgs[compIndex] == live_component_signature(pc)) {
				continue;
			}
			for (KX_GameObject *gameobj : gameObjectsOf(ob)) {
				EXP_ListValue<KX_PythonComponent> *components = gameobj->GetComponents();
				if (!components) {
					continue;
				}
				for (KX_PythonComponent *component : *components) {
					if (component->GetBlenderPythonComponent() == pc) {
						component->LiveUpdateArgs();
					}
				}
			}
			changed = true;
		}

		for (bProperty *prop = (bProperty *)ob->prop.first; prop; prop = prop->next) {
			const LivePropSnapshot *old = nullptr;
			for (const LivePropSnapshot &ps : snap.props) {
				if (ps.name == prop->name) {
					old = &ps;
					break;
				}
			}
			const bool same = old && old->type == prop->type && old->data == prop->data &&
			                  (prop->type != GPROP_STRING || old->str == (prop->poin ? (const char *)prop->poin : ""));
			if (same) {
				continue;
			}
			changed = true;
			EXP_Value *value = live_create_property_value(prop);
			if (!value) {
				continue;
			}
			for (KX_GameObject *gameobj : gameObjectsOf(ob)) {
				// No lugar: preserva registro de timer e debug da propriedade existente.
				EXP_Value *existing = gameobj->GetProperty(prop->name);
				if (existing) {
					existing->SetValue(value);
				}
				else {
					gameobj->SetProperty(prop->name, value);
				}
			}
			value->Release();
		}

		if (changed || snap.props.size() != (size_t)BLI_listbase_count(&ob->prop)) {
			LiveSnapshotTake(ob, snap);
		}
	}
}

KX_ExitInfo LA_BlenderLauncher::EngineNextFrame()
{
	if (m_liveUI) {
		// Eventos fora da região do jogo vão para o editor; a UI é composta no back buffer
		// antes do quadro do jogo, que desenha por cima na sua região e troca o buffer.
		if (WM_game_live_ui_step(m_context)) {
			LiveSyncFromBlender();
		}
	}
	else {
		// Free all window manager events unused.
		wm_event_free_all(m_window);
		// Cadeado fechado: a UI travada aparece escurecida, sinal de que não responde.
		WM_game_locked_ui_draw(m_context, m_ar);
	}

	return LA_Launcher::EngineNextFrame();
}
