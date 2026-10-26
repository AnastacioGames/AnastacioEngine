#ifndef __CCD_CONSTRAINT_H__
#define __CCD_CONSTRAINT_H__

#include "PHY_IConstraint.h"

class btTypedConstraint;

#include <vector>

class CcdConstraint : public PHY_IConstraint
{
private:
	btTypedConstraint *m_constraint;

	/// Python-visible id. Not stored in btTypedConstraint: there m_userConstraintId shares a
	/// union with m_userConstraintPtr, so setting the pointer overwrote the id.
	int m_identifier;

	/// Disable collision between constrained objects?
	bool m_disableCollision;
	/// The constraint is added in dynamic world?
	bool m_active;

public:
	CcdConstraint(btTypedConstraint *constraint, int identifier, bool disableCollision);

	/// Id of a constraint created by CreateConstraint, 0 if it has no CcdConstraint.
	static int GetIdentifier(const btTypedConstraint *constraint);
	virtual ~CcdConstraint();

	bool GetDisableCollision() const;
	bool GetActive() const;
	void SetActive(bool active);

	virtual bool GetEnabled() const;
	virtual void SetEnabled(bool enabled);

	virtual void SetParam(int param, float value0, float value1);
	virtual float GetParam(int param);

	virtual float GetBreakingThreshold() const;
	virtual void SetBreakingThreshold(float threshold);

	virtual int GetIdentifier() const;
	virtual PHY_ConstraintType GetType() const;

	virtual void SetInvalidationCallback(void (*callback)(void *client), void *client);

private:
	struct InvalidationCallback {
		void (*callback)(void *client);
		void *client;
	};
	std::vector<InvalidationCallback> m_invalidationCallbacks;
};

#endif  // __CCD_CONSTRAINT_H__
