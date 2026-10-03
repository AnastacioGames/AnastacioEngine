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

/** \file LA_BlenderLauncher.h
 *  \ingroup launcher
 */

#include "LA_Launcher.h"

#include "DNA_object_types.h"

#include <map>
#include <string>
#include <vector>

#include "RAS_Rect.h"

struct Object;
class KX_GameObject;
struct bContext;
struct ARegion;
struct View3D;
struct rcti;
struct wmWindowManager;
struct wmWindow;

class LA_BlenderLauncher : public LA_Launcher
{
protected:
	bContext *m_context;
	ARegion *m_ar;
	rcti *m_camFrame;
	View3D *m_view3d;
	wmWindowManager *m_windowManager;
	wmWindow *m_window;
	int m_alwaysUseExpandFraming;
	bool m_drawLetterBox;
	RAS_Rect m_areaRect;

	/// Saved blender data to restore at the game end as m_savedData from LA_Launcher.
	struct SavedBlenderData {
		int sceneLayer;
		Object *camera;
	} m_savedBlenderData;

	/// UI ao vivo: o editor continua respondendo fora da região do jogo (só quando o jogo roda o
	/// próprio .blend do editor). Valores editados no painel entram no jogo pelo LiveSync.
	bool m_liveUI;
	struct LivePropSnapshot {
		std::string name;
		short type;
		int data;
		std::string str;
	};
	struct LiveObjectSnapshot {
		RangeGPUParticleSettings gpuParticles;
		RangeGPUParticleSettings gpuParticlesMix;
		std::vector<LivePropSnapshot> props;
		// Veículo nativo: rodas (bWheelSettings sem next/prev/ob) e parâmetros do chassi.
		std::vector<bWheelSettings> wheels;
		std::vector<float> gears;
		float vehicleMaxTorque;
		float vehicleMaxRPM;
		short gearboxType;
		short vehicleRayCastMask;
		Object *steeringWheel;
		// Argumentos dos componentes Python, achatados na ordem componente/propriedade.
		std::vector<std::string> componentArgs;
	};
	std::map<Object *, LiveObjectSnapshot> m_liveSnapshots;

	static void LiveSnapshotTake(Object *ob, LiveObjectSnapshot &snap);
	void LiveSyncFromBlender();
	static void LiveSyncVehicle(KX_GameObject *gameobj, Object *ob, const LiveObjectSnapshot &old);

	virtual void RenderEngine();

	virtual RAS_ICanvas *CreateCanvas(RAS_Rasterizer *rasty, const RAS_OffScreen::AttachmentList& attachments, int numSamples);
	virtual RAS_Rasterizer::DrawType GetRasterizerDrawMode();
	virtual void InitCamera();

	virtual void SetWindowOrder(short order);

public:
	LA_BlenderLauncher(GHOST_ISystem *system, Main *maggie, Scene *scene, GlobalSettings *gs, RAS_Rasterizer::StereoMode stereoMode,
	                   int argc, char **argv, bContext *context, rcti *camframe, ARegion *ar, int alwaysUseExpandFraming);
	virtual ~LA_BlenderLauncher();

	virtual void InitEngine();
	virtual void ExitEngine();

	virtual KX_ExitInfo EngineNextFrame();
};
