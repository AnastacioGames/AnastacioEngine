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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file BL_NlaPlayer.cpp
 *  \ingroup ketsji
 */

#include "BL_NlaPlayer.h"
#include "BL_Action.h"
#include "BL_ArmatureObject.h"
#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"
#include "CM_Message.h"

#include <algorithm>
#include <cmath>

extern "C" {
#include "BKE_action.h"
#include "BKE_library.h"
#include "BKE_global.h"
#include "BKE_fcurve.h"
#include "BLI_string.h"
#include "BLI_math_rotation.h"
#include "BLI_math_vector.h"
#include "MEM_guardedalloc.h"
#include "DNA_anim_types.h"
#include "DNA_action_types.h"
#include "DNA_object_types.h"
}

namespace {

bool strip_usable(const NlaStrip *strip)
{
	return strip->type == NLASTRIP_TYPE_CLIP && strip->act && !(strip->flag & NLASTRIP_FLAG_MUTED);
}

/// Tracks evaluated by Blender: not muted, and only the solo one when solo is on.
bool track_usable(const AnimData *adt, const NlaTrack *track)
{
	if (track->flag & NLATRACK_MUTED) {
		return false;
	}
	if ((adt->flag & ADT_NLA_SOLO_TRACK) && !(track->flag & NLATRACK_SOLO)) {
		return false;
	}
	return true;
}

/// Strip of the track active at time, and the time clamped inside it (hold), like nlastrips_ctime_get_strip.
const NlaStrip *track_strip_at(const NlaTrack *track, float time, float &r_time)
{
	const NlaStrip *first = nullptr;
	const NlaStrip *before = nullptr;
	for (const NlaStrip *strip = (const NlaStrip *)track->strips.first; strip; strip = strip->next) {
		if (!strip_usable(strip)) {
			continue;
		}
		if (!first) {
			first = strip;
		}
		if (time >= strip->start && time <= strip->end) {
			r_time = time;
			return strip;
		}
		if (strip->end < time) {
			before = strip;
		}
	}
	if (first && time < first->start) {
		if (first->extendmode == NLASTRIP_EXTEND_HOLD) {
			r_time = first->start;
			return first;
		}
		return nullptr;
	}
	if (before && before->extendmode != NLASTRIP_EXTEND_NOTHING) {
		r_time = before->end;
		return before;
	}
	return nullptr;
}

/// Action frame for a strip time (copy of nlastrip_get_frame_actionclip without writing to the strip).
float strip_action_frame(const NlaStrip *strip, float time)
{
	const float repeat = (strip->repeat == 0.0f) ? 1.0f : strip->repeat;
	const float scale = (strip->scale == 0.0f) ? 1.0f : std::fabs(strip->scale);
	float actlength = strip->actend - strip->actstart;
	if (actlength == 0.0f) {
		actlength = 1.0f;
	}
	// At the strip end of a whole repeat count, stay on the last frame instead of wrapping.
	const bool atEnd = (time >= strip->end) && (repeat == std::floor(repeat));
	if (strip->flag & NLASTRIP_FLAG_REVERSE) {
		return atEnd ? strip->actstart : strip->actend - std::fmod(time - strip->start, actlength * scale) / scale;
	}
	return atEnd ? strip->actend : strip->actstart + std::fmod(time - strip->start, actlength * scale) / scale;
}

/// Influence curve of a strip (animated influence), or null.
const FCurve *strip_influence_curve(const NlaStrip *strip)
{
	for (const FCurve *fcu = (const FCurve *)strip->fcurves.first; fcu; fcu = fcu->next) {
		if (fcu->rna_path && STREQ(fcu->rna_path, "influence") && !fcu->driver) {
			return fcu;
		}
	}
	return nullptr;
}

/// Influence of a strip: its influence curve when animated, else the automatic blend in/out.
/// curve is the player's own copy, because evaluate_fcurve writes into the curve.
float strip_influence(const NlaStrip *strip, FCurve *curve, float time)
{
	if (strip->flag & NLASTRIP_FLAG_USR_INFLUENCE) {
		return curve ? evaluate_fcurve(curve, time) : strip->influence;
	}
	const float blendin = std::fabs(strip->blendin);
	const float blendout = std::fabs(strip->blendout);
	if (blendin != 0.0f && time <= strip->start + blendin) {
		return std::fabs(time - strip->start) / blendin;
	}
	if (blendout != 0.0f && time >= strip->end - blendout) {
		return std::fabs(strip->end - time) / blendout;
	}
	return 1.0f;
}

/// Rest transform of a pose channel (also the neutral value for Add blending).
void channel_rest(bPoseChannel *chan)
{
	zero_v3(chan->loc);
	unit_qt(chan->quat);
	zero_v3(chan->eul);
	unit_axis_angle(chan->rotAxis, &chan->rotAngle);
	copy_v3_fl(chan->size, 1.0f);
}

} // namespace

