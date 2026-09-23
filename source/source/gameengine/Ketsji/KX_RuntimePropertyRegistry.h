/*
 * Runtime properties exposed to gameplay-facing systems.
 *
 * This registry is deliberately small.  It is not a reflection layer for all
 * Blender RNA properties: entries are added only when their runtime contract
 * is safe and documented.
 */

#ifndef __KX_RUNTIMEPROPERTYREGISTRY_H__
#define __KX_RUNTIMEPROPERTYREGISTRY_H__

class KX_GameObject;

enum KX_RuntimePropertyType {
	KX_RUNTIME_PROPERTY_BOOL,
	KX_RUNTIME_PROPERTY_FLOAT,
	KX_RUNTIME_PROPERTY_VECTOR3
};

enum KX_RuntimePropertyAccess {
	KX_RUNTIME_PROPERTY_READ = 1,
	KX_RUNTIME_PROPERTY_WRITE = 2
};

struct KX_RuntimePropertyDescriptor {
	const char *identifier;
	const char *category;
	const char *label;
	KX_RuntimePropertyType type;
	unsigned int access;
};

struct KX_RuntimePropertyValue {
	KX_RuntimePropertyType type;
	bool boolValue;
	float floatValue;
	float vectorValue[3];
};

class KX_RuntimePropertyRegistry
{
public:
	/** Metadata owned by the registry; valid for the process lifetime. */
	static const KX_RuntimePropertyDescriptor *GetDescriptors(unsigned int& count);

	/**
	 * Read an explicitly supported runtime property.
	 * Returns false for an unknown property or an unavailable runtime feature,
	 * with an optional human-readable diagnostic in error.
	 */
	static bool Read(KX_GameObject *object,
	                 const char *identifier,
	                 KX_RuntimePropertyValue& value,
	                 const char **error = nullptr);
};

#endif  // __KX_RUNTIMEPROPERTYREGISTRY_H__
