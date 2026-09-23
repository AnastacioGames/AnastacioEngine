/* Shared contract for runtime properties used by gameplay-facing systems. */
#ifndef __SCA_RUNTIMEPROPERTY_H__
#define __SCA_RUNTIMEPROPERTY_H__

enum SCA_RuntimePropertyType {
	SCA_RUNTIME_PROPERTY_BOOL,
	SCA_RUNTIME_PROPERTY_FLOAT,
	SCA_RUNTIME_PROPERTY_VECTOR3
};

struct SCA_RuntimePropertyValue {
	SCA_RuntimePropertyType type;
	bool boolValue;
	float floatValue;
	float vectorValue[3];
};

#endif
