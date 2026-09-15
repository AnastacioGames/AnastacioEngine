
/** \file PHY_IVehicle.h
 *  \ingroup phys
 */

#ifndef __PHY_IVEHICLE_H__
#define __PHY_IVEHICLE_H__

//PHY_IVehicle provides a generic interface for (raycast based) vehicles. Mostly targetting 4 wheel cars and 2 wheel motorbikes.

#include "PHY_DynamicTypes.h"

class PHY_IMotionState;
class PHY_IPhysicsController;

/* Static per-wheel setup, as passed to AddWheel(). Safe to copy/expose freely;
 * never a reference into the physics backend's internal wheel data. */
struct PHY_VehicleWheelConfig
{
	mt::vec3 connectionPoint;
	mt::vec3 downDirection;
	mt::vec3 axleDirection;
	float suspensionRestLength;
	float wheelRadius;
	bool hasSteering;
	/* Game-logic metadata only (roadmap "plano 2", Fase C); has no effect on
	 * the physics backend. Set via SetWheelIsDriveWheel(), defaults to false. */
	bool isDriveWheel;
};

/* Per-wheel simulation output for a single physics tick, copied out of the
 * backend's internal wheel data (e.g. btWheelInfo) instead of exposing it by
 * reference. All fields belong to the same tick, identified by physicsTick. */
struct PHY_VehicleWheelState
{
	mt::vec3 worldPosition;
	mt::quat worldOrientation;
	float rotation;
	bool isInContact;
	mt::vec3 contactNormal;
	mt::vec3 contactPoint;
	float suspensionForce;
	unsigned long long physicsTick;

	/* Suspension mount point in world space (top of the raycast, fixed
	 * relative to the chassis) and the raycast direction in world space.
	 * Debug draw only; do not use for gameplay logic. */
	mt::vec3 hardPointWS;
	mt::vec3 wheelDirectionWS;
};

/* Live-editable vehicle parameters (roadmap Fase 4). Values are validated and
 * enqueued by the caller (e.g. the Vehicle Lab UI); the backend applies them
 * at the next safe simulation boundary, never mid-substep and never directly
 * from a render callback. */
enum PHY_VehicleParameterId
{
	PHY_VEHICLE_PARAM_SUSPENSION_STIFFNESS,
	PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_RELAXATION,
	PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_COMPRESSION,
	PHY_VEHICLE_PARAM_WHEEL_FRICTION,
	PHY_VEHICLE_PARAM_ROLL_INFLUENCE,
	PHY_VEHICLE_PARAM_MAX_SUSPENSION_TRAVEL,
	PHY_VEHICLE_PARAM_MAX_SUSPENSION_FORCE,
	PHY_VEHICLE_PARAM_STEERING,
	PHY_VEHICLE_PARAM_ENGINE_FORCE,
	PHY_VEHICLE_PARAM_BRAKE,
	/* wheelIndex is ignored for these two. */
	PHY_VEHICLE_PARAM_CHASSIS_MASS,
	PHY_VEHICLE_PARAM_RESET_SUSPENSION,
};

struct PHY_VehicleParameterCommand
{
	PHY_VehicleParameterId id;
	int wheelIndex;
	float value;
};

class PHY_IVehicle
{
public:
	virtual ~PHY_IVehicle()
	{
	};

	virtual void AddWheel(
	    PHY_IMotionState *motionState,
	    const mt::vec3 &connectionPoint,
	    const mt::vec3 &downDirection,
	    const mt::vec3 &axleDirection,
	    float suspensionRestLength,
	    float wheelRadius,
	    bool hasSteering) = 0;

	virtual int GetNumWheels() const = 0;

	virtual mt::vec3 GetWheelPosition(int wheelIndex) const = 0;
	virtual mt::quat GetWheelOrientationQuaternion(int wheelIndex) const = 0;
	virtual float GetWheelRotation(int wheelIndex) const = 0;

	/* Copies of static config / last-synced simulation state for one wheel.
	 * Never a reference into the backend's internal wheel data. Returns false
	 * (leaving *out untouched) for an out-of-range wheelIndex. */
	virtual bool GetWheelConfig(int wheelIndex, PHY_VehicleWheelConfig *out) const = 0;
	virtual bool GetWheelState(int wheelIndex, PHY_VehicleWheelState *out) const = 0;

