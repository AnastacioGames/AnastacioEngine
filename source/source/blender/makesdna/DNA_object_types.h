/*
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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 */

/** \file DNA_object_types.h
 *  \ingroup DNA
 *  \brief Object is a sort of wrapper for general info.
 */

#ifndef __DNA_OBJECT_TYPES_H__
#define __DNA_OBJECT_TYPES_H__

#include "DNA_object_enums.h"

#include "DNA_defs.h"
#include "DNA_listBase.h"
#include "DNA_ID.h"
#include "DNA_action_types.h" /* bAnimVizSettings */

#ifdef __cplusplus
extern "C" {
#endif

struct AnimData;
struct BoundBox;
struct DerivedMesh;
struct FluidsimSettings;
struct Ipo;
struct Material;
struct Object;
struct PartDeflect;
struct ParticleSystem;
struct Path;
struct RigidBodyOb;
struct SculptSession;
struct SoftBody;
struct bGPdata;
struct CurveMapping;


/* Vertex Groups - Name Info */
typedef struct bDeformGroup {
	struct bDeformGroup *next, *prev;
	char name[64];	/* MAX_VGROUP_NAME */
	/* need this flag for locking weights */
	char flag, pad[7];
} bDeformGroup;
#define MAX_VGROUP_NAME 64

/* bDeformGroup->flag */
#define DG_LOCK_WEIGHT 1

/**
 * The following illustrates the orientation of the
 * bounding box in local space
 *
 * <pre>
 *
 * Z  Y
 * | /
 * |/
 * .-----X
 *     2----------6
 *    /|         /|
 *   / |        / |
 *  1----------5  |
 *  |  |       |  |
 *  |  3-------|--7
 *  | /        | /
 *  |/         |/
 *  0----------4
 * </pre>
 */
typedef struct BoundBox {
	float vec[8][3];
	int flag, pad;
} BoundBox;

/* boundbox flag */
enum {
	BOUNDBOX_DISABLED = (1 << 0),
	BOUNDBOX_DIRTY  = (1 << 1),
};

typedef struct LodLevel {
	struct LodLevel *next, *prev;
	struct Object *source;
	int flags;
	float distance, pad;
	int obhysteresis;
	short atlas_cols, atlas_rows;
	int pad2;
} LodLevel;

/* Native vehicle wheel reference: identifies which child/scene objects act as
 * wheels for this chassis object, valid only when gameflag2 & OB_VEHICLE.
 * Every tunable float below follows the same "0 = use Bullet's built-in
 * default" convention as radius/suspension_rest_length. */
enum {
	WHEEL_SHOW_EXPANDED = (1 << 0)
};

typedef struct bWheelSettings {
	struct bWheelSettings *next, *prev;
	struct Object *ob;
	float radius;
	float suspension_rest_length;
	int has_steering;
	int has_drive;
	int flags;
	float suspension_stiffness;
	float suspension_damping;
	float suspension_compression;
	float friction;
	float roll_influence;
	float max_suspension_travel_cm;
	float max_suspension_force;
	float pad2;
	int pad3;
} bWheelSettings;

/* Object.gearbox_type values. */
enum {
	OB_GEARBOX_AUTOMATIC = 0,
	OB_GEARBOX_MANUAL    = 1
};

/* Native vehicle gearbox ratio entry: one entry per gear, ordered as the
 * driver shifts through them. A negative ratio is reverse gear; there is no
 * separate reverse flag, matching docs/vehicle-system-plan-2.md. */
typedef struct bGearRatio {
	struct bGearRatio *next, *prev;
	float ratio;
	int pad;
} bGearRatio;

typedef struct AnimationEvent {
	struct AnimationEvent *next, *prev;
	struct bAction *action;
	ListBase triggers;
	char eventcall[64];
	int flag, pad;
} AnimationEvent;

typedef struct AnimationEventTrigger {
	struct AnimationEventTrigger *next, *prev;
	char custom_arg[64];
	int frame, pad;
} AnimationEventTrigger;

typedef struct ObjectActivityCulling {
	/* For game engine, values around active camera where physics or logic are suspended */
	float physicsRadius;
	float logicRadius;

	int flags;
	int pad;
} ObjectActivityCulling;

/* Per-object GPU particle emitter settings (RAS_ParticleBuffer), used to seed it at game
 * start when Object.use_gpu_particles is on. See KX_ParticleSystem for the matching runtime
 * attributes (object.particles.*). Moved here from Scene in Fase I (was Scene.gpu_particles). */
typedef struct RangeGPUParticleSettings {
	float gravity[3];
	float lifetime;
	float emitter_position[3];
	float emitter_radius;
	float velocity[3];
	float velocity_randomness;
	float size;
	float color[4];
	float end_color[4];
	float end_size;
	int particle_count;
	int pad;
	char texture_path[1024]; /* FILE_MAX */
	float emission_direction[3];
	float emission_angle;
	/* Fase K: optional curve-driven size/color over lifetime.
	 * NULL-safe: falls back to linear mix(start, end) when use_* flags are off. */
	struct CurveMapping *size_curve;
	struct CurveMapping *color_curve;
	short use_size_curve, use_color_curve;
	/* Fase L: live in-game debug UI (Range.imgui overlay), toggled per-object. */
	short use_debug_ui;
	/* Fase M: blend mode for the particle draw (RAS_ParticleBuffer). 0 = Alpha, 1 = Additive. */
	short blend_mode;
	/* Billboard orientation mode for the particle draw. 0 = Camera Facing, 1 = Vertical. */
	short billboard_mode;
	/* Collision mode for the particle simulation shader. 0 = None, 1 = Ground Plane, 2 = Screen-Space. */
	short collision_mode;
	/* Fase N: seeds RAS_ParticleBuffer's runtime enabled flag at game start. Stored inverted
	 * (0 = enabled) so pre-existing .blend files, whose gpu_particles struct predates this
	 * field and is zeroed, keep emitting instead of silently going dark. */
	char disable_emission;
	/* Backface culling for the particle quad. 0 = off (default, both sides visible), 1 = on. */
	char use_backface_culling;
	char pad2[2];
	/* Ground Plane collision: world-space Z height of the analytic ground. */
	float collision_height;
	/* Bounce restitution (0 = sticks, 1 = bounces at equal velocity) applied on collision. */
	float collision_bounce;
	/* Velocity damping applied tangentially on collision. */
	float collision_friction;
	int pad3;
	/* Ground Plane collision: optional object whose world-space Z overrides collision_height
	 * every frame. NULL falls back to the fixed collision_height float above. */
	struct Object *collision_ground_object;
	/* Fase P: optional custom GLSL fragment shader, replacing the built-in sprite color/mask
	 * logic (round soft mask + linear/curve color mix). Path to an external .glsl file (same
	 * blend-relative "//" convention as texture_path above), not embedded in the .blend --
	 * RAS_ParticleBuffer polls its mtime at runtime and hot-reloads on change, so it can be
	 * edited in a real text editor while the game is running. Empty or use_custom_frag_shader ==
	 * 0 = default look. Must define its own `void main()` writing `fragColor`; see
	 * drawFragmentPreamble in RAS_ParticleShaderCache.cpp for the varyings/uniforms available
	 * (v_uv, v_lifeFrac, v_alpha, u_color, u_endColor, u_texture, u_useTexture, u_time, ...). */
	char frag_shader_path[1024]; /* FILE_MAX */
	short use_custom_frag_shader;
	char pad4[6];
} RangeGPUParticleSettings;

enum {
	GPU_PARTICLE_BLEND_ALPHA = 0,
	GPU_PARTICLE_BLEND_ADDITIVE = 1,
};

enum {
	GPU_PARTICLE_COLLISION_NONE = 0,
	GPU_PARTICLE_COLLISION_GROUND = 1,
	GPU_PARTICLE_COLLISION_DEPTH = 2,
};

enum {
	GPU_PARTICLE_BILLBOARD_CAMERA_FACING = 0,
	GPU_PARTICLE_BILLBOARD_VERTICAL = 1,
	/* Quad lies flat in world XY, facing down (world -Z) -- e.g. clouds seen from below. Fixed
	 * orientation, no camera dependency at all. */
	GPU_PARTICLE_BILLBOARD_HORIZONTAL = 2,
};

/* object activity flags */
enum {
	OB_ACTIVITY_PHYSICS = (1 << 0),
	OB_ACTIVITY_PHYSICS_SLEEPVELOCITY = (1 << 1),
	OB_ACTIVITY_LOGIC = (1 << 2),
	OB_ACTIVITY_LOGIC_COMPONENTS = (1 << 3)
};

typedef struct Object {
	ID id;
	struct AnimData *adt;		/* animation data (must be immediately after id for utilities to use it) */

	struct SculptSession *sculpt;

	short type, partype;
	int par1, par2, par3;	/* can be vertexnrs */
	char parsubstr[64];	/* String describing subobject info, MAX_ID_NAME-2 */
	struct Object *parent, *track;
	/* if ob->proxy (or proxy_group), this object is proxy for object ob->proxy */
	/* proxy_from is set in target back to the proxy. */
	struct Object *proxy, *proxy_group, *proxy_from;
	struct Ipo *ipo  DNA_DEPRECATED;  /* old animation system, deprecated for 2.5 */
	/* struct Path *path; */
	struct BoundBox *bb;  /* axis aligned boundbox (in localspace) */
	struct bAction *action  DNA_DEPRECATED;	 // XXX deprecated... old animation system
	struct bAction *poselib;
	struct bPose *pose;  /* pose data, armature objects only */
	void *data;  /* pointer to objects data - an 'ID' or NULL */

	struct bGPdata *gpd;	/* Grease Pencil data */

	bAnimVizSettings avs;	/* settings for visualization of object-transform animation */
	bMotionPath *mpath;		/* motion path cache for this object */

	struct Object *collision_bound; /* Range: Object used as Collision Bounds */
	void *pad1[2];

	ListBase constraintChannels  DNA_DEPRECATED; // XXX deprecated... old animation system
	ListBase effect  DNA_DEPRECATED;             // XXX deprecated... keep for readfile
	ListBase defbase;   /* list of bDeformGroup (vertex groups) names and flag only */
	ListBase modifiers; /* list of ModifierData structures */

	int mode;           /* Local object mode */
	int restore_mode;   /* Keep track of what mode to return to after toggling a mode */

	/* materials */
	struct Material **mat;	/* material slots */
	char *matbits;			/* a boolean field, with each byte 1 if corresponding material is linked to object */
	int totcol;				/* copy of mesh, curve & meta struct member of same name (keep in sync) */
	int actcol;				/* currently selected material in the UI */

	/* rot en drot have to be together! (transform('r' en 's')) */
	float loc[3], dloc[3], orig[3];
	float size[3];              /* scale in fact */
	float dsize[3] DNA_DEPRECATED ; /* DEPRECATED, 2.60 and older only */
	float dscale[3];            /* ack!, changing */
	float rot[3], drot[3];		/* euler rotation */
	float quat[4], dquat[4];	/* quaternion rotation */
	float rotAxis[3], drotAxis[3];	/* axis angle rotation - axis part */
	float rotAngle, drotAngle;	/* axis angle rotation - angle part */
	float obmat[4][4];		/* final worldspace matrix with constraints & animsys applied */
	float parentinv[4][4]; /* inverse result of parent, so that object doesn't 'stick' to parent */
	float constinv[4][4]; /* inverse result of constraints. doesn't include effect of parent or object local transform */
	float imat[4][4];	/* inverse matrix of 'obmat' for any other use than rendering! */
	                    /* note: this isn't assured to be valid as with 'obmat',
	                     *       before using this value you should do...
	                     *       invert_m4_m4(ob->imat, ob->obmat); */

	/* Previously 'imat' was used at render time, but as other places use it too
	 * the interactive ui of 2.5 creates problems. So now only 'imat_ren' should
	 * be used when ever the inverse of ob->obmat * re->viewmat is needed! - jahka
	 */
	float imat_ren[4][4];

	unsigned int lay;	/* copy of Base's layer in the scene */

	short flag;			/* copy of Base */
	short colbits DNA_DEPRECATED;		/* deprecated, use 'matbits' */

	short transflag, protectflag;	/* transformation settings and transform locks  */
	short trackflag, upflag;
	short nlaflag;				/* used for DopeSheet filtering settings (expanded/collapsed) */
	short scaflag;				/* ui state for game logic */
	char scavisflag;			/* more display settings for game logic */
	char depsflag;

	/* did last modifier stack generation need mapping support? */
	char lastNeedMapping;  /* bool */
	char pad;

	/* dupli-frame settings */
	int dupon, dupoff, dupsta, dupend;

	/* during realtime */

	/* note that inertia is only called inertia for historical reasons
	 * and is not changed to avoid DNA surgery. It actually reflects the
	 * Size value in the GameButtons (= radius) */

	float mass, damping, inertia;
	/* The form factor k is introduced to give the user more control
	 * and to fix incompatibility problems.
	 * For rotational symmetric objects, the inertia value can be
	 * expressed as: Theta = k * m * r^2
	 * where m = Mass, r = Radius
	 * For a Sphere, the form factor is by default = 0.4
	 */

	float formfactor;
	float rdamping;
	float margin;
	float max_vel; /* clamp the maximum velocity 0.0 is disabled */
	float min_vel; /* clamp the minimum velocity 0.0 is disabled */
	float max_angvel; /* clamp the maximum angular velocity, 0.0 is disabled */
	float min_angvel; /* clamp the minimum angular velocity, 0.0 is disabled */
	float obstacleRad;

	/* "Character" physics properties */
	float step_height;
	float jump_speed;
	float fall_speed;
	float max_slope;
	float smooth_movement;
	float jump_direction[3];
	int pad5;
	unsigned char max_jumps;
	char pad2[3];

	/** Collision mask settings */
	unsigned short col_group, col_mask;

	short rotmode;		/* rotation mode - uses defines set out in DNA_action_types.h for PoseChannel rotations... */

	char boundtype;            /* bounding box use for drawing */
	char collision_boundtype;  /* bounding box type used for collision */
	
	short dtx;			/* viewport draw extra settings */
	char dt;			/* viewport draw type */
	char empty_drawtype;
	float empty_drawsize;
	float dupfacesca;	/* dupliface scale */

	ListBase prop;			/* game logic property list (not to be confused with IDProperties) */
	ListBase sensors;		/* game logic sensors */
	ListBase controllers;	/* game logic controllers */
	ListBase actuators;		/* game logic actuators */
	ListBase components;	/* python components */

	struct ObjectActivityCulling activityCulling;

	float sf; /* sf is time-offset */

	short index;			/* custom index, for renderpasses */
	unsigned short actdef;	/* current deformation group, note: index starts at 1 */
	float col[4];			/* object color */

	int gameflag;
	int gameflag2;

	char restrictflag;		/* for restricting view, select, render etc. accessible in outliner */
	char recalc;			/* dependency flag */
	short softflag;			/* softbody settings */
	float anisotropicFriction[3];

	/* dynamic properties */
	float friction, rolling_friction, fh, reflect;
	float fhdist, xyfrict;
	short dynamode, pad6[3];

	ListBase constraints;		/* object constraints */
	ListBase nlastrips  DNA_DEPRECATED;			// XXX deprecated... old animation system
	ListBase hooks  DNA_DEPRECATED;				// XXX deprecated... old animation system
	ListBase particlesystem;	/* particle systems */

	struct BulletSoftBody *bsoft;	/* settings for game engine bullet soft body */
	struct PartDeflect *pd;		/* particle deflector/attractor/collision data */
	struct SoftBody *soft;		/* if exists, saved in file */
	struct Group *dup_group;	/* object duplicator for group */

	char  body_type;			/* for now used to temporarily holds the type of collision object */
	char  shapeflag;			/* flag for pinning */
	short shapenr;				/* current shape key for menu or pinned */
	float smoothresh;			/* smoothresh is phong interpolation ray_shadow correction in render */

	struct FluidsimSettings *fluidsimSettings; /* if fluidsim enabled, store additional settings */

	/* Runtime valuated curve-specific data, not stored in the file */
	struct CurveCache *curve_cache;

	struct DerivedMesh *derivedDeform, *derivedFinal;
	uint64_t lastDataMask;   /* the custom data layer mask that was last used to calculate derivedDeform and derivedFinal */
	uint64_t customdata_mask; /* (extra) custom data layer mask to use for creating derivedmesh, set by depsgraph */
	unsigned int state;			/* bit masks of game controllers that are active */
	unsigned int init_state;	/* bit masks of initial state as recorded by the users */

	ListBase gpulamp;		/* runtime, for glsl lamp display only */
	ListBase pc_ids;
	ListBase *duplilist;	/* for temporary dupli list storage, only for use by RNA API */

	struct RigidBodyOb *rigidbody_object;		/* settings for Bullet rigid body */
	struct RigidBodyCon *rigidbody_constraint;	/* settings for Bullet constraint */

	/* contains bWheelSettings, valid only when gameflag2 & OB_VEHICLE */
	ListBase vehicle_wheels;

	/* PHY_IVehicle::SetRayCastMask() collision mask for the suspension
	 * raycasts, valid only when gameflag2 & OB_VEHICLE. 0 = use the physics
	 * backend's built-in default (all layers). */
	short vehicle_ray_cast_mask;
	short pad_vehicle_a;
	int pad_vehicle_b;

	/* Native vehicle steering-wheel visual: child object rotated by game logic
	 * on its local Y axis based on the current steering value. Optional,
	 * valid only when gameflag2 & OB_VEHICLE. */
	struct Object *vehicle_steering_wheel;

	/* Powertrain "arcade feel" params, valid only when gameflag2 & OB_VEHICLE.
	 * Pure feeling tuning consumed by Python (vehicle_player_component.py) to
	 * scale engine force; never touches Bullet's btRaycastVehicle tire model. */
	float vehicle_max_torque;
	float vehicle_max_rpm;

	/* contains bGearRatio, valid only when gameflag2 & OB_VEHICLE. Gear
	 * selection (Automatic/Manual) is gearbox_type below; both are pure
	 * Python "arcade feel" like vehicle_max_torque/vehicle_max_rpm. */
	ListBase vehicle_gears;
	short gearbox_type;
	short gearbox_pad;
	int gearbox_pad2;

	/* Chassis Center of Mass local offset, valid only when gameflag2 &
	 * OB_VEHICLE. Non-zero values make the converter wrap the chassis
	 * collision shape in a btCompoundShape with this local transform, since
	 * Bullet has no direct local-COM setter. Zero (default) keeps the
	 * existing single-shape path untouched. */
	float vehicle_com_offset[3];
	int pad_vehicle_com_offset;

	float ima_ofs[2];		/* offset for image empties */
	ImageUser *iuser;		/* must be non-null when oject is an empty image */
	void *pad3;

	ListBase lodlevels;		/* contains data for levels of detail */
	LodLevel *currentlod;
	float lodfactor, pad4;

	ListBase animevents; /* contains data for animation events */

	struct PreviewImage *preview;

	struct Mesh *gamePredefinedBound;

	/* GPU particle emitter (RAS_ParticleBuffer), opt-in per object via gameflag2 & OB_GPU_PARTICLES */
	struct RangeGPUParticleSettings gpu_particles;
} Object;

/* Warning, this is not used anymore because hooks are now modifiers */
typedef struct ObHook {
	struct ObHook *next, *prev;

	struct Object *parent;
	float parentinv[4][4];	/* matrix making current transform unmodified */
	float mat[4][4];		/* temp matrix while hooking */
	float cent[3];			/* visualization of hook */
	float falloff;			/* if not zero, falloff is distance where influence zero */

	char name[64];	/* MAX_NAME */

	int *indexar;
	int totindex, curindex; /* curindex is cache for fast lookup */
	short type, active;		/* active is only first hook, for button menu */
	float force;
} ObHook;

/* runtime only, but include here for rna access */
typedef struct DupliObject {
	struct DupliObject *next, *prev;
	struct Object *ob;
	float mat[4][4];
	float orco[3], uv[2];

	short type; /* from Object.transflag */
	char no_draw, animated;

	/* persistent identifier for a dupli object, for inter-frame matching of
	 * objects with motion blur, or inter-update matching for syncing */
	int persistent_id[16]; /* 2*MAX_DUPLI_RECUR */

	/* particle this dupli was generated from */
	struct ParticleSystem *particle_system;
	unsigned int random_id;
	unsigned int pad;
} DupliObject;

/* **************** OBJECT ********************* */

/* dynamode */
#define OB_FH_NOR	        2

/* used many places... should be specialized  */
#define SELECT          1

/* type */
enum {
	OB_EMPTY      = 0,
	OB_MESH       = 1,
	OB_CURVE      = 2,
	OB_SURF       = 3,
	OB_FONT       = 4,
	OB_MBALL      = 5,

	OB_LAMP       = 10,
	OB_CAMERA     = 11,

	OB_SPEAKER    = 12,

/*	OB_WAVE       = 21, */
	OB_LATTICE    = 22,

/* 23 and 24 are for life and sector (old file compat.) */
	OB_ARMATURE   = 25,
};

/* check if the object type supports materials */
#define OB_TYPE_SUPPORT_MATERIAL(_type) \
	((_type) >= OB_MESH && (_type) <= OB_MBALL)
#define OB_TYPE_SUPPORT_VGROUP(_type) \
	(ELEM(_type, OB_MESH, OB_LATTICE))
#define OB_TYPE_SUPPORT_EDITMODE(_type) \
	(ELEM(_type, OB_MESH, OB_FONT, OB_CURVE, OB_SURF, OB_MBALL, OB_LATTICE, OB_ARMATURE))
#define OB_TYPE_SUPPORT_PARVERT(_type) \
	(ELEM(_type, OB_MESH, OB_SURF, OB_CURVE, OB_LATTICE))

/** Matches #OB_TYPE_SUPPORT_EDITMODE. */
#define OB_DATA_SUPPORT_EDITMODE(_type) \
	(ELEM(_type, ID_ME, ID_CU, ID_MB, ID_LT, ID_AR))

/* is this ID type used as object data */
#define OB_DATA_SUPPORT_ID(_id_type) \
	(ELEM(_id_type, ID_ME, ID_CU, ID_MB, ID_LA, ID_SPK, ID_CA, ID_LT, ID_AR))

#define OB_DATA_SUPPORT_ID_CASE \
	ID_ME: case ID_CU: case ID_MB: case ID_LA: case ID_SPK: case ID_CA: case ID_LT: case ID_AR

/* partype: first 4 bits: type */
enum {
	PARTYPE       = (1 << 4) - 1,
	PAROBJECT     = 0,
#ifdef DNA_DEPRECATED
	PARCURVE      = 1,  /* Deprecated. */
#endif
	PARKEY        = 2,  /* XXX Unused, deprecated? */

	PARSKEL       = 4,
	PARVERT1      = 5,
	PARVERT3      = 6,
	PARBONE       = 7,

	/* slow parenting - is not threadsafe and/or may give errors after jumping  */
	PARSLOW       = 16,
};

/* (short) transflag */
/* flags 1 and 2 were unused or relics from past features */
enum {
	OB_NEG_SCALE        = 1 << 2,
	OB_DUPLIFRAMES      = 1 << 3,
	OB_DUPLIVERTS       = 1 << 4,
	OB_DUPLIROT         = 1 << 5,
	OB_DUPLINOSPEED     = 1 << 6,
	OB_DUPLICALCDERIVED = 1 << 7, /* runtime, calculate derivedmesh for dupli before it's used */
	OB_DUPLIGROUP       = 1 << 8,
	OB_DUPLIFACES       = 1 << 9,
	OB_DUPLIFACES_SCALE = 1 << 10,
	OB_DUPLIPARTS       = 1 << 11,
	OB_RENDER_DUPLI     = 1 << 12,
	OB_NO_CONSTRAINTS   = 1 << 13,  /* runtime constraints disable */
	OB_NO_PSYS_UPDATE   = 1 << 14,  /* hack to work around particle issue */

	OB_DUPLI            = OB_DUPLIFRAMES | OB_DUPLIVERTS | OB_DUPLIGROUP | OB_DUPLIFACES | OB_DUPLIPARTS,
};

/* (short) trackflag / upflag */
enum {
	OB_POSX = 0,
	OB_POSY = 1,
	OB_POSZ = 2,
	OB_NEGX = 3,
	OB_NEGY = 4,
	OB_NEGZ = 5,
};

/* gameflag in game.h */

/* dt: no flags */
enum {
	OB_BOUNDBOX  = 1,
	OB_WIRE      = 2,
	OB_SOLID     = 3,
	OB_MATERIAL  = 4,
	OB_TEXTURE   = 5,
	OB_RENDER    = 6,

	OB_PAINT     = 100,  /* temporary used in draw code */
};

/* dtx: flags (short) */
enum {
	OB_DRAWBOUNDOX    = 1 << 0,
	OB_AXIS           = 1 << 1,
	OB_TEXSPACE       = 1 << 2,
	OB_DRAWNAME       = 1 << 3,
	OB_DRAWIMAGE      = 1 << 4,
	/* for solid+wire display */
	OB_DRAWWIRE       = 1 << 5,
	/* for overdraw s*/
	OB_DRAWXRAY       = 1 << 6,
	/* enable transparent draw */
	OB_DRAWTRANSP     = 1 << 7,
	OB_DRAW_ALL_EDGES = 1 << 8,  /* only for meshes currently */
};

/* empty_drawtype: no flags */
enum {
	OB_ARROWS        = 1,
	OB_PLAINAXES     = 2,
	OB_CIRCLE        = 3,
	OB_SINGLE_ARROW  = 4,
	OB_CUBE          = 5,
	OB_EMPTY_SPHERE  = 6,
	OB_EMPTY_CONE    = 7,
	OB_EMPTY_IMAGE   = 8,
};

/* boundtype */
enum {
	OB_BOUND_BOX           = 0,
	OB_BOUND_SPHERE        = 1,
	OB_BOUND_CYLINDER      = 2,
	OB_BOUND_CONE          = 3,
	OB_BOUND_TRIANGLE_MESH = 4,
	OB_BOUND_CONVEX_HULL   = 5,
/*	OB_BOUND_DYN_MESH      = 6, */ /*UNUSED*/
	OB_BOUND_CAPSULE       = 7,
	OB_BOUND_EMPTY         = 8,
};

/* lod flags */
enum {
	OB_LOD_USE_MESH			= 1 << 0,
	OB_LOD_USE_MAT			= 1 << 1,
	OB_LOD_USE_HYST			= 1 << 2,
	OB_LOD_USE_INVISIBLE	= 1 << 3,
	OB_LOD_USE_BILLBOARD	= 1 << 4,
	OB_LOD_USE_ATLAS		= 1 << 5,
};


/* **************** BASE ********************* */

/* also needed for base!!!!! or rather, they interfere....*/
/* base->flag and ob->flag */
enum {
	BA_WAS_SEL = (1 << 1),
	/* NOTE: BA_HAS_RECALC_DATA can be re-used later if freed in readfile.c. */
	// BA_HAS_RECALC_OB = (1 << 2),  /* DEPRECATED */
	// BA_HAS_RECALC_DATA =  (1 << 3),  /* DEPRECATED */
	BA_SNAP_FIX_DEPS_FIASCO = (1 << 2),  /* Yes, re-use deprecated bit, all fine since it's runtime only. */
};

	/* NOTE: this was used as a proper setting in past, so nullify before using */
#define BA_TEMP_TAG         (1 << 5)

/* #define BA_FROMSET          (1 << 7) */ /*UNUSED*/

#define BA_TRANSFORM_CHILD  (1 << 8)  /* child of a transformed object */
#define BA_TRANSFORM_PARENT (1 << 13)  /* parent of a transformed object */


/* an initial attempt as making selection more specific! */
#define BA_DESELECT     0
#define BA_SELECT       1


#define OB_FROMDUPLI        (1 << 9)
#define OB_DONE             (1 << 10)  /* unknown state, clear before use */
/* #define OB_RADIO            (1 << 11) */  /* deprecated */
#define OB_FROMGROUP        (1 << 12)

/* WARNING - when adding flags check on PSYS_RECALC */
/* ob->recalc (flag bits!) */
enum {
	OB_RECALC_OB        = 1 << 0,
	OB_RECALC_DATA      = 1 << 1,
/* time flag is set when time changes need recalc, so baked systems can ignore it */
	OB_RECALC_TIME      = 1 << 2,
/* only use for matching any flag, NOT as an argument since more flags may be added. */
	OB_RECALC_ALL       = OB_RECALC_OB | OB_RECALC_DATA | OB_RECALC_TIME,
};

/* controller state */
#define OB_MAX_STATES       30

/* collision masks */
#define OB_MAX_COL_MASKS    16

/* ob->gameflag */
enum {
	OB_DYNAMIC               = 1 << 0,
	OB_CHILD                 = 1 << 1,
	OB_ACTOR                 = 1 << 2,
	OB_INERTIA_LOCK_X        = 1 << 3,
	OB_INERTIA_LOCK_Y        = 1 << 4,
	OB_INERTIA_LOCK_Z        = 1 << 5,
	OB_DO_FH                 = 1 << 6,
	OB_ROT_FH                = 1 << 7,
	OB_ANISOTROPIC_FRICTION  = 1 << 8,
	OB_GHOST                 = 1 << 9,
	OB_RIGID_BODY            = 1 << 10,
	OB_BOUNDS                = 1 << 11,

	OB_COLLISION_RESPONSE    = 1 << 12,
	OB_SECTOR                = 1 << 13,
	OB_PROP                  = 1 << 14,
	OB_MAINACTOR             = 1 << 15,

	OB_COLLISION             = 1 << 16,
	OB_SOFT_BODY             = 1 << 17,
	OB_OCCLUDER              = 1 << 18,
	OB_SENSOR                = 1 << 19,
	OB_NAVMESH               = 1 << 20,
	OB_HASOBSTACLE           = 1 << 21,
	OB_CHARACTER             = 1 << 22,

	OB_LOD_UPDATE_PHYSICS	 = 1 << 25,

	OB_TASK_CONVERT			 = 1 << 26,
};

/* ob->gameflag2 */
enum {
	OB_LOCK_RIGID_BODY_X_AXIS       = 1 << 2,
	OB_LOCK_RIGID_BODY_Y_AXIS       = 1 << 3,
	OB_LOCK_RIGID_BODY_Z_AXIS       = 1 << 4,
	OB_LOCK_RIGID_BODY_X_ROT_AXIS   = 1 << 5,
	OB_LOCK_RIGID_BODY_Y_ROT_AXIS   = 1 << 6,
	OB_LOCK_RIGID_BODY_Z_ROT_AXIS   = 1 << 7,

	OB_GPU_PARTICLES                = 1 << 8,
	/* Marks this object as a depth-collider for GPU particle Screen-Space collision:
	 * rendered into a dedicated depth-only pass (see RAS_COLLISION_DEPTH), independent of
	 * material flags like Depth Transparency. */
	OB_GPU_PARTICLE_COLLIDER        = 1 << 9,

	/* Opt-out: excludes this object from the Sun/CSM static shadow cache even if its
	 * body_type would otherwise classify it as static (e.g. a scripted moving platform
	 * with Static physics). Forces it into the per-frame dynamic shadow caster list. */
	OB_FORCE_DYNAMIC_SHADOW          = 1 << 10,

	/* Marks this object as a vehicle chassis: ob->vehicle_wheels lists the wheel
	 * objects. Native designer-facing marker only; runtime vehicle creation still
	 * goes through KX_VehicleWrapper/vehicle preset. */
	OB_VEHICLE                       = 1 << 11,

/*	OB_LIFE     = OB_PROP | OB_DYNAMIC | OB_ACTOR | OB_MAINACTOR | OB_CHILD, */
};

/* ob->body_type */
enum {
	OB_BODY_TYPE_NO_COLLISION   = 0,
	OB_BODY_TYPE_STATIC         = 1,
	OB_BODY_TYPE_DYNAMIC        = 2,
	OB_BODY_TYPE_RIGID          = 3,
	OB_BODY_TYPE_SOFT           = 4,
	OB_BODY_TYPE_OCCLUDER       = 5,
	OB_BODY_TYPE_SENSOR         = 6,
	OB_BODY_TYPE_NAVMESH        = 7,
	OB_BODY_TYPE_CHARACTER      = 8,
};

/* ob->depsflag */
enum {
	OB_DEPS_EXTRA_OB_RECALC     = 1 << 0,
	OB_DEPS_EXTRA_DATA_RECALC   = 1 << 1,
};

/* ob->scavisflag */
enum {
	OB_VIS_SENS     = 1 << 0,
	OB_VIS_CONT     = 1 << 1,
	OB_VIS_ACT      = 1 << 2,
};

/* ob->scaflag */
enum {
	OB_SHOWSENS     = 1 << 6,
	OB_SHOWACT      = 1 << 7,
	OB_ADDSENS      = 1 << 8,
	OB_ADDCONT      = 1 << 9,
	OB_ADDACT       = 1 << 10,
	OB_SHOWCONT     = 1 << 11,
	OB_ALLSTATE     = 1 << 12,
	OB_INITSTBIT    = 1 << 13,
	OB_DEBUGSTATE   = 1 << 14,
	OB_SHOWSTATE    = 1 << 15,
};

/* ob->restrictflag */
enum {
	OB_RESTRICT_VIEW    = 1 << 0,
	OB_RESTRICT_SELECT  = 1 << 1,
	OB_RESTRICT_RENDER  = 1 << 2,
};

/* ob->shapeflag */
enum {
	OB_SHAPE_LOCK       = 1 << 0,
	// OB_SHAPE_TEMPLOCK   = 1 << 1,  /* deprecated */
	OB_SHAPE_EDIT_MODE  = 1 << 2,
};

/* ob->nlaflag */
enum {
	/* WARNING: flags (1 << 0) and (1 << 1) were from old animsys */
	/* object-channel expanded status */
	OB_ADS_COLLAPSED    = 1 << 10,
	/* object's ipo-block */
	OB_ADS_SHOWIPO      = 1 << 11,
	/* object's constraint channels */
	OB_ADS_SHOWCONS     = 1 << 12,
	/* object's material channels */
	OB_ADS_SHOWMATS     = 1 << 13,
	/* object's marticle channels */
	OB_ADS_SHOWPARTS    = 1 << 14,
};

/* ob->animevents */
enum {
	ANIMEVENT_SHOW = (1 << 0)
};

/* ob->protectflag */
enum {
	OB_LOCK_LOCX    = 1 << 0,
	OB_LOCK_LOCY    = 1 << 1,
	OB_LOCK_LOCZ    = 1 << 2,
	OB_LOCK_LOC     = OB_LOCK_LOCX | OB_LOCK_LOCY | OB_LOCK_LOCZ,
	OB_LOCK_ROTX    = 1 << 3,
	OB_LOCK_ROTY    = 1 << 4,
	OB_LOCK_ROTZ    = 1 << 5,
	OB_LOCK_ROT     = OB_LOCK_ROTX | OB_LOCK_ROTY | OB_LOCK_ROTZ,
	OB_LOCK_SCALEX  = 1 << 6,
	OB_LOCK_SCALEY  = 1 << 7,
	OB_LOCK_SCALEZ  = 1 << 8,
	OB_LOCK_SCALE   = OB_LOCK_SCALEX | OB_LOCK_SCALEY | OB_LOCK_SCALEZ,
	OB_LOCK_ROTW    = 1 << 9,
	OB_LOCK_ROT4D   = 1 << 10,
};

#define MAX_DUPLI_RECUR 8

#ifdef __cplusplus
}
#endif

#endif
