#include "KX_RuntimePropertyRegistry.h"

#include "KX_GameObject.h"

namespace {

const KX_RuntimePropertyDescriptor runtimeProperties[] = {
	{"transform.local_position", "Transform", "Local Position", KX_RUNTIME_PROPERTY_VECTOR3, KX_RUNTIME_PROPERTY_READ},
	{"transform.local_scale", "Transform", "Local Scale", KX_RUNTIME_PROPERTY_VECTOR3, KX_RUNTIME_PROPERTY_READ},
	{"render.visible", "Render", "Visible", KX_RUNTIME_PROPERTY_BOOL, KX_RUNTIME_PROPERTY_READ},
	{"physics.mass", "Physics", "Mass", KX_RUNTIME_PROPERTY_FLOAT, KX_RUNTIME_PROPERTY_READ},
	{"physics.linear_velocity", "Physics", "Linear Velocity", KX_RUNTIME_PROPERTY_VECTOR3, KX_RUNTIME_PROPERTY_READ},
	{"physics.angular_velocity", "Physics", "Angular Velocity", KX_RUNTIME_PROPERTY_VECTOR3, KX_RUNTIME_PROPERTY_READ},
	{"physics.gravity", "Physics", "Gravity", KX_RUNTIME_PROPERTY_VECTOR3, KX_RUNTIME_PROPERTY_READ},
};

bool EqualIdentifier(const char *left, const char *right)
{
	if (!left || !right) {
		return false;
	}
	while (*left && *right && *left == *right) {
		++left;
		++right;
	}
	return *left == *right;
}

void SetError(const char **error, const char *message)
{
	if (error) {
		*error = message;
	}
}

void SetVector(KX_RuntimePropertyValue& value, const mt::vec3& vector)
{
	value.type = KX_RUNTIME_PROPERTY_VECTOR3;
	value.vectorValue[0] = vector.x;
	value.vectorValue[1] = vector.y;
	value.vectorValue[2] = vector.z;
}

}  // namespace

const KX_RuntimePropertyDescriptor *KX_RuntimePropertyRegistry::GetDescriptors(unsigned int& count)
{
	count = sizeof(runtimeProperties) / sizeof(runtimeProperties[0]);
	return runtimeProperties;
}

bool KX_RuntimePropertyRegistry::Read(KX_GameObject *object,
	                                     const char *identifier,
	                                     KX_RuntimePropertyValue& value,
	                                     const char **error)
{
	if (!object) {
		SetError(error, "Runtime property target is unavailable.");
		return false;
	}

	if (EqualIdentifier(identifier, "transform.local_position")) {
		SetVector(value, object->NodeGetLocalPosition());
		return true;
	}
	if (EqualIdentifier(identifier, "transform.local_scale")) {
		SetVector(value, object->NodeGetLocalScaling());
		return true;
	}

	if (EqualIdentifier(identifier, "render.visible")) {
		value.type = KX_RUNTIME_PROPERTY_BOOL;
		value.boolValue = object->GetVisible();
		return true;
	}

	if (EqualIdentifier(identifier, "physics.mass")) {
		if (!object->GetPhysicsController()) {
			SetError(error, "Physics mass is unavailable because the object has no physics controller.");
			return false;
		}
		value.type = KX_RUNTIME_PROPERTY_FLOAT;
		value.floatValue = object->GetMass();
		return true;
	}
	if (EqualIdentifier(identifier, "physics.linear_velocity")) { SetVector(value, object->GetLinearVelocity(false)); return true; }
	if (EqualIdentifier(identifier, "physics.angular_velocity")) { SetVector(value, object->GetAngularVelocity(false)); return true; }
	if (EqualIdentifier(identifier, "physics.gravity")) { SetVector(value, object->GetGravity()); return true; }

	SetError(error, "Unknown runtime property identifier.");
	return false;
}