	/* Monotonic counter incremented once per synchronized simulation step
	 * (i.e. once per SyncWheels() call), so callers can detect whether two
	 * reads belong to the same tick. */
	virtual unsigned long long GetPhysicsTick() const = 0;

	/* Signed scalar speed of the chassis along its forward axis, in km/h
	 * (backend native unit) and m/s. Sign matches the backend's convention,
	 * not necessarily the game's forward direction. */
	virtual float GetCurrentSpeedKmHour() const = 0;
	virtual float GetCurrentSpeedMps() const = 0;

	/* Unit vector along the chassis' forward axis, in world space. */
	virtual mt::vec3 GetForwardVector() const = 0;

	/* Current right/up/forward axis indices, each a permutation of {0, 1, 2}. */
	virtual void GetCoordinateSystem(int *rightIndex, int *upIndex, int *forwardIndex) const = 0;

	/* Reapplies the wheels' rest suspension length, applied at the next safe
	 * simulation boundary (backend-specific; never called mid-substep). */
	virtual void ResetSuspension() = 0;

	virtual int GetUserConstraintId() const = 0;
	virtual int GetUserConstraintType() const = 0;

	/* The chassis controller this vehicle was created with (CreateVehicle's
	 * ctrl argument). Used by a rebuild to re-attach a new vehicle to the same
	 * chassis after destroying this one; never take ownership of it. */
	virtual PHY_IPhysicsController *GetChassisController() const = 0;

	// some basic steering/braking/tuning/balancing (bikes)

	virtual void SetSteeringValue(float steering, int wheelIndex) = 0;

	virtual void ApplyEngineForce(float force, int wheelIndex) = 0;

	virtual void ApplyBraking(float braking, int wheelIndex) = 0;

	virtual void SetWheelFriction(float friction, int wheelIndex) = 0;

	virtual void SetSuspensionStiffness(float suspensionStiffness, int wheelIndex) = 0;

	virtual void SetSuspensionDamping(float suspensionStiffness, int wheelIndex) = 0;

	virtual void SetSuspensionCompression(float suspensionStiffness, int wheelIndex) = 0;

	virtual void SetRollInfluence(float rollInfluence, int wheelIndex) = 0;

	virtual void SetMaxSuspensionTravel(float maxSuspensionTravelCm, int wheelIndex) = 0;

	virtual void SetMaxSuspensionForce(float maxSuspensionForce, int wheelIndex) = 0;

	/* Game-logic metadata only, see PHY_VehicleWheelConfig::isDriveWheel. Does
	 * not touch the physics backend; no-op for an out-of-range wheelIndex. */
	virtual void SetWheelIsDriveWheel(int wheelIndex, bool isDriveWheel) = 0;

	/* Current live values, for the Vehicle Lab UI to display alongside a
	 * pending edit. Return 0 for an out-of-range wheelIndex. */
	virtual float GetWheelFriction(int wheelIndex) const = 0;
	virtual float GetSuspensionStiffness(int wheelIndex) const = 0;
	virtual float GetSuspensionDamping(int wheelIndex) const = 0;
	virtual float GetSuspensionCompression(int wheelIndex) const = 0;
	virtual float GetRollInfluence(int wheelIndex) const = 0;
	virtual float GetMaxSuspensionTravel(int wheelIndex) const = 0;
	virtual float GetMaxSuspensionForce(int wheelIndex) const = 0;

	/* Chassis mass in kg. Setting it goes through PHY_IPhysicsController's
	 * mass/inertia update, never a direct rigid body write. */
	virtual float GetChassisMass() const = 0;

	/* Validated live-parameter edit, queued and applied at the next call to
	 * the backend's post-step sync point (never applied out of band). A
	 * NaN/infinite value or an out-of-range wheelIndex (for a per-wheel
	 * parameter) drops the whole command instead of applying it partially. */
	virtual void QueueParameterCommand(const PHY_VehicleParameterCommand &command) = 0;

	virtual void SetCoordinateSystem(int rightIndex, int upIndex, int forwardIndex) = 0;

	virtual void SetRayCastMask(short mask) = 0;
	virtual short GetRayCastMask() const = 0;

	/* Lets a single external owner (e.g. KX_VehicleWrapper) know when this
	 * vehicle is about to be destroyed, so it can stop dereferencing it.
	 * Passing a nullptr callback unregisters any previous registration. */
	virtual void SetInvalidationCallback(void (*callback)(void *client), void *client) = 0;
};

#endif  /* __PHY_IVEHICLE_H__ */