BL_NlaPlayer::BL_NlaPlayer(KX_GameObject *obj)
	:m_obj(obj),
	m_prevPose(nullptr),
	m_stripPose(nullptr),
	m_startFrame(0.0f),
	m_endFrame(0.0f),
	m_frame(0.0f),
	m_startTime(0.0f),
	m_speed(1.0f),
	m_loop(true),
	m_playing(false),
	m_done(true),
	m_frameSet(false),
	m_needApply(false),
	m_prevUpdate(-1.0f),
	m_chanPose(nullptr)
{
}

BL_NlaPlayer::~BL_NlaPlayer()
{
	FreeActions();
	if (m_prevPose) {
		BKE_pose_free(m_prevPose);
	}
	if (m_stripPose) {
		BKE_pose_free(m_stripPose);
	}
}

void BL_NlaPlayer::FreeActions()
{
	for (const auto &pair : m_actions) {
		BKE_libblock_free(G.main, pair.second);
	}
	m_actions.clear();
	for (const auto &pair : m_influence) {
		free_fcurve(pair.second);
	}
	m_influence.clear();
	m_chans.clear();
	m_chanPose = nullptr;
}

bool BL_NlaPlayer::Play(float speed, bool loop)
{
	Object *blenderobj = m_obj->GetBlenderObject();
	AnimData *adt = blenderobj ? blenderobj->adt : nullptr;
	if (m_obj->GetGameObjectType() != SCA_IObject::OBJ_ARMATURE) {
		CM_Warning("playNLA: object " << m_obj->GetName() << " is not an armature, NLA ignored");
		return false;
	}
	if (!adt || (adt->flag & ADT_NLA_EVAL_OFF)) {
		CM_Warning("playNLA: object " << m_obj->GetName() << " has no NLA tracks to play");
		return false;
	}

	// Called again while already playing (e.g. every frame from an Always sensor): keep going.
	if (m_playing && !m_done && speed == m_speed && loop == m_loop) {
		return true;
	}

	FreeActions();
	m_bones.clear();
	bool found = false;
	for (const NlaTrack *track = (const NlaTrack *)adt->nla_tracks.first; track; track = track->next) {
		if (!track_usable(adt, track)) {
			continue;
		}
		for (const NlaStrip *strip = (const NlaStrip *)track->strips.first; strip; strip = strip->next) {
			if (!strip_usable(strip)) {
				continue;
			}
			if (!found) {
				m_startFrame = strip->start;
				m_endFrame = strip->end;
				found = true;
			}
			m_startFrame = std::min(m_startFrame, strip->start);
			m_endFrame = std::max(m_endFrame, strip->end);
			if (strip->flag & NLASTRIP_FLAG_USR_INFLUENCE) {
				const FCurve *curve = strip_influence_curve(strip);
				if (curve) {
					m_influence[strip] = copy_fcurve(curve);
				}
			}
			if (m_actions.find(strip->act) == m_actions.end()) {
				m_actions[strip->act] = BKE_action_copy(G.main, strip->act);
				for (const FCurve *fcu = (const FCurve *)strip->act->curves.first; fcu; fcu = fcu->next) {
					if (!fcu->rna_path) {
						continue;
					}
					char *bone = BLI_str_quoted_substrN(fcu->rna_path, "pose.bones[");
					if (bone) {
						m_bones.insert(bone);
						MEM_freeN(bone);
					}
				}
			}
		}
	}
	if (!found) {
		CM_Warning("playNLA: object " << m_obj->GetName() << " has no NLA strip to play");
		m_playing = false;
		m_done = true;
		return false;
	}

	m_speed = speed;
	m_loop = loop;
	// Playing backwards starts at the end.
	m_frame = (speed < 0.0f) ? m_endFrame : m_startFrame;
	m_startTime = KX_GetActiveEngine()->GetAnimationsTime() - m_obj->GetScene()->GetSuspendedDelta();
	m_playing = true;
	m_done = false;
	m_frameSet = (speed < 0.0f);  // sync the clock with m_frame on the first update
	m_needApply = false;
	m_prevUpdate = -1.0f;
	return true;
}

void BL_NlaPlayer::Stop()
{
	m_playing = false;
	m_done = true;
	FreeActions();
}

bool BL_NlaPlayer::IsPlaying() const
{
	return m_playing && !m_done;
}

bool BL_NlaPlayer::NeedsUpdate() const
{
	return IsPlaying() || (m_playing && m_needApply);
}

float BL_NlaPlayer::GetFrame() const
{
	return m_frame;
}

float BL_NlaPlayer::GetStartFrame() const
{
	return m_startFrame;
}

float BL_NlaPlayer::GetEndFrame() const
{
	return m_endFrame;
}

void BL_NlaPlayer::SetFrame(float frame)
{
	if (!m_playing) {
		return;
	}
	m_frame = std::max(m_startFrame, std::min(frame, m_endFrame));
	m_frameSet = true;
	m_done = false;
}

