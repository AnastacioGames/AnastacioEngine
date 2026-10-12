/** \file KX_VFogGlow.h
 *  \ingroup ketsji
 *  \brief Glowing objects that light the Volumetric Fog as virtual point lamps.
 */

#ifndef __KX_VFOG_GLOW_H__
#define __KX_VFOG_GLOW_H__

#include "mathfu.h"

#include <vector>

class KX_Scene;

/* An object with the game property fog_glow (strength) seen by the fog as a Point lamp: color from
 * the object color, reach from fog_glow_radius or 4x its largest scale. */
struct KX_VFogGlow {
	mt::vec3 position;
	mt::vec3 color;
	float radius;
	/* Strength at the camera, to rank it with the real lamps. */
	float score;
};

/* Glows whose reach gets near the fogged part (reach = fog max distance around camPos). */
void KX_VFogCollectGlows(KX_Scene *scene, const mt::vec3& camPos, float reach, std::vector<KX_VFogGlow>& glows);

#endif  /* __KX_VFOG_GLOW_H__ */
