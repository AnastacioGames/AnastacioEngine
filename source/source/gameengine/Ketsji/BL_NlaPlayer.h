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

/** \file BL_NlaPlayer.h
 *  \ingroup ketsji
 *
 * Plays the NLA tracks of an armature in game: each track is a layer, evaluated
 * from the bottom up with the same pose blending used by the action layers.
 */

#ifndef __BL_NLAPLAYER_H__
#define __BL_NLAPLAYER_H__

#include <cfloat>
#include <map>
#include <set>
#include <string>
#include <vector>

class KX_GameObject;
struct bAction;
struct bPose;
struct bPoseChannel;
struct FCurve;
struct NlaStrip;

class BL_NlaPlayer
{
private:
	KX_GameObject *m_obj;
	/// Private copies of the strip actions, evaluated from animation threads.
	std::map<bAction *, bAction *> m_actions;
	/// Bones keyed by the strips: reset to rest before each evaluation so Add strips don't accumulate.
	std::set<std::string> m_bones;
	/// Pose channels of m_bones, cached for the pose m_chanPose.
	std::vector<bPoseChannel *> m_chans;
	/// Private copies of the animated influence curves (evaluate_fcurve writes into the curve).
	std::map<const NlaStrip *, FCurve *> m_influence;
	bPose *m_prevPose;
	bPose *m_stripPose;

	float m_startFrame;
	float m_endFrame;
	float m_frame;
	float m_startTime;
	float m_speed;
	bool m_loop;
	bool m_playing;
	bool m_done;
	bool m_frameSet;
	/// The frame changed while culled: the pose still has to be applied.
	bool m_needApply;
	float m_prevUpdate;
	bPose *m_chanPose;

	void FreeActions();
	void ApplyPose();

public:
	BL_NlaPlayer(KX_GameObject *obj);
	~BL_NlaPlayer();

	/// Start the NLA from its first frame. Returns false when the object has no usable strip.
	/// earliest: the clock may start before the first strip (FLT_MAX: at the first strip).
	bool Play(float speed, bool loop, float earliest = FLT_MAX);
	void Stop();
	bool IsPlaying() const;
	/// Playing, or finished while culled with the last pose not applied yet.
	bool NeedsUpdate() const;

	float GetFrame() const;
	void SetFrame(float frame);
	float GetStartFrame() const;
	float GetEndFrame() const;

	void Update(float curtime, bool applyToObject);
};

#endif  /* __BL_NLAPLAYER_H__ */