void BL_NlaPlayer::Update(float curtime, bool applyToObject)
{
	if (!m_playing) {
		return;
	}
	if ((m_done || m_prevUpdate == curtime) && !m_frameSet) {
		// Finished while culled: apply the last pose once the armature is visible again.
		if (m_needApply && applyToObject) {
			ApplyPose();
			static_cast<BL_ArmatureObject *>(m_obj)->UpdateTimestep(curtime - (float)m_obj->GetScene()->GetSuspendedDelta());
			m_needApply = false;
		}
		return;
	}
	m_prevUpdate = curtime;
	curtime -= (float)m_obj->GetScene()->GetSuspendedDelta();

	const float fps = (float)KX_GetActiveEngine()->GetAnimFrameRate();
	if (m_frameSet || m_speed == 0.0f) {
		// Keep the frame set from Python and continue the clock from it.
		m_startTime = (m_speed != 0.0f) ? curtime - (m_frame - m_startFrame) / (fps * m_speed) : curtime;
		m_frameSet = false;
	}
	else {
		m_frame = m_startFrame + (curtime - m_startTime) * fps * m_speed;
	}

	const float length = m_endFrame - m_startFrame;
	if (m_frame > m_endFrame || m_frame < m_startFrame) {
		if (m_loop && length > 0.0f) {
			m_frame = m_startFrame + std::fmod(std::fmod(m_frame - m_startFrame, length) + length, length);
			m_startTime = curtime - (m_frame - m_startFrame) / (fps * m_speed);
		}
		else {
			m_frame = (m_frame > m_endFrame) ? m_endFrame : m_startFrame;
			m_done = true;
		}
	}

	// Culled armatures only advance the clock.
	if (applyToObject) {
		ApplyPose();
		static_cast<BL_ArmatureObject *>(m_obj)->UpdateTimestep(curtime);
		m_needApply = false;
	}
	else {
		m_needApply = true;
	}
}

void BL_NlaPlayer::ApplyPose()
{
	BL_ArmatureObject *arm = static_cast<BL_ArmatureObject *>(m_obj);
	Object *blenderobj = m_obj->GetBlenderObject();
	AnimData *adt = blenderobj ? blenderobj->adt : nullptr;
	if (!adt) {
		return;
	}

	bPose *pose = arm->GetArmatureObject()->pose;
	if (pose != m_chanPose) {
		// Look the keyed bones up once (again only if the pose was rebuilt).
		m_chans.clear();
		for (const std::string &name : m_bones) {
			bPoseChannel *chan = BKE_pose_channel_find_name(pose, name.c_str());
			if (chan) {
				m_chans.push_back(chan);
			}
		}
		m_chanPose = pose;
	}
	for (bPoseChannel *chan : m_chans) {
		channel_rest(chan);
	}

	// Like Blender, the first strip writes its full value: influence only blends over strips below.
	bool first = true;

	// Tracks go from the bottom up: each strip blends over the result of the tracks below it.
	for (const NlaTrack *track = (const NlaTrack *)adt->nla_tracks.first; track; track = track->next) {
		if (!track_usable(adt, track)) {
			continue;
		}
		float time;
		const NlaStrip *strip = track_strip_at(track, m_frame, time);
		if (!strip) {
			continue;
		}
		const auto it = m_actions.find(strip->act);
		if (it == m_actions.end()) {
			continue;
		}
		const auto curve = m_influence.find(strip);
		const float influence = std::max(0.0f, std::min(strip_influence(
		        strip, (curve != m_influence.end()) ? curve->second : nullptr, time), 1.0f));
		if (influence <= 0.0f) {
			continue;
		}

		if (first) {
			arm->SetPoseByAction(it->second, strip_action_frame(strip, time));
			first = false;
			continue;
		}

		arm->GetPose(&m_prevPose);
		if (strip->blendmode == NLASTRIP_MODE_ADD) {
			// Bones the strip doesn't key stay at rest, so they add nothing.
			for (bPoseChannel *chan = (bPoseChannel *)pose->chanbase.first; chan; chan = chan->next) {
				channel_rest(chan);
			}
		}
		arm->SetPoseByAction(it->second, strip_action_frame(strip, time));

		if (strip->blendmode == NLASTRIP_MODE_ADD) {
			// result = below + strip * influence
			arm->GetPose(&m_stripPose);
			arm->BlendInPose(m_prevPose, 1.0f, BL_Action::ACT_BLEND_BLEND);
			arm->BlendInPose(m_stripPose, influence, BL_Action::ACT_BLEND_ADD);
		}
		else if (influence < 1.0f) {
			// Replace (and unsupported modes): result = mix(below, strip, influence)
			arm->BlendInPose(m_prevPose, 1.0f - influence, BL_Action::ACT_BLEND_BLEND);
		}
	}
}
