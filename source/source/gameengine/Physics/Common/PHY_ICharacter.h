
/** \file PHY_ICharacter.h
 *  \ingroup phys
 */

#ifndef __PHY_ICHARACTER_H__
#define __PHY_ICHARACTER_H__

//PHY_ICharacter provides a generic interface for "character" controllers

#include <utility>
#include <vector>
#include <string>

enum PHY_CharacterPosture {
	POSTURE_STAND = 0,
	POSTURE_CROUCH,
	POSTURE_CRAWL,
	POSTURE_JUMP_TUCK, ///< Automatic while rising in a jump.
	POSTURE_COUNT
};

class PHY_ICharacter
{
public:
	virtual ~PHY_ICharacter()
	{
		// Python may still hold a KX_CharacterWrapper: tell it the character is gone.
		std::vector<std::pair<void (*)(void *), void *> > callbacks = std::move(m_invalidationCallbacks);
		for (const std::pair<void (*)(void *), void *>& entry : callbacks) {
			entry.first(entry.second);
		}
	}

	/** Called when the character is deleted, so Python wrappers drop their pointer.
	 * A nullptr callback unregisters only this client. */
	void SetInvalidationCallback(void (*callback)(void *client), void *client)
	{
		for (auto it = m_invalidationCallbacks.begin(); it != m_invalidationCallbacks.end(); ++it) {
			if (it->second == client) {
				if (callback) {
					it->first = callback;
				}
				else {
					m_invalidationCallbacks.erase(it);
				}
				return;
			}
		}
		if (callback) {
			m_invalidationCallbacks.emplace_back(callback, client);
		}
	}

	virtual void Jump() = 0;
	virtual bool OnGround() = 0;

	virtual float GetGravity() = 0;
	virtual void SetGravity(float gravity) = 0;

	virtual unsigned char GetMaxJumps() = 0;
	virtual void SetMaxJumps(unsigned char maxJumps) = 0;

	virtual unsigned char GetJumpCount() = 0;

	/// Motion actuators in Add mode sum their walk this logic frame (W + D = diagonal).
	double m_addWalkStamp = -1.0;
	float m_addWalkLength = 0.0f;

	virtual void SetWalkDirection(const mt::vec3& dir) = 0;
	virtual mt::vec3 GetWalkDirection() = 0;

	virtual void SetJumpDirection(const mt::vec3& dir) = 0;
	virtual mt::vec3 GetJumpDirection() = 0;

	virtual const float GetSmoothMovement() = 0;
	virtual void SetSmoothMovement(float smoothMovement) = 0;

	virtual float GetFallSpeed() const = 0;
	virtual void SetFallSpeed(float fallSpeed) = 0;

	virtual float GetMaxSlope() const = 0;
	virtual void SetMaxSlope(float maxSlope) = 0;

	virtual float GetJumpSpeed() const = 0;
	virtual void SetJumpSpeed(float jumpSpeed) = 0;

	virtual void SetVelocity(const mt::vec3& vel, float time, bool local) = 0;

	virtual void Reset() = 0;

	/// Posture: the collision shape changes, the mesh does not.
	/// Growing back (stand up, untuck) waits until there is room.
	virtual void SetPosture(int posture) = 0;
	virtual int GetPosture() const = 0;
	virtual int GetRequestedPosture() const = 0;
	virtual bool CanStand() const = 0;
	/// Run: walk faster (Run Speed) while standing.
	virtual void SetRunning(bool running) = 0;
	virtual bool IsRunning() const = 0;
	/// Game property to keep updated with the posture name (empty = none).
	virtual const std::string& GetPostureProperty() const = 0;

private:
	std::vector<std::pair<void (*)(void *), void *> > m_invalidationCallbacks;
};

#endif //__PHY_ICHARACTER_H__
