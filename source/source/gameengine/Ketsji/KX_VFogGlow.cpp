/** \file gameengine/Ketsji/KX_VFogGlow.cpp
 *  \ingroup ketsji
 */

#include "KX_VFogGlow.h"

#include "KX_GameObject.h"
#include "KX_Scene.h"
#include "EXP_Value.h"

#include <algorithm>

void KX_VFogCollectGlows(KX_Scene *scene, const mt::vec3& camPos, float reach, std::vector<KX_VFogGlow>& glows)
{
	glows.clear();
	for (KX_GameObject *gameobj : *scene->GetObjectList()) {
		EXP_Value *prop = gameobj->GetProperty("fog_glow");
		if (!prop || !gameobj->GetVisible()) {
			continue;
		}
		const float strength = (float)prop->GetNumber();
		if (strength <= 0.0f) {
			continue;
		}
		float radius;
		if (EXP_Value *r = gameobj->GetProperty("fog_glow_radius")) {
			radius = std::max((float)r->GetNumber(), 0.01f);
		}
		else {
			const mt::vec3& s = gameobj->NodeGetWorldScaling();
			radius = std::max(4.0f * std::max(std::max(std::fabs(s.x), std::fabs(s.y)), std::fabs(s.z)), 0.01f);
		}
		const mt::vec3& pos = gameobj->NodeGetWorldPosition();
		const float dist = (pos - camPos).Length();
		if (dist > reach + radius) {
			continue;
		}
		const mt::vec4& col = gameobj->GetObjectColor();
		KX_VFogGlow glow;
		glow.position = pos;
		glow.color = mt::vec3(col.x, col.y, col.z) * strength;
		glow.radius = radius;
		glow.score = strength * radius * radius / (radius * radius + dist * dist);
		glows.push_back(glow);
	}
}
