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
 * The Original Code is Copyright (C) 2009 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/editors/space_logic/logic_window.c
 *  \ingroup splogic
 */

#include <string.h>
#include <stdio.h>
#include <stddef.h>
#include <float.h>

#include "DNA_actuator_types.h"
#include "DNA_controller_types.h"
#include "DNA_property_types.h"
#include "DNA_space_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_world_types.h"
#include "DNA_sensor_types.h"
#include "DNA_constraint_types.h"
#include "DNA_object_types.h"

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_string_utils.h"
#include "BLI_utildefines.h"
#include "BLI_math.h"

#include "BKE_action.h"
#include "BKE_context.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_sca.h"

#include "ED_undo.h"

#include "BLT_translation.h"

#include "UI_interface.h"
#include "UI_view2d.h"

#include "RNA_access.h"

/* XXX BAD BAD */
#include "../interface/interface_intern.h"

#include "logic_intern.h"

#define B_REDR		1

#define B_ADD_SENS		2703
#define B_CHANGE_SENS		2704
#define B_DEL_SENS		2705

#define B_ADD_CONT		2706
#define B_CHANGE_CONT		2707
#define B_DEL_CONT		2708

#define B_ADD_ACT		2709
#define B_CHANGE_ACT		2710
#define B_DEL_ACT		2711

#define B_SOUNDACT_BROWSE	2712

#define B_SETPROP		2714
#define B_SETACTOR		2715
#define B_SETMAINACTOR		2716
#define B_SETDYNA		2717
#define B_SET_STATE_BIT	2718
#define B_INIT_STATE_BIT	2719

/* proto */
static ID **get_selected_and_linked_obs(bContext *C, short *count, short scavisflag);

static void do_logic_buts(bContext *C, void *UNUSED(arg), int event)
{
	Main *bmain= CTX_data_main(C);
	bSensor *sens;
	bController *cont;
	bActuator *act;
	Object *ob;
	int didit, bit;

	ob = CTX_data_active_object(C);
	if (ob == NULL) { return; }

	switch (event) {

	case B_SETPROP:
		/* check for inconsistent types */
		ob->gameflag &= ~(OB_SECTOR|OB_MAINACTOR|OB_DYNAMIC|OB_ACTOR);
		break;

	case B_SETACTOR:
	case B_SETDYNA:
	case B_SETMAINACTOR:
		ob->gameflag &= ~(OB_SECTOR|OB_PROP);
		break;

	case B_ADD_SENS:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			if (ob->scaflag & OB_ADDSENS) {
				ob->scaflag &= ~OB_ADDSENS;
				sens= new_sensor(SENS_ALWAYS);
				BLI_addtail(&(ob->sensors), sens);
				BLI_uniquename(&ob->sensors, sens, DATA_("Sensor"), '.', offsetof(bSensor, name), sizeof(sens->name));
				ob->scaflag |= OB_SHOWSENS;
			}
		}

		ED_undo_push(C, "Add sensor");
		break;

	case B_CHANGE_SENS:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			sens= ob->sensors.first;
			while (sens) {
				if (sens->type != sens->otype) {
					init_sensor(sens);
					sens->otype= sens->type;
					break;
				}
				sens= sens->next;
			}
		}
		break;

	case B_DEL_SENS:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			sens= ob->sensors.first;
			while (sens) {
				if (sens->flag & SENS_DEL) {
					BLI_remlink(&(ob->sensors), sens);
					free_sensor(sens);
					break;
				}
				sens= sens->next;
			}
		}
		ED_undo_push(C, "Delete sensor");
		break;

	case B_ADD_CONT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			if (ob->scaflag & OB_ADDCONT) {
				ob->scaflag &= ~OB_ADDCONT;
				cont= new_controller(CONT_LOGIC_AND);
				BLI_uniquename(&ob->controllers, cont, DATA_("Controller"), '.', offsetof(bController, name), sizeof(cont->name));
				ob->scaflag |= OB_SHOWCONT;
				BLI_addtail(&(ob->controllers), cont);
				/* set the controller state mask from the current object state.
				 * A controller is always in a single state, so select the lowest bit set
				 * from the object state */
				for (bit=0; bit<32; bit++) {
					if (ob->state & (1<<bit))
						break;
				}
				cont->state_mask = (1<<bit);
				if (cont->state_mask == 0) {
					/* shouldn't happen, object state is never 0 */
					cont->state_mask = 1;
				}
			}
		}
		ED_undo_push(C, "Add controller");
		break;

	case B_SET_STATE_BIT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			if (ob->scaflag & OB_ALLSTATE) {
				ob->scaflag &= ~OB_ALLSTATE;
				ob->state = 0x3FFFFFFF;
			}
		}
		break;

	case B_INIT_STATE_BIT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			if (ob->scaflag & OB_INITSTBIT) {
				ob->scaflag &= ~OB_INITSTBIT;
				ob->state = ob->init_state;
				if (!ob->state)
					ob->state = 1;
			}
		}
		break;

	case B_CHANGE_CONT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			cont= ob->controllers.first;
			while (cont) {
				if (cont->type != cont->otype) {
					init_controller(cont);
					cont->otype= cont->type;
					break;
				}
				cont= cont->next;
			}
		}
		break;


	case B_DEL_CONT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			cont= ob->controllers.first;
			while (cont) {
				if (cont->flag & CONT_DEL) {
					BLI_remlink(&(ob->controllers), cont);
					unlink_controller(cont);
					free_controller(cont);
					break;
				}
				cont= cont->next;
			}
		}
		ED_undo_push(C, "Delete controller");
		break;

	case B_ADD_ACT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			if (ob->scaflag & OB_ADDACT) {
				ob->scaflag &= ~OB_ADDACT;
				act= new_actuator(ACT_OBJECT);
				BLI_uniquename(&ob->actuators, act, DATA_("Actuator"), '.', offsetof(bActuator, name), sizeof(act->name));
				BLI_addtail(&(ob->actuators), act);
				ob->scaflag |= OB_SHOWACT;
			}
		}
		ED_undo_push(C, "Add actuator");
		break;

	case B_CHANGE_ACT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			act= ob->actuators.first;
			while (act) {
				if (act->type != act->otype) {
					init_actuator(act);
					act->otype= act->type;
					break;
				}
				act= act->next;
			}
		}
		break;

	case B_DEL_ACT:
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			act= ob->actuators.first;
			while (act) {
				if (act->flag & ACT_DEL) {
					BLI_remlink(&(ob->actuators), act);
					unlink_actuator(act);
					free_actuator(act);
					break;
				}
				act= act->next;
			}
		}
		ED_undo_push(C, "Delete actuator");
		break;

	case B_SOUNDACT_BROWSE:
		/* since we don't know which... */
		didit= 0;
		for (ob=bmain->object.first; ob; ob=ob->id.next) {
			act= ob->actuators.first;
			while (act) {
				if (act->type==ACT_SOUND) {
					bSoundActuator *sa= act->data;
					if (sa->sndnr) {
						ID *sound= bmain->sound.first;
						int nr= 1;

						if (sa->sndnr == -2) {
// XXX							activate_databrowse((ID *)bmain->sound.first, ID_SO, 0, B_SOUNDACT_BROWSE,
//											&sa->sndnr, do_logic_buts);
							break;
						}

						while (sound) {
							if (nr==sa->sndnr)
								break;
							nr++;
							sound= sound->next;
						}

						if (sa->sound)
							id_us_min(((ID *)sa->sound));

						sa->sound= (struct bSound *)sound;

						if (sound) {
							id_us_plus(sound);
						}

						sa->sndnr= 0;
						didit= 1;
					}
				}
				act= act->next;
			}
			if (didit)
				break;
		}

		break;
	}
}


static const char *sensor_name(int type)
{
	switch (type) {
	case SENS_ALWAYS:
		return N_("Always");
	case SENS_NEAR:
		return N_("Near");
	case SENS_KEYBOARD:
		return N_("Keyboard");
	case SENS_PROPERTY:
		return N_("Property");
	case SENS_ARMATURE:
		return N_("Armature");
	case SENS_ACTUATOR:
		return N_("Actuator");
	case SENS_DELAY:
		return N_("Delay");
	case SENS_MOUSE:
		return N_("Mouse");
	case SENS_COLLISION:
		return N_("Collision");
	case SENS_RADAR:
		return N_("Radar");
	case SENS_RANDOM:
		return N_("Random");
	case SENS_RAY:
		return N_("Ray");
	case SENS_MOVEMENT:
		return N_("Movement");
	case SENS_ANIMATIONEVENT:
		return N_("Animation Event");
	case SENS_MESSAGE:
		return N_("Message");
	case SENS_JOYSTICK:
		return N_("Joystick");
	}
	return N_("Unknown");
}

static const char *controller_name(int type)
{
	switch (type) {
	case CONT_LOGIC_AND:
		return N_("And");
	case CONT_LOGIC_OR:
		return N_("Or");
	case CONT_LOGIC_NAND:
		return N_("Nand");
	case CONT_LOGIC_NOR:
		return N_("Nor");
	case CONT_LOGIC_XOR:
		return N_("Xor");
	case CONT_LOGIC_XNOR:
		return N_("Xnor");
	case CONT_EXPRESSION:
		return N_("Expression");
	case CONT_PYTHON:
		return N_("Python");
	}
	return N_("Unknown");
}

static const char *actuator_name(int type)
{
	switch (type) {
	case ACT_ACTION:
		return N_("Action");
	case ACT_OBJECT:
		return N_("Motion");
	case ACT_LAMP:
		return N_("Lamp");
	case ACT_CAMERA:
		return N_("Camera");
	case ACT_MATERIAL:
		return N_("Material");
	case ACT_SOUND:
		return N_("Sound");
	case ACT_PROPERTY:
		return N_("Property");
	case ACT_EDIT_OBJECT:
		return N_("Edit Object");
	case ACT_CONSTRAINT:
		return N_("Constraint");
	case ACT_SCENE:
		return N_("Scene");
	case ACT_GROUP:
		return N_("Group");
	case ACT_RANDOM:
		return N_("Random");
	case ACT_MESSAGE:
		return N_("Message");
	case ACT_GAME:
		return N_("Game");
	case ACT_VIBRATION:
		return N_("Vibration");
	case ACT_VISIBILITY:
		return N_("Visibility");
	case ACT_2DFILTER:
		return N_("Filter 2D");
	case ACT_PARENT:
		return N_("Parent");
	case ACT_STATE:
		return N_("State");
	case ACT_ARMATURE:
		return N_("Armature");
	case ACT_STEERING:
		return N_("Steering");
	case ACT_MOUSE:
		return N_("Mouse");
	}
	return N_("Unknown");
}

static void set_sca_ob(Object *ob)
{
	bController *cont;
	bActuator *act;

	cont= ob->controllers.first;
	while (cont) {
		cont->mynew= (bController *)ob;
		cont= cont->next;
	}
	act= ob->actuators.first;
	while (act) {
		act->mynew= (bActuator *)ob;
		act= act->next;
	}
}

static ID **get_selected_and_linked_obs(bContext *C, short *count, short scavisflag)
{
	Base *base;
	Main *bmain = CTX_data_main(C);
	Scene *scene = CTX_data_scene(C);
	Object *ob, *obt, *obact = CTX_data_active_object(C);
	ID **idar;
	bSensor *sens;
	bController *cont;
	unsigned int lay;
	int a, nr, do_it;

	/* we need a sorted object list */
	/* set scavisflags flags in Objects to indicate these should be evaluated */
	/* also hide ob pointers in ->new entries of controllerss/actuators */

	*count = 0;

	if (scene == NULL) { return NULL; }

	ob = bmain->object.first;
	while (ob) {
		ob->scavisflag = 0;
		set_sca_ob(ob);
		ob = ob->id.next;
	}

	/* XXX here it checked 3d lay */
	lay = scene->lay;

	base = FIRSTBASE;
	while (base) {
		if (base->lay & lay) {
			if (base->flag & SELECT) {
				if (scavisflag & BUTS_SENS_SEL) base->object->scavisflag |= OB_VIS_SENS;
				if (scavisflag & BUTS_CONT_SEL) base->object->scavisflag |= OB_VIS_CONT;
				if (scavisflag & BUTS_ACT_SEL) base->object->scavisflag |= OB_VIS_ACT;
			}
		}
		base = base->next;
	}

	if (obact) {
		if (scavisflag & BUTS_SENS_ACT) obact->scavisflag |= OB_VIS_SENS;
		if (scavisflag & BUTS_CONT_ACT) obact->scavisflag |= OB_VIS_CONT;
		if (scavisflag & BUTS_ACT_ACT) obact->scavisflag |= OB_VIS_ACT;
	}

	/* BUTS_XXX_STATE are similar to BUTS_XXX_LINK for selecting the object */
	if (scavisflag & (BUTS_SENS_LINK | BUTS_CONT_LINK | BUTS_ACT_LINK | BUTS_SENS_STATE | BUTS_ACT_STATE)) {
		do_it = true;
		while (do_it) {
			do_it = false;

			ob = bmain->object.first;
			while (ob) {

				/* 1st case: select sensor when controller selected */
				if ((scavisflag & (BUTS_SENS_LINK | BUTS_SENS_STATE)) && (ob->scavisflag & OB_VIS_SENS) == 0) {
					sens = ob->sensors.first;
					while (sens) {
						for (a = 0; a < sens->totlinks; a++) {
							if (sens->links[a]) {
								obt = (Object*)sens->links[a]->mynew;
								if (obt && (obt->scavisflag & OB_VIS_CONT)) {
									do_it = true;
									ob->scavisflag |= OB_VIS_SENS;
									break;
								}
							}
						}
						if (do_it) break;
						sens = sens->next;
					}
				}

				/* 2nd case: select cont when act selected */
				if ((scavisflag & BUTS_CONT_LINK) && (ob->scavisflag & OB_VIS_CONT) == 0) {
					cont = ob->controllers.first;
					while (cont) {
						for (a = 0; a < cont->totlinks; a++) {
							if (cont->links[a]) {
								obt = (Object*)cont->links[a]->mynew;
								if (obt && (obt->scavisflag & OB_VIS_ACT)) {
									do_it = true;
									ob->scavisflag |= OB_VIS_CONT;
									break;
								}
							}
						}
						if (do_it) break;
						cont = cont->next;
					}
				}

				/* 3rd case: select controller when sensor selected */
				if ((scavisflag & BUTS_CONT_LINK) && (ob->scavisflag & OB_VIS_SENS)) {
					sens = ob->sensors.first;
					while (sens) {
						for (a = 0; a < sens->totlinks; a++) {
							if (sens->links[a]) {
								obt = (Object*)sens->links[a]->mynew;
								if (obt && (obt->scavisflag & OB_VIS_CONT) == 0) {
									do_it = true;
									obt->scavisflag |= OB_VIS_CONT;
								}
							}
						}
						sens = sens->next;
					}
				}

				/* 4th case: select actuator when controller selected */
				if ((scavisflag & (BUTS_ACT_LINK | BUTS_ACT_STATE)) && (ob->scavisflag & OB_VIS_CONT)) {
					cont = ob->controllers.first;
					while (cont) {
						for (a = 0; a < cont->totlinks; a++) {
							if (cont->links[a]) {
								obt = (Object*)cont->links[a]->mynew;
								if (obt && (obt->scavisflag & OB_VIS_ACT) == 0) {
									do_it = true;
									obt->scavisflag |= OB_VIS_ACT;
								}
							}
						}
						cont = cont->next;
					}

				}
				ob = ob->id.next;
			}
		}
	}

	/* now we count */
	ob= bmain->object.first;
	while (ob) {
		if (ob->scavisflag) (*count)++;
		ob = ob->id.next;
	}

	if (*count == 0) return NULL;
	if (*count > 24) *count = 24;  /* temporal */

	idar = MEM_callocN((*count)*sizeof(void *), "idar");

	ob= bmain->object.first;
	nr= 0;

	/* make the active object always the first one of the list */
	if (obact) {
		idar[0] = (ID *)obact;
		nr++;
	}

	while (ob) {
		if ((ob->scavisflag) && (ob != obact)) {
			idar[nr] = (ID*)ob;
			nr++;
		}
		if (nr >= 24) break;
		ob = ob->id.next;
	}

	/* just to be sure... these were set in set_sca_done_ob() */
	clear_sca_new_poins();

	return idar;
}

static void get_armature_bone_constraint(Object *ob, const char *posechannel, const char *constraint_name, bConstraint **constraint)
{
	/* check that bone exist in the active object */
	if (ob->type == OB_ARMATURE && ob->pose) {
		bPoseChannel *pchan= BKE_pose_channel_find_name(ob->pose, posechannel);
		if (pchan) {
			bConstraint *con = BLI_findstring(&pchan->constraints, constraint_name, offsetof(bConstraint, name));
			if (con) {
				*constraint = con;
			}
		}
	}
	/* didn't find any */
}

static void do_sensor_menu(bContext *C, void *UNUSED(arg), int event)
{
	SpaceLogic *slogic= CTX_wm_space_logic(C);
	ID **idar;
	Object *ob;
	bSensor *sens;
	short count, a;

	idar= get_selected_and_linked_obs(C, &count, slogic->scaflag);

	for (a = 0; a < count; a++) {
		ob = (Object*)idar[a];
		if (event == 0 || event == 2) ob->scaflag |= OB_SHOWSENS;
		else if (event == 1) ob->scaflag &= ~OB_SHOWSENS;
	}

	for (a = 0; a < count; a++) {
		ob = (Object*)idar[a];
		sens = ob->sensors.first;
		while (sens) {
			if (event == 2) sens->flag |= SENS_SHOW;
			else if (event == 3) sens->flag &= ~SENS_SHOW;
			sens = sens->next;
		}
	}

	if (idar) MEM_freeN(idar);
}

static uiBlock *sensor_menu(bContext *C, ARegion *ar, void *UNUSED(arg))
{
	uiBlock *block;
	int yco = 0;

	block= UI_block_begin(C, ar, __func__, UI_EMBOSS_PULLDOWN);
	UI_block_func_butmenu_set(block, do_sensor_menu, NULL);

	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Show Objects"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 1, 0, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Hide Objects"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 1, 1, "");
	uiDefBut(block, UI_BTYPE_SEPR_LINE, 0, "",	0, (short)(yco-=6), 160, 6, NULL, 0.0, 0.0, 0, 0, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Show Sensors"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 1, 2, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Hide Sensors"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 1, 3, "");

	UI_block_direction_set(block, UI_DIR_UP);
	UI_block_end(C, block);

	return block;
}

static void do_controller_menu(bContext *C, void *UNUSED(arg), int event)
{
	SpaceLogic *slogic = CTX_wm_space_logic(C);
	ID **idar;
	Object *ob;
	bController *cont;
	short count, a;

	idar = get_selected_and_linked_obs(C, &count, slogic->scaflag);

	for (a = 0; a < count; a++) {
		ob = (Object*)idar[a];
		if (event == 0 || event == 2) ob->scaflag |= OB_SHOWCONT;
		else if (event == 1) ob->scaflag &= ~OB_SHOWCONT;
	}

	for (a = 0; a < count; a++) {
		ob = (Object*)idar[a];
		cont = ob->controllers.first;
		while (cont) {
			if (event == 2) cont->flag |= CONT_SHOW;
			else if (event == 3) cont->flag &= ~CONT_SHOW;
			cont = cont->next;
		}
	}

	if (idar) MEM_freeN(idar);
}

static uiBlock *controller_menu(bContext *C, ARegion *ar, void *UNUSED(arg))
{
	uiBlock *block;
	int yco=0;

	block= UI_block_begin(C, ar, __func__, UI_EMBOSS_PULLDOWN);
	UI_block_func_butmenu_set(block, do_controller_menu, NULL);

	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Show Objects"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 1, 0, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Hide Objects"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 1, 1, "");
	uiDefBut(block, UI_BTYPE_SEPR_LINE, 0, "",					0, (short)(yco-=6), 160, 6, NULL, 0.0, 0.0, 0, 0, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Show Controllers"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 2, 2, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Hide Controllers"),	0, (short)(yco-=20), 160, 19, NULL, 0.0, 0.0, 3, 3, "");

	UI_block_direction_set(block, UI_DIR_UP);
	UI_block_end(C, block);

	return block;
}

static void do_actuator_menu(bContext *C, void *UNUSED(arg), int event)
{
	SpaceLogic *slogic= CTX_wm_space_logic(C);
	ID **idar;
	Object *ob;
	bActuator *act;
	short count, a;

	idar = get_selected_and_linked_obs(C, &count, slogic->scaflag);

	for (a = 0; a < count; a++) {
		ob = (Object*)idar[a];
		if (event == 0 || event == 2) ob->scaflag |= OB_SHOWACT;
		else if (event == 1) ob->scaflag &= ~OB_SHOWACT;
	}

	for (a = 0; a < count; a++) {
		ob = (Object*)idar[a];
		act = ob->actuators.first;
		while (act) {
			if (event == 2) act->flag |= ACT_SHOW;
			else if (event == 3) act->flag &= ~ACT_SHOW;
			act = act->next;
		}
	}

	if (idar) MEM_freeN(idar);
}

static uiBlock *actuator_menu(bContext *C, ARegion *ar, void *UNUSED(arg))
{
	uiBlock *block;
	int xco=0;

	block= UI_block_begin(C, ar, __func__, UI_EMBOSS_PULLDOWN);
	UI_block_func_butmenu_set(block, do_actuator_menu, NULL);

	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Show Objects"),	0, (short)(xco-=20), 160, 19, NULL, 0.0, 0.0, 1, 0, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Hide Objects"),	0, (short)(xco-=20), 160, 19, NULL, 0.0, 0.0, 1, 1, "");
	uiDefBut(block, UI_BTYPE_SEPR_LINE, 0, "",	0, (short)(xco-=6), 160, 6, NULL, 0.0, 0.0, 0, 0, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Show Actuators"),	0, (short)(xco-=20), 160, 19, NULL, 0.0, 0.0, 1, 2, "");
	uiDefBut(block, UI_BTYPE_BUT_MENU, 1, IFACE_("Hide Actuators"),	0, (short)(xco-=20), 160, 19, NULL, 0.0, 0.0, 1, 3, "");

	UI_block_direction_set(block, UI_DIR_UP);
	UI_block_end(C, block);

	return block;
}

static void check_controller_state_mask(bContext *UNUSED(C), void *arg1_but, void *arg2_mask)
{
	unsigned int *cont_mask = arg2_mask;
	uiBut *but = arg1_but;

	/* a controller is always in a single state */
	*cont_mask = (1<<but->retval);
	but->retval = B_REDR;
}

static uiBlock *controller_state_mask_menu(bContext *C, ARegion *ar, void *arg_cont)
{
	uiBlock *block;
	uiBut *but;
	bController *cont = arg_cont;

	short yco = 12, xco = 0, stbit, offset;

	block= UI_block_begin(C, ar, __func__, UI_EMBOSS);

	/* use this for a fake extra empy space around the buttons */
	uiDefBut(block, UI_BTYPE_LABEL, 0, "",			-5, -5, 200, 34, NULL, 0, 0, 0, 0, "");

	for (offset=0; offset<15; offset += 5) {
		UI_block_align_begin(block);
		for (stbit=0; stbit<5; stbit++) {
			but = uiDefButBitI(block, UI_BTYPE_TOGGLE, (1<<(stbit+offset)), (stbit+offset), "",	(short)(xco+12*stbit+13*offset), yco, 12, 12, (int *)&(cont->state_mask), 0, 0, 0, 0, "");
			UI_but_func_set(but, check_controller_state_mask, but, &(cont->state_mask));
		}
		for (stbit=0; stbit<5; stbit++) {
			but = uiDefButBitI(block, UI_BTYPE_TOGGLE, (1<<(stbit+offset+15)), (stbit+offset+15), "",	(short)(xco+12*stbit+13*offset), yco-12, 12, 12, (int *)&(cont->state_mask), 0, 0, 0, 0, "");
			UI_but_func_set(but, check_controller_state_mask, but, &(cont->state_mask));
		}
	}
	UI_block_align_end(block);

	UI_block_direction_set(block, UI_DIR_UP);
	UI_block_end(C, block);

	return block;
}

static bool is_sensor_linked(uiBlock *block, bSensor *sens)
{
	bController *cont;
	int i;

	for (i = 0; i < sens->totlinks; i++) {
		cont = sens->links[i];
		if (UI_block_links_find_inlink(block, cont) != NULL)
			return 1;
	}
	return 0;
}

/* Sensors code */

static void draw_sensor_header(uiLayout *layout, PointerRNA *ptr, PointerRNA *logic_ptr)
{
	uiLayout *box, *row, *sub;
	bSensor *sens = (bSensor *)ptr->data;

	box = uiLayoutBox(layout);
	row = uiLayoutRow(box, true);
	
	sub = uiLayoutRow(row, true);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemR(sub, ptr, "show_expanded", UI_ITEM_R_NO_BG, "", ICON_NONE);
	uiItemR(sub, ptr, "show_description", UI_ITEM_R_NO_BG, "", ICON_TEXT);
	if (RNA_boolean_get(ptr, "show_expanded")) {
		uiItemR(sub, ptr, "type", 0, "", ICON_NONE);
		uiItemR(sub, ptr, "name", 0, "", ICON_NONE);
	}
	else {
		uiItemL(sub, IFACE_(sensor_name(sens->type)), ICON_NONE);
		uiItemL(sub, sens->name, ICON_NONE);
	}

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, (((RNA_boolean_get(logic_ptr, "show_sensors_active_states") &&
	                         RNA_boolean_get(ptr, "show_expanded")) || RNA_boolean_get(ptr, "pin")) &&
					         RNA_boolean_get(ptr, "active")));
	uiItemR(sub, ptr, "pin", UI_ITEM_R_NO_BG, "", ICON_NONE);

	sub = uiLayoutRow(row, true);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	
	uiItemR(row, ptr, "color", 0, "", ICON_COLOR);
	uiItemEnumO(sub, "LOGIC_OT_sensor_move", "", ICON_TRIA_UP, "direction", 1); // up
	uiItemEnumO(sub, "LOGIC_OT_sensor_move", "", ICON_TRIA_DOWN, "direction", 2); // down

	sub = uiLayoutRow(row, false);
	uiItemR(sub, ptr, "active", 0, "", ICON_NONE);

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemO(sub, "", ICON_X, "LOGIC_OT_sensor_remove");

	// Sensor Description
	if (RNA_boolean_get(ptr, "show_description")) {
		row = uiLayoutRow(box, false);
		uiItemR(row, ptr, "sensor_description", 0, "", ICON_NONE);
	}
	
	// Custom Color
	uiLayoutBoxSetCustomColor(box, sens->color);
}

static void draw_sensor_internal_header(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *box, *split, *sub, *row;

	box = uiLayoutBox(layout);
	uiLayoutSetActive(box, RNA_boolean_get(ptr, "active"));
	split = uiLayoutSplit(box, 0.45f, false);

	row = uiLayoutRow(split, true);
	uiItemR(row, ptr, "use_pulse_true_level", 0, "", ICON_DOTSUP);
	uiItemR(row, ptr, "use_pulse_false_level", 0, "", ICON_DOTSDOWN);

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, (RNA_boolean_get(ptr, "use_pulse_true_level") ||
	                        RNA_boolean_get(ptr, "use_pulse_false_level")));
	if (RNA_boolean_get(ptr, "use_dt")) {
		uiItemR(sub, ptr, "tick_skip_dt", 0, IFACE_("Skip dt"), ICON_NONE);
	}
	else {
		uiItemR(sub, ptr, "tick_skip", 0, IFACE_("Skip"), ICON_NONE);
	}

	row = uiLayoutRow(split, true);
	uiItemR(row, ptr, "use_level", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	uiItemR(row, ptr, "use_tap", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

	row = uiLayoutRow(split, true);
	uiItemR(row, ptr, "use_dt", UI_ITEM_R_TOGGLE, IFACE_("Dt"), ICON_NONE);
	uiItemR(row, ptr, "invert", UI_ITEM_R_TOGGLE, IFACE_("Invert"), ICON_NONE);
}
/* sensors in alphabetical order */

static void draw_sensor_animation_event(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;

	Object *ob = (Object *)ptr->id.data;
	bool hasEvent = ob->animevents.first ? true : false;
	if (!hasEvent) {
		uiItemL(layout, IFACE_("Add an animation event to the object!"), ICON_INFO);
		return;
	}

	row = uiLayoutRow(layout, true);
	
	uiItemL(row, IFACE_("Event Index:"), ICON_SEQUENCE);
	uiItemR(row, ptr, "event_index", 0, "", ICON_NONE);

	int index = 0;
	int eventIndex = RNA_int_get(ptr, "event_index");
	char name[128];

	bool ok = false;

	int triggerIndexByEvent = -1;
	LISTBASE_FOREACH(AnimationEvent*, event, &ob->animevents) {
		if (index == eventIndex) {
			if (event->action) {
				strcpy(name, event->action->id.name);
				memmove(name, name + 2, strlen(name) - 1);

				uiItemL(row, IFACE_(name), ICON_ACTION);

				// Now, get the trigger value
				index = 0;
				LISTBASE_FOREACH(AnimationEventTrigger*, trigger, &event->triggers) {
					if (index == RNA_int_get(ptr, "trigger_index")) {
						triggerIndexByEvent = (int)trigger->frame;
						break;
					}
					index++;
				}
				ok = true;
			}
			break;
		}
		index++;
	}

	if (!ok) {
		uiItemL(row, IFACE_("Nothing"), ICON_CANCEL);
	}

	row = uiLayoutRow(layout, false);
	uiLayoutSetActive(row, !RNA_boolean_get(ptr, "trigger_all"));

	uiItemL(row, IFACE_("Trigger index:"), ICON_ACTION);
	uiItemR(row, ptr, "trigger_index", 0, "", ICON_NONE);

	if (triggerIndexByEvent == -1) {
		uiItemL(row, IFACE_("Nothing"), ICON_CANCEL);
	}
	else {
		char buffer[8];
		snprintf(buffer, sizeof(buffer), "%d", triggerIndexByEvent);
		uiItemL(row, IFACE_(buffer), ICON_ACTION_TWEAK);
	}

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "trigger_all", UI_ITEM_R_TOGGLE, IFACE_("All"), ICON_NONE);
}

static void draw_sensor_actuator(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob = (Object *)ptr->id.data;
	PointerRNA settings_ptr;

	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);
	uiItemPointerR(layout, ptr, "actuator", &settings_ptr, "actuators", NULL, ICON_LOGIC);
}

static void draw_sensor_armature(uiLayout *layout, PointerRNA *ptr)
{
	bSensor *sens = (bSensor *)ptr->data;
	bArmatureSensor *as = (bArmatureSensor *) sens->data;
	Object *ob = (Object *)ptr->id.data;
	uiLayout *row;

	if (ob->type != OB_ARMATURE) {
		uiItemL(layout, IFACE_("Sensor only available for armatures"), ICON_NONE);
		return;
	}

	if (ob->pose) {
		PointerRNA pose_ptr, pchan_ptr;
		PropertyRNA *bones_prop;

		RNA_pointer_create((ID *)ob, &RNA_Pose, ob->pose, &pose_ptr);
		bones_prop = RNA_struct_find_property(&pose_ptr, "bones");

		uiItemPointerR(layout, ptr, "bone", &pose_ptr, "bones", NULL, ICON_BONE_DATA);

		if (RNA_property_collection_lookup_string(&pose_ptr, bones_prop, as->posechannel, &pchan_ptr))
			uiItemPointerR(layout, ptr, "constraint", &pchan_ptr, "constraints", NULL, ICON_CONSTRAINT_BONE);
	}
	row = uiLayoutRow(layout, true);
	uiItemR(row, ptr, "test_type", 0, NULL, ICON_NONE);
	if (RNA_enum_get(ptr, "test_type") != SENS_ARM_STATE_CHANGED) {
		uiItemR(row, ptr, "value", 0, NULL, ICON_NONE);
	}
}

static void draw_sensor_collision(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *row, *split;
	PointerRNA main_ptr;

	RNA_main_pointer_create(CTX_data_main(C), &main_ptr);

	split = uiLayoutSplit(layout, 0.3f, false);
	row = uiLayoutRow(split, true);
	uiItemR(row, ptr, "use_pulse", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	uiItemR(row, ptr, "use_material", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

	switch (RNA_boolean_get(ptr, "use_material")) {
		case SENS_COLLISION_PROPERTY:
			uiItemR(split, ptr, "property", 0, NULL, ICON_NONE);
			break;
		case SENS_COLLISION_MATERIAL:
			uiItemPointerR(split, ptr, "material", &main_ptr, "materials", NULL, ICON_MATERIAL_DATA);
			break;
	}
}

static void draw_sensor_delay(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row, *split;

	row = uiLayoutRow(layout, false);

	if (RNA_boolean_get(ptr, "use_deltatime")) {
		uiItemR(row, ptr, "delay_time", 0, NULL, ICON_NONE);
	}
	else {
		uiItemR(row, ptr, "delay", 0, NULL, ICON_NONE);
	}
	
	uiItemR(row, ptr, "duration", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "use_repeat", 0, NULL, ICON_NONE);
	split = uiLayoutSplit(layout, 1.0f, false);
	row = uiLayoutRow(split, false);
	uiItemR(row, ptr, "repeat_times", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "use_deltatime", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	
}

static void draw_sensor_joystick(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *col, *row, *split;

	uiItemR(layout, ptr, "joystick_index", 0, NULL, ICON_NONE);
	split = uiLayoutSplit(layout, 0.75f, false);
	row = uiLayoutRow(split, false);
	uiItemR(row, ptr, "event_type", 0, NULL, ICON_NONE);

	switch (RNA_enum_get(ptr, "event_type")) {
		case SENS_JOY_BUTTON:
			uiItemR(split, ptr, "use_all_events", 0, NULL, ICON_NONE);

			col = uiLayoutColumn(layout, false);
			uiLayoutSetActive(col, RNA_boolean_get(ptr, "use_all_events") == false);
			uiItemR(col, ptr, "button_number", 0, NULL, ICON_NONE);
			break;
		case SENS_JOY_AXIS:
			uiItemR(split, ptr, "use_all_events", 0, NULL, ICON_NONE);

			col = uiLayoutColumn(layout, false);
			uiItemR(col, ptr, "axis_number", 0, NULL, ICON_NONE);
			uiLayoutSetActive(col, RNA_boolean_get(ptr, "use_all_events") == false);
			uiItemR(col, ptr, "axis_direction", 0, NULL, ICON_NONE);
			uiItemR(col, ptr, "axis_threshold", 0, NULL, ICON_NONE);
			break;
		case SENS_JOY_AXIS_SINGLE:
			col = uiLayoutColumn(layout, false);
			uiItemR(col, ptr, "single_axis_number", 0, NULL, ICON_NONE);
			uiItemR(col, ptr, "axis_threshold", 0, NULL, ICON_NONE);
			break;
		case SENS_JOY_SHOULDER_TRIGGER:
			col = uiLayoutColumn(layout, false);
			uiItemR(col, ptr, "axis_trigger_number", 0, NULL, ICON_NONE);
			uiItemR(col, ptr, "axis_threshold", 0, NULL, ICON_NONE);
			break;
	}
}

static void draw_sensor_keyboard(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob = (Object *)ptr->id.data;
	PointerRNA settings_ptr;
	uiLayout *row, *col;

	row = uiLayoutRow(layout, false);
	uiItemL(row, CTX_IFACE_(BLT_I18NCONTEXT_ID_WINDOWMANAGER, "Key:"), ICON_NONE);
	col = uiLayoutColumn(row, false);
	uiLayoutSetActive(col, RNA_boolean_get(ptr, "use_all_keys") == false);
	uiItemR(col, ptr, "key", UI_ITEM_R_EVENT, "", ICON_NONE);
	col = uiLayoutColumn(row, false);
	uiItemR(col, ptr, "use_all_keys", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

	col = uiLayoutColumn(layout, false);
	uiLayoutSetActive(col, RNA_boolean_get(ptr, "use_all_keys") == false);
	row = uiLayoutRow(col, false);
	uiItemL(row, IFACE_("First Modifier:"), ICON_NONE);
	uiItemR(row, ptr, "modifier_key_1", UI_ITEM_R_EVENT, "", ICON_NONE);

	row = uiLayoutRow(col, false);
	uiItemL(row, IFACE_("Second Modifier:"), ICON_NONE);
	uiItemR(row, ptr, "modifier_key_2", UI_ITEM_R_EVENT, "", ICON_NONE);

	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);
	uiItemPointerR(layout, ptr, "log", &settings_ptr, "properties", NULL, ICON_NONE);
	uiItemPointerR(layout, ptr, "target", &settings_ptr, "properties", NULL, ICON_NONE);
}

static void draw_sensor_message(uiLayout *layout, PointerRNA *ptr)
{
	uiItemR(layout, ptr, "subject", 0, NULL, ICON_NONE);
}

static void draw_sensor_mouse(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *split, *split2;
	PointerRNA main_ptr;

	split = uiLayoutSplit(layout, 0.8f, false);
	uiItemR(split, ptr, "mouse_event", 0, NULL, ICON_NONE);

	if (RNA_enum_get(ptr, "mouse_event") == BL_SENS_MOUSE_MOUSEOVER_ANY) {
		uiItemR(split, ptr, "use_pulse", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

		split = uiLayoutSplit(layout, 0.3f, false);
		uiItemR(split, ptr, "use_material", 0, "", ICON_NONE);

		split2 = uiLayoutSplit(split, 0.7f, false);
		if (RNA_enum_get(ptr, "use_material") == SENS_RAY_PROPERTY) {
			uiItemR(split2, ptr, "property", 0, "", ICON_NONE);
		}
		else {
			RNA_main_pointer_create(CTX_data_main(C), &main_ptr);
			uiItemPointerR(split2, ptr, "material", &main_ptr, "materials", "", ICON_MATERIAL_DATA);
		}
		uiItemR(split2, ptr, "use_x_ray", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

		split = uiLayoutSplit(layout, 0.3, false);
		uiItemR(split, ptr, "mask", 0, NULL, ICON_NONE);
	}
}

static void draw_sensor_near(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;

	uiItemR(layout, ptr, "property", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, true);
	uiItemR(row, ptr, "distance", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "reset_distance", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "use_debug", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
}

static void draw_sensor_property(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob = (Object *)ptr->id.data;
	PointerRNA settings_ptr;

	uiLayout *row, *runtime_box;
	uiItemR(layout, ptr, "evaluation_type", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "use_runtime_property", 0, NULL, ICON_NONE);
	if (RNA_boolean_get(ptr, "use_runtime_property")) {
		runtime_box = uiLayoutBox(layout);
		uiItemL(runtime_box, "Runtime API", ICON_INFO);
		uiItemR(runtime_box, ptr, "runtime_target", 0, "Target (empty = self)", ICON_NONE);
		uiItemR(runtime_box, ptr, "runtime_property", 0, "Exposed Property", ICON_NONE);
		if (RNA_enum_get(ptr, "runtime_property") == SENS_RUNTIME_PROP_VISIBLE) {
			uiItemL(runtime_box, "Category: Render  |  Type: Boolean", ICON_NONE);
		}
		else if (RNA_enum_get(ptr, "runtime_property") == SENS_RUNTIME_PROP_LOCAL_POSITION ||
		         RNA_enum_get(ptr, "runtime_property") == SENS_RUNTIME_PROP_LOCAL_SCALE) {
			uiItemL(runtime_box, "Category: Transform  |  Type: Vector3", ICON_NONE);
		}
		else {
			uiItemL(runtime_box, "Category: Physics", ICON_NONE);
		}
	}

	if (!RNA_boolean_get(ptr, "use_runtime_property")) {
		RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);
		uiItemPointerR(layout, ptr, "property", &settings_ptr, "properties", NULL, ICON_NONE);
	}

	switch (RNA_enum_get(ptr, "evaluation_type")) {
		case SENS_PROP_INTERVAL:
			if (RNA_boolean_get(ptr, "use_runtime_property") && RNA_enum_get(ptr, "runtime_property") == SENS_RUNTIME_PROP_MASS) {
				row = uiLayoutRow(layout, false);
				uiItemR(row, ptr, "runtime_value", 0, "Minimum", ICON_NONE);
				uiItemR(row, ptr, "runtime_value_max", 0, "Maximum", ICON_NONE);
			}
			else {
				row = uiLayoutRow(layout, false);
				uiItemR(row, ptr, "value_min", 0, NULL, ICON_NONE);
				uiItemR(row, ptr, "value_max", 0, NULL, ICON_NONE);
			}
			break;
		case SENS_PROP_EQUAL:
		case SENS_PROP_NEQUAL:
		case SENS_PROP_LESSTHAN:
		case SENS_PROP_GREATERTHAN:
			if (RNA_boolean_get(ptr, "use_runtime_property")) {
				const int property = RNA_enum_get(ptr, "runtime_property");
				if (property == SENS_RUNTIME_PROP_VISIBLE) {
					uiItemR(layout, ptr, "runtime_bool_value", 0, NULL, ICON_NONE);
				}
				else if (property == SENS_RUNTIME_PROP_MASS) {
					uiItemR(layout, ptr, "runtime_value", 0, "Value", ICON_NONE);
				}
				else {
					uiItemR(layout, ptr, "runtime_value", 0, NULL, ICON_NONE);
				}
			}
			else {
				uiItemR(layout, ptr, "value", 0, NULL, ICON_NONE);
			}
			break;
		case SENS_PROP_CHANGED:
			break;
	}
}

static void draw_sensor_radar(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;

	uiItemR(layout, ptr, "property", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "axis", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "angle", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "distance", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "use_debug", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
}

static void draw_sensor_random(uiLayout *layout, PointerRNA *ptr)
{
	uiItemR(layout, ptr, "seed", 0, NULL, ICON_NONE);
}

static void draw_sensor_ray(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *split, *row;
	PointerRNA main_ptr;

	RNA_main_pointer_create(CTX_data_main(C), &main_ptr);
	split = uiLayoutSplit(layout, 0.3f, false);
	uiItemR(split, ptr, "ray_type", 0, "", ICON_NONE);
	switch (RNA_enum_get(ptr, "ray_type")) {
		case SENS_RAY_PROPERTY:
			uiItemR(split, ptr, "property", 0, "", ICON_NONE);
			break;
		case SENS_RAY_MATERIAL:
			uiItemPointerR(split, ptr, "material", &main_ptr, "materials", "", ICON_MATERIAL_DATA);
			break;
	}

	split = uiLayoutSplit(layout, 0.3, false);
	uiItemR(split, ptr, "axis", 0, "", ICON_NONE);
	row = uiLayoutRow(split, false);
	uiItemR(row, ptr, "range", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "use_x_ray", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	split = uiLayoutSplit(layout, 0.3, false);
	uiItemR(split, ptr, "mask", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "use_debug", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
}

static void draw_sensor_movement(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;
	uiItemR(layout, ptr, "axis", 0, NULL, ICON_NONE);
	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "use_local", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	uiItemR(row, ptr, "threshold", 0, NULL, ICON_NONE);
}

static void draw_brick_sensor(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *box;

	if (!RNA_boolean_get(ptr, "show_expanded"))
		return;

	draw_sensor_internal_header(layout, ptr);

	box = uiLayoutBox(layout);
	uiLayoutSetActive(box, RNA_boolean_get(ptr, "active"));

	switch (RNA_enum_get(ptr, "type")) {

		case SENS_ANIMATIONEVENT:
			draw_sensor_animation_event(box, ptr);
			break;
		case SENS_ACTUATOR:
			draw_sensor_actuator(box, ptr);
			break;
		case SENS_ALWAYS:
			break;
		case SENS_ARMATURE:
			draw_sensor_armature(box, ptr);
			break;
		case SENS_COLLISION:
			draw_sensor_collision(box, ptr, C);
			break;
		case SENS_DELAY:
			draw_sensor_delay(box, ptr);
			break;
		case SENS_JOYSTICK:
			draw_sensor_joystick(box, ptr);
			break;
		case SENS_KEYBOARD:
			draw_sensor_keyboard(box, ptr);
			break;
		case SENS_MESSAGE:
			draw_sensor_message(box, ptr);
			break;
		case SENS_MOUSE:
			draw_sensor_mouse(box, ptr, C);
			break;
		case SENS_NEAR:
			draw_sensor_near(box, ptr);
			break;
		case SENS_PROPERTY:
			draw_sensor_property(box, ptr);
			break;
		case SENS_RADAR:
			draw_sensor_radar(box, ptr);
			break;
		case SENS_RANDOM:
			draw_sensor_random(box, ptr);
			break;
		case SENS_MOVEMENT:
			draw_sensor_movement(box, ptr);
			break;
		case SENS_RAY:
			draw_sensor_ray(box, ptr, C);
			break;
	}
}

/* Controller code */
static void draw_controller_header(uiLayout *layout, PointerRNA *ptr, int xco, int width, int yco)
{
	uiLayout *box, *row, *sub;
	bController *cont = (bController *)ptr->data;

	char state[3];
	BLI_snprintf(state, sizeof(state), "%d", RNA_int_get(ptr, "states"));

	box = uiLayoutBox(layout);
	row = uiLayoutRow(box, false);

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemR(sub, ptr, "show_expanded", UI_ITEM_R_NO_BG, "", ICON_NONE);
	if (RNA_boolean_get(ptr, "show_expanded")) {
		uiItemR(sub, ptr, "type", 0, "", ICON_NONE);
		uiItemR(sub, ptr, "name", 0, "", ICON_NONE);
		/* XXX provisory for Blender 2.50Beta */
		uiDefBlockBut(uiLayoutGetBlock(layout), controller_state_mask_menu, cont, state, (short)(xco+width-44), yco, 22+22, UI_UNIT_Y, IFACE_("Set controller state index (from 1 to 30)"));
	}
	else {
		uiItemL(sub, IFACE_(controller_name(cont->type)), ICON_NONE);
		uiItemL(sub, cont->name, ICON_NONE);
		uiItemL(sub, state, ICON_NONE);
	}

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemR(sub, ptr, "use_priority", 0, "", ICON_NONE);

	sub = uiLayoutRow(row, true);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemEnumO(sub, "LOGIC_OT_controller_move", "", ICON_TRIA_UP, "direction", 1); // up
	uiItemEnumO(sub, "LOGIC_OT_controller_move", "", ICON_TRIA_DOWN, "direction", 2); // down

	sub = uiLayoutRow(row, false);
	uiItemR(sub, ptr, "active", 0, "", ICON_NONE);

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemO(sub, "", ICON_X, "LOGIC_OT_controller_remove");

	if (cont->color)
		uiLayoutBoxSetCustomColor(box, cont->color);
}

static void draw_controller_expression(uiLayout *layout, PointerRNA *ptr)
{
	uiItemR(layout, ptr, "expression", 0, "", ICON_NONE);
}

static void draw_controller_python(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *split, *sub;

	split = uiLayoutSplit(layout, 0.3, true);
	uiItemR(split, ptr, "mode", 0, "", ICON_NONE);
	if (RNA_enum_get(ptr, "mode") == CONT_PY_SCRIPT) {
		uiItemR(split, ptr, "text", 0, "", ICON_NONE);
	}
	else {
		sub = uiLayoutSplit(split, 0.8f, false);
		uiItemR(sub, ptr, "module", 0, "", ICON_NONE);
		uiItemR(sub, ptr, "use_debug", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	}
}

static void draw_controller_state(uiLayout *UNUSED(layout), PointerRNA *UNUSED(ptr))
{

}

static void draw_brick_controller(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *box;

	if (!RNA_boolean_get(ptr, "show_expanded"))
		return;

	box = uiLayoutBox(layout);
	uiLayoutSetActive(box, RNA_boolean_get(ptr, "active"));

	draw_controller_state(box, ptr);

	switch (RNA_enum_get(ptr, "type")) {
		case CONT_LOGIC_AND:
			break;
		case CONT_LOGIC_OR:
			break;
		case CONT_EXPRESSION:
			draw_controller_expression(box, ptr);
			break;
		case CONT_PYTHON:
			draw_controller_python(box, ptr);
			break;
		case CONT_LOGIC_NAND:
			break;
		case CONT_LOGIC_NOR:
			break;
		case CONT_LOGIC_XOR:
			break;
		case CONT_LOGIC_XNOR:
			break;
	}
}

/* Actuator code */
static void draw_actuator_header(uiLayout *layout, PointerRNA *ptr, PointerRNA *logic_ptr)
{
	uiLayout *box, *row, *sub;
	bActuator *act= (bActuator *)ptr->data;

	box = uiLayoutBox(layout);
	row = uiLayoutRow(box, false);

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemR(sub, ptr, "show_expanded", UI_ITEM_R_NO_BG, "", ICON_NONE);
	if (RNA_boolean_get(ptr, "show_expanded")) {
		uiItemR(sub, ptr, "type", 0, "", ICON_NONE);
		uiItemR(sub, ptr, "name", 0, "", ICON_NONE);
	}
	else {
		uiItemL(sub, IFACE_(actuator_name(act->type)), ICON_NONE);
		uiItemL(sub, act->name, ICON_NONE);
	}

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, (((RNA_boolean_get(logic_ptr, "show_actuators_active_states") &&
	                          RNA_boolean_get(ptr, "show_expanded")) || RNA_boolean_get(ptr, "pin")) &&
	                          RNA_boolean_get(ptr, "active")));
	uiItemR(sub, ptr, "pin", UI_ITEM_R_NO_BG, "", ICON_NONE);

	sub = uiLayoutRow(row, true);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemEnumO(sub, "LOGIC_OT_actuator_move", "", ICON_TRIA_UP, "direction", 1); // up
	uiItemEnumO(sub, "LOGIC_OT_actuator_move", "", ICON_TRIA_DOWN, "direction", 2); // down

	sub = uiLayoutRow(row, false);
	uiItemR(sub, ptr, "active", 0, "", ICON_NONE);

	sub = uiLayoutRow(row, false);
	uiLayoutSetActive(sub, RNA_boolean_get(ptr, "active"));
	uiItemO(sub, "", ICON_X, "LOGIC_OT_actuator_remove");

	if (act->color)
		uiLayoutBoxSetCustomColor(box, act->color);
}

static void draw_actuator_action(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob = (Object *)ptr->id.data;
	PointerRNA settings_ptr;
	uiLayout *row, *sub;

	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "play_mode", 0, "", ICON_NONE);

	sub = uiLayoutRow(row, true);
	uiItemR(sub, ptr, "use_force", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	uiItemR(sub, ptr, "use_additive", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

	row = uiLayoutColumn(sub, false);
	uiLayoutSetActive(row, (RNA_boolean_get(ptr, "use_additive") || RNA_boolean_get(ptr, "use_force")));
	uiItemR(row, ptr, "use_local", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "action", 0, "", ICON_NONE);
	uiItemR(row, ptr, "use_continue_last_frame", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	if ((RNA_enum_get(ptr, "play_mode") == ACT_ACTION_FROM_PROP))
		uiItemPointerR(row, ptr, "property", &settings_ptr, "properties", NULL, ICON_NONE);

	else {
		uiItemR(row, ptr, "frame_start", 0, NULL, ICON_NONE);
		uiItemR(row, ptr, "frame_end", 0, NULL, ICON_NONE);
	}

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "frame_blend_in", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "priority", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "layer", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "layer_weight", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "blend_mode", 0, "", ICON_NONE);

	uiItemPointerR(layout, ptr, "frame_property", &settings_ptr, "properties", NULL, ICON_NONE);

#ifdef __NLA_ACTION_BY_MOTION_ACTUATOR
	uiItemR(layout, "stride_length", 0, NULL, ICON_NONE);
#endif
}

static void draw_actuator_armature(uiLayout *layout, PointerRNA *ptr)
{
	bActuator *act = (bActuator *)ptr->data;
	bArmatureActuator *aa = (bArmatureActuator *) act->data;
	Object *ob = (Object *)ptr->id.data;
	bConstraint *constraint = NULL;
	PointerRNA pose_ptr, pchan_ptr;
	PropertyRNA *bones_prop = NULL;

	if (ob->type != OB_ARMATURE) {
		uiItemL(layout, IFACE_("Actuator only available for armatures"), ICON_NONE);
		return;
	}

	if (ob->pose) {
		RNA_pointer_create((ID *)ob, &RNA_Pose, ob->pose, &pose_ptr);
		bones_prop = RNA_struct_find_property(&pose_ptr, "bones");
	}

	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_ARM_RUN:
			break;
		case ACT_ARM_ENABLE:
		case ACT_ARM_DISABLE:
			if (ob->pose) {
				uiItemPointerR(layout, ptr, "bone", &pose_ptr, "bones", NULL, ICON_BONE_DATA);

				if (RNA_property_collection_lookup_string(&pose_ptr, bones_prop, aa->posechannel, &pchan_ptr))
					uiItemPointerR(layout, ptr, "constraint", &pchan_ptr, "constraints", NULL, ICON_CONSTRAINT_BONE);
			}
			break;
		case ACT_ARM_SETTARGET:
			if (ob->pose) {
				uiItemPointerR(layout, ptr, "bone", &pose_ptr, "bones", NULL, ICON_BONE_DATA);

				if (RNA_property_collection_lookup_string(&pose_ptr, bones_prop, aa->posechannel, &pchan_ptr))
					uiItemPointerR(layout, ptr, "constraint", &pchan_ptr, "constraints", NULL, ICON_CONSTRAINT_BONE);
			}

			uiItemR(layout, ptr, "target", 0, NULL, ICON_NONE);

			/* show second target only if the constraint supports it */
			get_armature_bone_constraint(ob, aa->posechannel, aa->constraint, &constraint);
			if (constraint && constraint->type == CONSTRAINT_TYPE_KINEMATIC) {
				uiItemR(layout, ptr, "secondary_target", 0, NULL, ICON_NONE);
			}
			break;
		case ACT_ARM_SETWEIGHT:
			if (ob->pose) {
				uiItemPointerR(layout, ptr, "bone", &pose_ptr, "bones", NULL, ICON_BONE_DATA);

				if (RNA_property_collection_lookup_string(&pose_ptr, bones_prop, aa->posechannel, &pchan_ptr))
					uiItemPointerR(layout, ptr, "constraint", &pchan_ptr, "constraints", NULL, ICON_CONSTRAINT_BONE);
			}

			uiItemR(layout, ptr, "weight", 0, NULL, ICON_NONE);
			break;
		case ACT_ARM_SETINFLUENCE:
			if (ob->pose) {
				uiItemPointerR(layout, ptr, "bone", &pose_ptr, "bones", NULL, ICON_BONE_DATA);

				if (RNA_property_collection_lookup_string(&pose_ptr, bones_prop, aa->posechannel, &pchan_ptr))
					uiItemPointerR(layout, ptr, "constraint", &pchan_ptr, "constraints", NULL, ICON_CONSTRAINT_BONE);
			}

			uiItemR(layout, ptr, "influence", 0, NULL, ICON_NONE);
			break;
	}
}

static void draw_actuator_camera(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;
	uiItemR(layout, ptr, "object", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "height", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "axis", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, true);
	uiItemR(row, ptr, "min", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "max", 0, NULL, ICON_NONE);

	uiItemR(layout, ptr, "damping", 0, NULL, ICON_NONE);
}

static void draw_actuator_constraint(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *row, *col, *sub, *split;
	PointerRNA main_ptr;

	RNA_main_pointer_create(CTX_data_main(C), &main_ptr);

	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);
	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_CONST_TYPE_LOC:
			uiItemR(layout, ptr, "limit", 0, NULL, ICON_NONE);

			row = uiLayoutRow(layout, true);
			uiItemR(row, ptr, "limit_min", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "limit_max", 0, NULL, ICON_NONE);

			uiItemR(layout, ptr, "damping", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			break;

		case ACT_CONST_TYPE_DIST:
			split = uiLayoutSplit(layout, 0.8, false);
			uiItemR(split, ptr, "direction", 0, NULL, ICON_NONE);
			row = uiLayoutRow(split, true);
			uiItemR(row, ptr, "use_local", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			uiItemR(row, ptr, "use_normal", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			row = uiLayoutRow(layout, false);
			col = uiLayoutColumn(row, true);
			uiItemL(col, IFACE_("Range:"), ICON_NONE);
			uiItemR(col, ptr, "range", 0, "", ICON_NONE);

			col = uiLayoutColumn(row, true);
			uiItemR(col, ptr, "use_force_distance", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			sub = uiLayoutColumn(col, false);
			uiLayoutSetActive(sub, RNA_boolean_get(ptr, "use_force_distance") == true);
			uiItemR(sub, ptr, "distance", 0, "", ICON_NONE);

			uiItemR(layout, ptr, "damping", UI_ITEM_R_SLIDER, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.15f, false);
			uiItemR(split, ptr, "use_material_detect", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			if (RNA_boolean_get(ptr, "use_material_detect"))
				uiItemPointerR(split, ptr, "material", &main_ptr, "materials", NULL, ICON_MATERIAL_DATA);
			else
				uiItemR(split, ptr, "property", 0, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.15, false);
			uiItemR(split, ptr, "use_persistent", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			row = uiLayoutRow(split, true);
			uiItemR(row, ptr, "time", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "damping_rotation", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			break;

		case ACT_CONST_TYPE_ORI:
			uiItemR(layout, ptr, "direction_axis_pos", 0, NULL, ICON_NONE);

			row=uiLayoutRow(layout, true);
			uiItemR(row, ptr, "damping", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			uiItemR(row, ptr, "time", 0, NULL, ICON_NONE);

			row=uiLayoutRow(layout, false);
			uiItemR(row, ptr, "rotation_max", 0, NULL, ICON_NONE);

			row=uiLayoutRow(layout, true);
			uiItemR(row, ptr, "angle_min", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "angle_max", 0, NULL, ICON_NONE);
			break;

		case ACT_CONST_TYPE_FH:
			split = uiLayoutSplit(layout, 0.75, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "fh_damping", UI_ITEM_R_SLIDER, NULL, ICON_NONE);

			uiItemR(row, ptr, "fh_height", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_fh_paralel_axis", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "direction_axis", 0, NULL, ICON_NONE);
			split = uiLayoutSplit(row, 0.9f, false);
			uiItemR(split, ptr, "fh_force", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_fh_normal", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.15, false);
			uiItemR(split, ptr, "use_material_detect", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			if (RNA_boolean_get(ptr, "use_material_detect"))
				uiItemPointerR(split, ptr, "material", &main_ptr, "materials", NULL, ICON_MATERIAL_DATA);
			else
				uiItemR(split, ptr, "property", 0, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.15, false);
			uiItemR(split, ptr, "use_persistent", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "time", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "damping_rotation", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			break;
	}
}

static void draw_actuator_edit_object(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob = (Object *)ptr->id.data;
	uiLayout *row, *split, *sub;
	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_EDOB_ADD_OBJECT:
			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "object", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "time", 0, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "linear_velocity", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_local_linear_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "angular_velocity", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_local_angular_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			break;
		case ACT_EDOB_END_OBJECT:
			break;
		case ACT_EDOB_REPLACE_MESH:
			if (ob->type != OB_MESH) {
				uiItemL(layout, IFACE_("Mode only available for mesh objects"), ICON_NONE);
				break;
			}
			split = uiLayoutSplit(layout, 0.6, false);
			uiItemR(split, ptr, "mesh", 0, NULL, ICON_NONE);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "use_replace_display_mesh", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			uiItemR(row, ptr, "use_replace_physics_mesh", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			break;
		case ACT_EDOB_TRACK_TO:
			split = uiLayoutSplit(layout, 0.5, false);
			uiItemR(split, ptr, "track_object", 0, NULL, ICON_NONE);
			sub = uiLayoutSplit(split, 0.7f, false);
			uiItemR(sub, ptr, "time", 0, NULL, ICON_NONE);
			uiItemR(sub, ptr, "use_3d_tracking", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "up_axis", 0, NULL, ICON_NONE);

			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "track_axis", 0, NULL, ICON_NONE);
			break;
		case ACT_EDOB_DYNAMICS:
			if (ob->type != OB_MESH) {
				uiItemL(layout, IFACE_("Mode only available for mesh objects"), ICON_NONE);
				break;
			}
			uiItemR(layout, ptr, "dynamic_operation", 0, NULL, ICON_NONE);
			if (RNA_enum_get(ptr, "dynamic_operation") == ACT_EDOB_SET_MASS)
				uiItemR(layout, ptr, "mass", 0, NULL, ICON_NONE);
			break;
		case ACT_EDOB_CHANGE_COLOR:
			row = uiLayoutRow(layout, true);
			uiItemR(row, ptr, "use_lerp_col", 0, NULL, ICON_NONE);

			row = uiLayoutRow(row, true);
			uiLayoutSetActive(row, RNA_boolean_get(ptr, "use_lerp_col"));
			uiItemR(row, ptr, "lerp_col", 0, NULL, ICON_NONE);

			row = uiLayoutRow(layout, true);
			uiItemR(row, ptr, "change_col", 0, NULL, ICON_NONE);
			break;
	}
}

static void draw_actuator_filter_2d(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row, *split;

	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);
	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_2DFILTER_CUSTOMFILTER:
			uiItemR(layout, ptr, "filter_pass", 0, NULL, ICON_NONE);
			uiItemR(layout, ptr, "glsl_shader", 0, NULL, ICON_NONE);
			uiItemR(layout, ptr, "use_mipmap", 0, NULL, ICON_NONE);
			break;
		case ACT_2DFILTER_MOTIONBLUR:
			split=uiLayoutSplit(layout, 0.75f, true);
			row = uiLayoutRow(split, false);
			uiLayoutSetActive(row, RNA_boolean_get(ptr, "use_motion_blur") == true);
			uiItemR(row, ptr, "motion_blur_factor", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_motion_blur", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			break;
		case ACT_2DFILTER_SSAO:
		case ACT_2DFILTER_BLOOM:
		case ACT_2DFILTER_TONEMAP:
		case ACT_2DFILTER_LIGHTSCATTER:
		case ACT_2DFILTER_SSR:
		case ACT_2DFILTER_FXAA:
			uiItemL(layout, "Uses the scene post-processing defaults.", ICON_INFO);
			break;
		default: // all other 2D Filters
			uiItemR(layout, ptr, "filter_pass", 0, NULL, ICON_NONE);
			break;
	}
}

static void draw_actuator_game(uiLayout *layout, PointerRNA *ptr)
{
	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);
  if (ELEM(RNA_enum_get(ptr, "mode"), ACT_GAME_LOAD, ACT_GAME_SCREENSHOT)) {
    uiItemR(layout, ptr, "filename", 0, NULL, ICON_NONE);
  }

  if (ELEM(RNA_enum_get(ptr, "mode"), ACT_GAME_SAVECFG, ACT_GAME_LOADCFG)) {
    uiItemR(layout, ptr, "saveloc", 0, NULL, ICON_NONE);
    uiItemR(layout, ptr, "extension_name", 0, NULL, ICON_NONE);
  }
		
}

static void draw_actuator_message(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	Object *ob;
	PointerRNA main_ptr, settings_ptr;
	uiLayout *row;

	RNA_main_pointer_create(CTX_data_main(C), &main_ptr);

	ob = (Object *)ptr->id.data;
	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);

	uiItemPointerR(layout, ptr, "to_property", &main_ptr, "objects", NULL, ICON_OBJECT_DATA);
	uiItemR(layout, ptr, "subject", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, true);
	uiItemR(row, ptr, "body_type", 0, NULL, ICON_NONE);

	if (RNA_enum_get(ptr, "body_type") == ACT_MESG_MESG)
		uiItemR(row, ptr, "body_message", 0, "", ICON_NONE);
	else // mode == ACT_MESG_PROP
		uiItemPointerR(row, ptr, "body_property", &settings_ptr, "properties", "", ICON_NONE);
}

static void draw_actuator_motion(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob;
	PointerRNA settings_ptr;
	uiLayout *split, *row, *col, *sub;
	int physics_type;
	bool angular;

	ob = (Object *)ptr->id.data;
	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);
	physics_type = RNA_enum_get(&settings_ptr, "physics_type");
	angular = (RNA_enum_get(ptr, "servo_mode") == ACT_SERVO_ANGULAR);
	
	uiItemR(layout, ptr, "mode", 0, NULL, ICON_PREFERENCES);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_OBJECT_NORMAL:
			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "offset_location", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_local_location", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "offset_rotation", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_local_rotation", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			if (ELEM(physics_type, OB_BODY_TYPE_DYNAMIC, OB_BODY_TYPE_RIGID, OB_BODY_TYPE_SOFT)) {
				uiItemL(layout, IFACE_("Dynamic Object Settings:"), ICON_NONE);
				split = uiLayoutSplit(layout, 0.9, false);
				row = uiLayoutRow(split, false);
				uiItemR(row, ptr, "force", 0, NULL, ICON_NONE);
				uiItemR(split, ptr, "use_local_force", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

				split = uiLayoutSplit(layout, 0.9, false);
				row = uiLayoutRow(split, false);
				uiItemR(row, ptr, "torque", 0, NULL, ICON_NONE);
				uiItemR(split, ptr, "use_local_torque", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

				split = uiLayoutSplit(layout, 0.9, false);
				row = uiLayoutRow(split, false);
				uiItemR(row, ptr, "linear_velocity", 0, NULL, ICON_NONE);
				row = uiLayoutRow(split, true);
				uiItemR(row, ptr, "use_local_linear_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
				uiItemR(row, ptr, "use_add_linear_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

				split = uiLayoutSplit(layout, 0.9, false);
				row = uiLayoutRow(split, false);
				uiItemR(row, ptr, "angular_velocity", 0, NULL, ICON_NONE);
				uiItemR(split, ptr, "use_local_angular_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

				uiItemR(layout, ptr, "damping", 0, NULL, ICON_NONE);
			}
			break;
		case ACT_OBJECT_SERVO:
			uiItemR(layout, ptr, "reference_object", 0, NULL, ICON_NONE);

			uiItemR(layout, ptr, "servo_mode", 0, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			if (angular) {
				uiItemR(row, ptr, "angular_velocity", 0, NULL, ICON_NONE);
				uiItemR(split, ptr, "use_local_angular_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			}
			else {
				uiItemR(row, ptr, "linear_velocity", 0, NULL, ICON_NONE);
				uiItemR(split, ptr, "use_local_linear_velocity", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			}

			row = uiLayoutRow(layout, false);
			col = uiLayoutColumn(row, false);
			uiItemR(col, ptr, "use_servo_limit_x", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			sub = uiLayoutColumn(col, true);
			uiLayoutSetActive(sub, RNA_boolean_get(ptr, "use_servo_limit_x") == true);
			uiItemR(sub, ptr, "force_max_x", 0, NULL, ICON_NONE);
			uiItemR(sub, ptr, "force_min_x", 0, NULL, ICON_NONE);

			col = uiLayoutColumn(row, false);
			uiItemR(col, ptr, "use_servo_limit_y", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			sub = uiLayoutColumn(col, true);
			uiLayoutSetActive(sub, RNA_boolean_get(ptr, "use_servo_limit_y") == true);
			uiItemR(sub, ptr, "force_max_y", 0, NULL, ICON_NONE);
			uiItemR(sub, ptr, "force_min_y", 0, NULL, ICON_NONE);

			col = uiLayoutColumn(row, false);
			uiItemR(col, ptr, "use_servo_limit_z", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			sub = uiLayoutColumn(col, true);
			uiLayoutSetActive(sub, RNA_boolean_get(ptr, "use_servo_limit_z") == true);
			uiItemR(sub, ptr, "force_max_z", 0, NULL, ICON_NONE);
			uiItemR(sub, ptr, "force_min_z", 0, NULL, ICON_NONE);

			//XXXACTUATOR missing labels from original 2.49 ui (e.g. Servo, Min, Max, Fast)
			//Layout designers willing to help on that, please compare with 2.49 ui
			// (since the old code is going to be deleted ... soon)

			col = uiLayoutColumn(layout, true);
			uiItemR(col, ptr, "proportional_coefficient", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			uiItemR(col, ptr, "integral_coefficient", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			uiItemR(col, ptr, "derivate_coefficient", UI_ITEM_R_SLIDER, NULL, ICON_NONE);
			break;
		case ACT_OBJECT_CHARACTER:
			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "offset_location", 0, NULL, ICON_NONE);
			row = uiLayoutRow(split, true);
			uiItemR(row, ptr, "use_local_location", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			uiItemR(row, ptr, "use_add_character_location", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "offset_rotation", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_local_rotation", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);

			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			split = uiLayoutSplit(row, 0.7, false);
			uiItemL(split, "", ICON_NONE); /*Just use this for some spacing */
			uiItemR(split, ptr, "use_character_jump", UI_ITEM_R_TOGGLE, NULL, ICON_POSE_DATA);
			break;
		case ACT_OBJECT_NORMAL_SET:
			split = uiLayoutSplit(layout, 0.9, false);
			row = uiLayoutRow(split, false);
			uiItemR(row, ptr, "offset_location", 0, NULL, ICON_NONE);
			uiItemR(split, ptr, "use_local_location", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
	}
}

static void draw_actuator_parent(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row, *sub;

	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);

	if (RNA_enum_get(ptr, "mode") == ACT_PARENT_SET) {
		uiItemR(layout, ptr, "object", 0, NULL, ICON_NONE);

		row = uiLayoutRow(layout, false);
		uiItemR(row, ptr, "use_compound", 0, NULL, ICON_NONE);
		sub = uiLayoutRow(row, false);
		uiLayoutSetActive(sub, RNA_boolean_get(ptr, "use_compound") == true);
		uiItemR(sub, ptr, "use_ghost", 0, NULL, ICON_NONE);
	}
}

static void draw_actuator_property(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	Object *ob = (Object *)ptr->id.data;
	bActuator *act = (bActuator *)ptr->data;
	bPropertyActuator *pa = (bPropertyActuator *) act->data;
	Object *ob_from= pa->ob;
	World *world = CTX_data_scene(C)->world;
	PointerRNA settings_ptr, obj_settings_ptr;
	const int actuator_mode = RNA_enum_get(ptr, "actuator_mode");

	uiLayout *row, *sub;

	if ((RNA_boolean_get(ptr, "use_world_property") || actuator_mode == 3) && world)
		RNA_id_pointer_create((ID *)world, &settings_ptr);
	else
		RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);

	uiItemR(layout, ptr, "actuator_mode", 0, NULL, ICON_NONE);
	if (actuator_mode == 1 || actuator_mode == 2) {
		uiLayout *runtime_box = uiLayoutBox(layout);
		const int runtime_property = RNA_enum_get(ptr, "runtime_property");
		if (actuator_mode == 1) {
			uiItemL(runtime_box, "Runtime API", ICON_INFO);
			uiItemR(runtime_box, ptr, "object", 0, "Target (empty = self)", ICON_NONE);
			uiItemR(runtime_box, ptr, "runtime_property", 0, "Exposed Property", ICON_NONE);
		}
		else {
			const int weather_category = RNA_enum_get(ptr, "weather_category");
			uiItemR(runtime_box, ptr, "weather_category", 0, NULL, ICON_NONE);
			if (weather_category == 1)
				uiItemR(runtime_box, ptr, "cloud_effect", 0, "Property", ICON_NONE);
			else if (weather_category == 2)
				uiItemR(runtime_box, ptr, "lens_flare_effect", 0, "Property", ICON_NONE);
			else if (weather_category == 3)
				uiItemR(runtime_box, ptr, "mist_effect", 0, "Property", ICON_NONE);
			else
				uiItemR(runtime_box, ptr, "weather_effect", 0, "Property", ICON_NONE);
		}
		uiItemR(runtime_box, ptr, "mode", 0, NULL, ICON_NONE);
		if (runtime_property == ACT_RUNTIME_PROP_VISIBLE ||
		    runtime_property == ACT_RUNTIME_PROP_WEATHER_RAIN ||
		    runtime_property == ACT_RUNTIME_PROP_WEATHER_RIPPLES ||
		    runtime_property == ACT_RUNTIME_PROP_WEATHER_CLOUDS ||
		    runtime_property == ACT_RUNTIME_PROP_WEATHER_LENS_FLARE ||
		    runtime_property == ACT_RUNTIME_PROP_WEATHER_MIST) {
			uiItemL(runtime_box, actuator_mode == 2 ?
			        "Category: Weather  |  Type: Boolean" : "Category: Render  |  Type: Boolean", ICON_NONE);
			uiItemR(runtime_box, ptr, "runtime_bool_value", 0, NULL, ICON_NONE);
		}
		else if (runtime_property == ACT_RUNTIME_PROP_MASS ||
		         runtime_property >= ACT_RUNTIME_PROP_WEATHER_RAIN_INTENSITY) {
			uiItemL(runtime_box, actuator_mode == 2 ?
			        "Category: Weather  |  Type: Float" : "Category: Physics  |  Type: Float", ICON_NONE);
			uiItemR(runtime_box, ptr, "runtime_value", 0, "Value", ICON_NONE);
		}
		else if (actuator_mode == 2) {
			/* Weather controls are Boolean or scalar Float, never Vector3. */
			uiItemL(runtime_box, "Category: Weather  |  Type: Float", ICON_NONE);
			uiItemR(runtime_box, ptr, "runtime_value", 0, "Value", ICON_NONE);
		}
		else {
			if (RNA_enum_get(ptr, "runtime_property") == ACT_RUNTIME_PROP_LOCAL_POSITION ||
			    RNA_enum_get(ptr, "runtime_property") == ACT_RUNTIME_PROP_LOCAL_SCALE) {
				uiItemL(runtime_box, "Category: Transform  |  Type: Vector3", ICON_NONE);
			}
			else {
				uiItemL(runtime_box, "Category: Physics  |  Type: Vector3", ICON_NONE);
			}
			uiItemR(runtime_box, ptr, "runtime_value", 0, NULL, ICON_NONE);
		}
		return;
	}

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "mode", 0, NULL, ICON_NONE);

	if ((RNA_boolean_get(ptr, "use_world_property") || actuator_mode == 3) && !world)
		uiItemL(layout, "No World in this scene", ICON_ERROR);
	else
		uiItemPointerR(layout, ptr, "property", &settings_ptr, "properties", NULL, ICON_NONE);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_PROP_TOGGLE:
		case ACT_PROP_LEVEL:
			break;
		case ACT_PROP_ADD:
			uiItemR(layout, ptr, "value", 0, NULL, ICON_NONE);
			break;
		case ACT_PROP_ASSIGN:
			uiItemR(layout, ptr, "value", 0, NULL, ICON_NONE);
			break;
		case ACT_PROP_COPY:
			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "object", 0, NULL, ICON_NONE);
			if (ob_from) {
				RNA_pointer_create((ID *)ob_from, &RNA_GameObjectSettings, ob_from, &obj_settings_ptr);
				uiItemPointerR(row, ptr, "object_property", &obj_settings_ptr, "properties", NULL, ICON_NONE);
			}
			else {
				sub = uiLayoutRow(row, false);
				uiLayoutSetActive(sub, false);
				uiItemR(sub, ptr, "object_property", 0, NULL, ICON_NONE);
			}
			break;
	}
}

static void draw_actuator_random(uiLayout *layout, PointerRNA *ptr)
{
	Object *ob;
	PointerRNA settings_ptr;
	uiLayout *row;

	ob = (Object *)ptr->id.data;
	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);

	row = uiLayoutRow(layout, false);

	uiItemR(row, ptr, "seed", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "distribution", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemPointerR(row, ptr, "property", &settings_ptr, "properties", NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);

	switch (RNA_enum_get(ptr, "distribution")) {
		case ACT_RANDOM_BOOL_CONST:
			uiItemR(row, ptr, "use_always_true", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_BOOL_UNIFORM:
			uiItemL(row, IFACE_("Choose between true and false, 50% chance each"), ICON_NONE);
			break;

		case ACT_RANDOM_BOOL_BERNOUILLI:
			uiItemR(row, ptr, "chance", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_INT_CONST:
			uiItemR(row, ptr, "int_value", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_INT_UNIFORM:
			uiItemR(row, ptr, "int_min", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "int_max", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_INT_POISSON:
			uiItemR(row, ptr, "int_mean", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_FLOAT_CONST:
			uiItemR(row, ptr, "float_value", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_FLOAT_UNIFORM:
			uiItemR(row, ptr, "float_min", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "float_max", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_FLOAT_NORMAL:
			uiItemR(row, ptr, "float_mean", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "standard_derivation", 0, NULL, ICON_NONE);
			break;

		case ACT_RANDOM_FLOAT_NEGATIVE_EXPONENTIAL:
			uiItemR(row, ptr, "half_life_time", 0, NULL, ICON_NONE);
			break;
	}
}

static void draw_actuator_scene(uiLayout *layout, PointerRNA *ptr)
{
	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_SCENE_CAMERA:
			uiItemR(layout, ptr, "camera", 0, NULL, ICON_NONE);
			break;
		case ACT_SCENE_RESTART:
			break;
		default: // ACT_SCENE_SET|ACT_SCENE_ADD_FRONT|ACT_SCENE_ADD_BACK|ACT_SCENE_REMOVE|ACT_SCENE_SUSPEND|ACT_SCENE_RESUME
			uiItemR(layout, ptr, "scene", 0, NULL, ICON_NONE);
			break;
	}
}

static void draw_actuator_sound(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *row, *col;

	uiTemplateID(layout, C, ptr, "sound", NULL, "SOUND_OT_open", NULL, UI_TEMPLATE_ID_FILTER_ALL);
	if (!RNA_pointer_get(ptr, "sound").data) {
		uiItemL(layout, IFACE_("Select a sound from the list or load a new one"), ICON_NONE);
		return;
	}
	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "volume", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "pitch", 0, NULL, ICON_NONE);

	uiItemR(layout, ptr, "use_sound_3d", 0, NULL, ICON_NONE);

	col = uiLayoutColumn(layout, false);
	uiLayoutSetActive(col, RNA_boolean_get(ptr, "use_sound_3d") == true);

	row = uiLayoutRow(col, false);
	uiItemR(row, ptr, "gain_3d_min", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "gain_3d_max", 0, NULL, ICON_NONE);

	row = uiLayoutRow(col, false);
	uiItemR(row, ptr, "distance_3d_reference", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "distance_3d_max", 0, NULL, ICON_NONE);

	row = uiLayoutRow(col, false);
	uiItemR(row, ptr, "rolloff_factor_3d", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "cone_outer_gain_3d", 0, NULL, ICON_NONE);

	row = uiLayoutRow(col, false);
	uiItemR(row, ptr, "cone_outer_angle_3d", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "cone_inner_angle_3d", 0, NULL, ICON_NONE);
}

static void draw_actuator_state(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *split;
	Object *ob = (Object *)ptr->id.data;
	PointerRNA settings_ptr;
	RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);

	split = uiLayoutSplit(layout, 0.35, false);
	uiItemR(split, ptr, "operation", 0, NULL, ICON_NONE);

	uiTemplateLayers(split, ptr, "states", &settings_ptr, "used_states", 0);
}

static void draw_actuator_vibration(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;
	row = uiLayoutRow(layout, false);

	uiItemR(layout, ptr, "mode", 0, NULL, 0);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_VIBRATION_PLAY:
		{
			uiItemR(row, ptr, "joy_index", 0, NULL, ICON_NONE);
			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "joy_strength_left", 0, NULL, ICON_NONE);
			uiItemR(row, ptr, "joy_strength_right", 0, NULL, ICON_NONE);
			row = uiLayoutRow(layout, false);
			uiItemR(row, ptr, "joy_duration", 0, NULL, ICON_NONE);
			break;
		}
		case ACT_VIBRATION_STOP:
		{
			uiItemR(row, ptr, "joy_index", 0, NULL, ICON_NONE);
			break;
		}
	}
}

static void draw_actuator_visibility(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;
	row = uiLayoutRow(layout, false);

	uiItemR(row, ptr, "use_visible", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "use_occlusion", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "apply_to_children", 0, NULL, ICON_NONE);
}

static void draw_actuator_steering(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row;
	uiLayout *col;

	uiItemR(layout, ptr, "mode", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "target", 0, NULL, ICON_NONE);
	uiItemR(layout, ptr, "navmesh", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "distance", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "velocity", 0, NULL, ICON_NONE);
	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "acceleration", 0, NULL, ICON_NONE);
	uiItemR(row, ptr, "turn_speed", 0, NULL, ICON_NONE);

	row = uiLayoutRow(layout, false);
	col = uiLayoutColumn(row, false);
	uiItemR(col, ptr, "facing", 0, NULL, ICON_NONE);
	col = uiLayoutColumn(row, false);
	uiItemR(col, ptr, "facing_axis", 0, NULL, ICON_NONE);
	if (!RNA_boolean_get(ptr, "facing")) {
		uiLayoutSetActive(col, false);
	}
	col = uiLayoutColumn(row, false);
	uiItemR(col, ptr, "normal_up", 0, NULL, ICON_NONE);
	if (!RNA_pointer_get(ptr, "navmesh").data) {
		uiLayoutSetActive(col, false);
	}

	row = uiLayoutRow(layout, false);
	col = uiLayoutColumn(row, false);
	uiItemR(col, ptr, "self_terminated", 0, NULL, ICON_NONE);
	if (RNA_enum_get(ptr, "mode")==ACT_STEERING_PATHFOLLOWING) {
		col = uiLayoutColumn(row, false);
		uiItemR(col, ptr, "update_period", 0, NULL, ICON_NONE);
	}
	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "lock_z_velocity", 1, NULL, ICON_NONE);
	row = uiLayoutRow(layout, false);
	uiItemR(row, ptr, "show_visualization", 0, NULL, ICON_NONE);
	if (RNA_enum_get(ptr, "mode") != ACT_STEERING_PATHFOLLOWING) {
		uiLayoutSetActive(row, false);
	}
}

static void draw_actuator_mouse(uiLayout *layout, PointerRNA *ptr)
{
	uiLayout *row, *col, *subcol, *split, *subsplit;

	uiItemR(layout, ptr, "mode", 0, NULL, 0);

	switch (RNA_enum_get(ptr, "mode")) {
		case ACT_MOUSE_VISIBILITY:
			row = uiLayoutRow(layout, 0);
			uiItemR(row, ptr, "visible", UI_ITEM_R_TOGGLE, NULL, 0);
			break;

		case ACT_MOUSE_LOOK:
			/* X axis */
			row = uiLayoutRow(layout, 0);
			col = uiLayoutColumn(row, 1);

			uiItemR(col, ptr, "use_axis_x", UI_ITEM_R_TOGGLE, NULL, 0);

			subcol = uiLayoutColumn(col, 1);
			uiLayoutSetActive(subcol, RNA_boolean_get(ptr, "use_axis_x")==1);
			uiItemR(subcol, ptr, "sensitivity_x", 0, NULL, 0);
			uiItemR(subcol, ptr, "threshold_x", 0, NULL, 0);

			uiItemR(subcol, ptr, "min_x", 0, NULL, 0);
			uiItemR(subcol, ptr, "max_x", 0, NULL, 0);

			uiItemR(subcol, ptr, "object_axis_x", 0, NULL, 0);

			/* Y Axis */
			col = uiLayoutColumn(row, 1);

			uiItemR(col, ptr, "use_axis_y", UI_ITEM_R_TOGGLE, NULL, 0);

			subcol = uiLayoutColumn(col, 1);
			uiLayoutSetActive(subcol, RNA_boolean_get(ptr, "use_axis_y")==1);
			uiItemR(subcol, ptr, "sensitivity_y", 0, NULL, 0);
			uiItemR(subcol, ptr, "threshold_y", 0, NULL, 0);

			uiItemR(subcol, ptr, "min_y", 0, NULL, 0);
			uiItemR(subcol, ptr, "max_y", 0, NULL, 0);

			uiItemR(subcol, ptr, "object_axis_y", 0, NULL, 0);

			/* Lower options */
			row = uiLayoutRow(layout, 0);
			split = uiLayoutSplit(row, 0.5, 0);

			subsplit = uiLayoutSplit(split, 0.5, 1);
			uiLayoutSetActive(subsplit, RNA_boolean_get(ptr, "use_axis_x")==1);
			uiItemR(subsplit, ptr, "local_x", UI_ITEM_R_TOGGLE, NULL, 0);
			uiItemR(subsplit, ptr, "reset_x", UI_ITEM_R_TOGGLE, NULL, 0);

			subsplit = uiLayoutSplit(split, 0.5, 1);
			uiLayoutSetActive(subsplit, RNA_boolean_get(ptr, "use_axis_y")==1);
			uiItemR(subsplit, ptr, "local_y", UI_ITEM_R_TOGGLE, NULL, 0);
			uiItemR(subsplit, ptr, "reset_y", UI_ITEM_R_TOGGLE, NULL, 0);

			break;
	}
}

static void draw_brick_actuator(uiLayout *layout, PointerRNA *ptr, bContext *C)
{
	uiLayout *box;

	if (!RNA_boolean_get(ptr, "show_expanded"))
		return;

	box = uiLayoutBox(layout);
	uiLayoutSetActive(box, RNA_boolean_get(ptr, "active"));

	switch (RNA_enum_get(ptr, "type")) {
		case ACT_ACTION:
			draw_actuator_action(box, ptr);
			break;
		case ACT_ARMATURE:
			draw_actuator_armature(box, ptr);
			break;
		case ACT_CAMERA:
			draw_actuator_camera(box, ptr);
			break;
		case ACT_CONSTRAINT:
			draw_actuator_constraint(box, ptr, C);
			break;
		case ACT_EDIT_OBJECT:
			draw_actuator_edit_object(box, ptr);
			break;
		case ACT_2DFILTER:
			draw_actuator_filter_2d(box, ptr);
			break;
		case ACT_GAME:
			draw_actuator_game(box, ptr);
			break;
		case ACT_MESSAGE:
			draw_actuator_message(box, ptr, C);
			break;
		case ACT_OBJECT:
			draw_actuator_motion(box, ptr);
			break;
		case ACT_PARENT:
			draw_actuator_parent(box, ptr);
			break;
		case ACT_PROPERTY:
			draw_actuator_property(box, ptr, C);
			break;
		case ACT_RANDOM:
			draw_actuator_random(box, ptr);
			break;
		case ACT_SCENE:
			draw_actuator_scene(box, ptr);
			break;
		case ACT_SOUND:
			draw_actuator_sound(box, ptr, C);
			break;
		case ACT_STATE:
			draw_actuator_state(box, ptr);
			break;
		case ACT_VIBRATION:
			draw_actuator_vibration(box, ptr);
			break;
		case ACT_VISIBILITY:
			draw_actuator_visibility(box, ptr);
			break;
		case ACT_STEERING:
			draw_actuator_steering(box, ptr);
			break;
		case ACT_MOUSE:
			draw_actuator_mouse(box, ptr);
			break;
	}
}

void logic_buttons(bContext *C, ARegion *ar)
{
	SpaceLogic *slogic= CTX_wm_space_logic(C);
	Object *ob= CTX_data_active_object(C);
	ID **idar;
	PointerRNA logic_ptr, settings_ptr, object_ptr;
	uiLayout *layout, *row, *box;
	uiBlock *block;
	uiBut *but;
	char uiblockstr[32];
	short a, count;
	int xco, yco, width, height;

	if (ob==NULL) return;

	RNA_pointer_create(NULL, &RNA_SpaceLogicEditor, slogic, &logic_ptr);
	idar= get_selected_and_linked_obs(C, &count, slogic->scaflag);

	BLI_snprintf(uiblockstr, sizeof(uiblockstr), "buttonswin %p", (void *)ar);
	block= UI_block_begin(C, ar, uiblockstr, UI_EMBOSS);
	UI_block_func_handle_set(block, do_logic_buts, NULL);
	UI_block_bounds_set_normal(block, U.widget_unit/2);

	/* loop over all objects and set visible/linked flags for the logic bricks */
	for (a=0; a<count; a++) {
		bActuator *act;
		bSensor *sens;
		bController *cont;
		int iact;
		short flag;

		ob= (Object *)idar[a];

		/* clean ACT_LINKED and ACT_VISIBLE of all potentially visible actuators so that we can determine which is actually linked/visible */
		act = ob->actuators.first;
		while (act) {
			act->flag &= ~(ACT_LINKED|ACT_VISIBLE);
			act = act->next;
		}
		/* same for sensors */
		sens= ob->sensors.first;
		while (sens) {
			sens->flag &= ~(SENS_VISIBLE);
			sens = sens->next;
		}

		/* mark the linked and visible actuators */
		cont= ob->controllers.first;
		while (cont) {
			flag = ACT_LINKED;

			/* this controller is visible, mark all its actuator */
			if ((ob->scaflag & OB_ALLSTATE) || (ob->state & cont->state_mask)) {
				flag |= ACT_VISIBLE;
			}

			for (iact=0; iact<cont->totlinks; iact++) {
				act = cont->links[iact];
				if (act)
					act->flag |= flag;
			}
			cont = cont->next;
		}
	}

	/* ****************** Controllers ****************** */

	xco= 21 * U.widget_unit; yco= - U.widget_unit / 2; width= 15 * U.widget_unit;
	layout= UI_block_layout(block, UI_LAYOUT_VERTICAL, UI_LAYOUT_PANEL, xco, yco, width, 20, 0, UI_style_get());
	row = uiLayoutRow(layout, true);

	uiDefBlockBut(block, controller_menu, NULL, IFACE_("Controllers"), xco - U.widget_unit / 2, yco, width, UI_UNIT_Y, "");		/* replace this with uiLayout stuff later */

	uiItemR(row, &logic_ptr, "show_controllers_selected_objects", 0, IFACE_("Sel"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_controllers_active_object", 0, IFACE_("Act"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_controllers_linked_controller", 0, IFACE_("Link"), ICON_NONE);
	
	for (a = 0; a < count; a++) {
		bController *cont;
		PointerRNA ptr;
		uiLayout *split, *subsplit, *col;


		ob= (Object *)idar[a];

		/* only draw the controller common header if "use_visible" */
		if ( (ob->scavisflag & OB_VIS_CONT) == 0) {
			continue;
		}

		/* Drawing the Controller Header common to all Selected Objects */

		RNA_pointer_create((ID *)ob, &RNA_GameObjectSettings, ob, &settings_ptr);

		split = uiLayoutSplit(layout, 0.05f, false);
		uiItemR(split, &settings_ptr, "show_state_panel", UI_ITEM_R_NO_BG, "", ICON_RIGHTARROW);
		
		row = uiLayoutRow(split, true);
		uiDefButBitS(block, UI_BTYPE_TOGGLE, OB_SHOWCONT, B_REDR, ob->id.name + 2, (short)(xco - U.widget_unit / 2), yco, (short)(width - 1.5f * U.widget_unit), UI_UNIT_Y, &ob->scaflag, 0, 31, 0, 0, TIP_("Object name, click to show/hide controllers"));

		RNA_pointer_create((ID *)ob, &RNA_Object, ob, &object_ptr);
		uiLayoutSetContextPointer(row, "object", &object_ptr);
		uiItemMenuEnumO(row, C, "LOGIC_OT_controller_add", "type", IFACE_("Add Controller"), ICON_CONSTRAINT);

		if (RNA_boolean_get(&settings_ptr, "show_state_panel")) {

			box = uiLayoutBox(layout);
			split = uiLayoutSplit(box, 0.2f, false);

			col = uiLayoutColumn(split, false);
			uiItemL(col, IFACE_("Visible"), ICON_NONE);
			uiItemL(col, IFACE_("Initial"), ICON_NONE);

			subsplit = uiLayoutSplit(split, 0.85f, false);
			col = uiLayoutColumn(subsplit, false);
			row = uiLayoutRow(col, false);
			uiLayoutSetActive(row, RNA_boolean_get(&settings_ptr, "use_all_states") == false);
			uiTemplateGameStates(row, &settings_ptr, "states_visible", &settings_ptr, "used_states", 0);
			row = uiLayoutRow(col, false);
			uiTemplateGameStates(row, &settings_ptr, "states_initial", &settings_ptr, "used_states", 0);

			col = uiLayoutColumn(subsplit, false);
			uiItemR(col, &settings_ptr, "use_all_states", UI_ITEM_R_TOGGLE, NULL, ICON_NONE);
			uiItemR(col, &settings_ptr, "show_debug_state", 0, "", ICON_NONE);
		}

		/* End of Drawing the Controller Header common to all Selected Objects */

		if ((ob->scaflag & OB_SHOWCONT) == 0) continue;


		uiItemS(layout);

		for (cont= ob->controllers.first; cont; cont=cont->next) {
			RNA_pointer_create((ID *)ob, &RNA_Controller, cont, &ptr);

			if (!(ob->scaflag & OB_ALLSTATE) && !(ob->state & cont->state_mask))
				continue;

			/* use two nested splits to align inlinks/links properly */
			split = uiLayoutSplit(layout, 0.05f, false);

			/* put inlink button to the left */
			col = uiLayoutColumn(split, false);
			uiLayoutSetActive(col, RNA_boolean_get(&ptr, "active"));
			uiLayoutSetAlignment(col, UI_LAYOUT_ALIGN_LEFT);
			but = uiDefIconBut(block, UI_BTYPE_INLINK, 0, ICON_INLINK, 0, 0, UI_UNIT_X, UI_UNIT_Y, cont, LINK_CONTROLLER, 0, 0, 0, "");
			if (!RNA_boolean_get(&ptr, "active")) {
				UI_but_flag_enable(but, UI_BUT_SCA_LINK_GREY);
			}

			//col = uiLayoutColumn(split, true);
			/* nested split for middle and right columns */
			subsplit = uiLayoutSplit(split, 0.95f, false);

			col = uiLayoutColumn(subsplit, true);
			uiLayoutSetContextPointer(col, "controller", &ptr);

			/* should make UI template for controller header.. function will do for now */
//			draw_controller_header(col, &ptr);
			draw_controller_header(col, &ptr, xco, width, yco); //provisory for 2.50 beta

			/* draw the brick contents */
			draw_brick_controller(col, &ptr);

			/* put link button to the right */
			col = uiLayoutColumn(subsplit, false);
			uiLayoutSetActive(col, RNA_boolean_get(&ptr, "active"));
			uiLayoutSetAlignment(col, UI_LAYOUT_ALIGN_LEFT);
			but = uiDefIconBut(block, UI_BTYPE_LINK, 0, ICON_LINK, 0, 0, UI_UNIT_X, UI_UNIT_Y, NULL, 0, 0, 0, 0, "");
			if (!RNA_boolean_get(&ptr, "active")) {
				UI_but_flag_enable(but, UI_BUT_SCA_LINK_GREY);
			}

			// Line color, check if line color is equal to wcol_box.inner, if true, use black line color.
			char line_color[3] = {cont->color[0], cont->color[1], cont->color[2]};
			if (U.themes.first) {
				bTheme *btheme = U.themes.first;

				if (line_color[0] == btheme->tui.wcol_box.inner[0] &&
					line_color[1] == btheme->tui.wcol_box.inner[1] &&
					line_color[2] == btheme->tui.wcol_box.inner[2]) {

					line_color[0] = 0;
					line_color[1] = 0;
					line_color[2] = 0;
				}
			}

			UI_but_link_set(but, NULL, (void ***)&(cont->links), &cont->totlinks, LINK_CONTROLLER, LINK_ACTUATOR, line_color);

			// Set controller color to actuators.
			if (cont->links) {
				for (int i = 0; i < cont->totlinks; i++) {
					if (cont->links[i]) {
						bActuator *act = cont->links[i];
						copy_v3_v3_char(act->color, cont->color);
					}
				}
			}
			// Reset color (We don't know when all links will be removed from it so the color must be constantly received from the sensor).
			if (U.themes.first) {
				bTheme *btheme = U.themes.first;
				copy_v3_v3_char(cont->color, btheme->tui.wcol_box.inner);
			}
		}
	}
	UI_block_layout_resolve(block, NULL, &yco);	/* stores final height in yco */
	height = yco;

	/* ****************** Sensors ****************** */

	xco= U.widget_unit / 2; yco= -U.widget_unit / 2; width= 17 * U.widget_unit;
	layout= UI_block_layout(block, UI_LAYOUT_VERTICAL, UI_LAYOUT_PANEL, xco, yco, width, 20, 0, UI_style_get());
	row = uiLayoutRow(layout, true);

	uiDefBlockBut(block, sensor_menu, NULL, IFACE_("Sensors"), xco - U.widget_unit / 2, yco, 15 * U.widget_unit, UI_UNIT_Y, "");		/* replace this with uiLayout stuff later */

	uiItemR(row, &logic_ptr, "show_sensors_selected_objects", 0, IFACE_("Sel"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_sensors_active_object", 0, IFACE_("Act"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_sensors_linked_controller", 0, IFACE_("Link"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_sensors_active_states", 0, IFACE_("State"), ICON_NONE);

	for (a=0; a<count; a++) {
		bSensor *sens;
		PointerRNA ptr;

		ob= (Object *)idar[a];

		/* only draw the sensor common header if "use_visible" */
		if ((ob->scavisflag & OB_VIS_SENS) == 0) continue;

		row = uiLayoutRow(layout, true);
		uiDefButBitS(block, UI_BTYPE_TOGGLE, OB_SHOWSENS, B_REDR, ob->id.name + 2, (short)(xco - U.widget_unit / 2), yco, (short)(width - 1.5f * U.widget_unit), UI_UNIT_Y, &ob->scaflag, 0, 31, 0, 0, TIP_("Object name, click to show/hide sensors"));

		RNA_pointer_create((ID *)ob, &RNA_Object, ob, &object_ptr);
		uiLayoutSetContextPointer(row, "object", &object_ptr);
		uiItemMenuEnumO(row, C, "LOGIC_OT_sensor_add", "type", IFACE_("Add Sensor"), ICON_OOPS);

		if ((ob->scaflag & OB_SHOWSENS) == 0) continue;

		uiItemS(layout);

		for (sens= ob->sensors.first; sens; sens=sens->next) {
			RNA_pointer_create((ID *)ob, &RNA_Sensor, sens, &ptr);

			if ((ob->scaflag & OB_ALLSTATE) ||
				!(slogic->scaflag & BUTS_SENS_STATE) ||
				(sens->totlinks == 0) ||											/* always display sensor without links so that is can be edited */
				(sens->flag & SENS_PIN && slogic->scaflag & BUTS_SENS_STATE) ||	/* states can hide some sensors, pinned sensors ignore the visible state */
				(is_sensor_linked(block, sens))
				)
			{	// gotta check if the current state is visible or not
				uiLayout *split, *col;

				/* make as visible, for move operator */
				sens->flag |= SENS_VISIBLE;

				split = uiLayoutSplit(layout, 0.95f, false);
				col = uiLayoutColumn(split, true);
				uiLayoutSetContextPointer(col, "sensor", &ptr);

				/* should make UI template for sensor header.. function will do for now */
				draw_sensor_header(col, &ptr, &logic_ptr);

				/* draw the brick contents */
				draw_brick_sensor(col, &ptr, C);

				/* put link button to the right */
				col = uiLayoutColumn(split, false);
				uiLayoutSetActive(col, RNA_boolean_get(&ptr, "active"));
				but = uiDefIconBut(block, UI_BTYPE_LINK, 0, ICON_LINK, 0, 0, UI_UNIT_X, UI_UNIT_Y, NULL, 0, 0, 0, 0, "");
				if (!RNA_boolean_get(&ptr, "active")) {
					UI_but_flag_enable(but, UI_BUT_SCA_LINK_GREY);
				}

				// Line color, check if line color is equal to wcol_box.inner, if true, use black line color.
				char line_color[3] = {sens->color[0], sens->color[1], sens->color[2]};
				if (U.themes.first) {
					bTheme *btheme = U.themes.first;

					if (line_color[0] == btheme->tui.wcol_box.inner[0] &&
						line_color[1] == btheme->tui.wcol_box.inner[1] &&
						line_color[2] == btheme->tui.wcol_box.inner[2]) {

						line_color[0] = 0;
						line_color[1] = 0;
						line_color[2] = 0;
					}
				}

				/* use old-school uiButtons for links for now */
				UI_but_link_set(but, NULL, (void ***)&sens->links, &sens->totlinks, LINK_SENSOR, LINK_CONTROLLER, line_color);

				// Set sensor color to controllers.
				if (sens->links) {
					for (int i = 0; i < sens->totlinks; i++) {
						if (sens->links[i]) {
							bController *cont = sens->links[i];
							copy_v3_v3_char(cont->color, sens->color);
						}
					}
				}

			}
		}
	}
	UI_block_layout_resolve(block, NULL, &yco);	/* stores final height in yco */
	height = MIN2(height, yco);

	/* ****************** Actuators ****************** */

	xco= 40 * U.widget_unit; yco= -U.widget_unit / 2; width= 17 * U.widget_unit;
	layout= UI_block_layout(block, UI_LAYOUT_VERTICAL, UI_LAYOUT_PANEL, xco, yco, width, 20, 0, UI_style_get());
	row = uiLayoutRow(layout, true);

	uiDefBlockBut(block, actuator_menu, NULL, IFACE_("Actuators"), xco - U.widget_unit / 2, yco, 15 * U.widget_unit, UI_UNIT_Y, "");		/* replace this with uiLayout stuff later */

	uiItemR(row, &logic_ptr, "show_actuators_selected_objects", 0, IFACE_("Sel"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_actuators_active_object", 0, IFACE_("Act"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_actuators_linked_controller", 0, IFACE_("Link"), ICON_NONE);
	uiItemR(row, &logic_ptr, "show_actuators_active_states", 0, IFACE_("State"), ICON_NONE);

	for (a=0; a<count; a++) {
		bActuator *act;
		PointerRNA ptr;

		ob= (Object *)idar[a];

		/* only draw the actuator common header if "use_visible" */
		if ((ob->scavisflag & OB_VIS_ACT) == 0) {
			continue;
		}

		row = uiLayoutRow(layout, true);
		uiDefButBitS(block, UI_BTYPE_TOGGLE, OB_SHOWACT, B_REDR, ob->id.name + 2, (short)(xco - U.widget_unit / 2), yco, (short)(width - 1.5f * U.widget_unit), UI_UNIT_Y, &ob->scaflag, 0, 31, 0, 0, TIP_("Object name, click to show/hide actuators"));

		RNA_pointer_create((ID *)ob, &RNA_Object, ob, &object_ptr);
		uiLayoutSetContextPointer(row, "object", &object_ptr);
		uiItemMenuEnumO(row, C, "LOGIC_OT_actuator_add", "type", IFACE_("Add Actuator"), ICON_GAME);

		if ((ob->scaflag & OB_SHOWACT) == 0) continue;

		uiItemS(layout);

		for (act= ob->actuators.first; act; act=act->next) {

			RNA_pointer_create((ID *)ob, &RNA_Actuator, act, &ptr);

			if ((ob->scaflag & OB_ALLSTATE) ||
				!(slogic->scaflag & BUTS_ACT_STATE) ||
				!(act->flag & ACT_LINKED) ||		/* always display actuators without links so that is can be edited */
				(act->flag & ACT_VISIBLE) ||		/* this actuator has visible connection, display it */
				(act->flag & ACT_PIN && slogic->scaflag & BUTS_ACT_STATE)	/* states can hide some sensors, pinned sensors ignore the visible state */
				)
			{	// gotta check if the current state is visible or not
				uiLayout *split, *col;

				/* make as visible, for move operator */
				act->flag |= ACT_VISIBLE;

				split = uiLayoutSplit(layout, 0.05f, false);

				/* put inlink button to the left */
				col = uiLayoutColumn(split, false);
				uiLayoutSetActive(col, RNA_boolean_get(&ptr, "active"));
				but = uiDefIconBut(block, UI_BTYPE_INLINK, 0, ICON_INLINK, 0, 0, UI_UNIT_X, UI_UNIT_Y, act, LINK_ACTUATOR, 0, 0, 0, "");
				if (!RNA_boolean_get(&ptr, "active")) {
					UI_but_flag_enable(but, UI_BUT_SCA_LINK_GREY);
				}

				col = uiLayoutColumn(split, true);
				uiLayoutSetContextPointer(col, "actuator", &ptr);

				/* should make UI template for actuator header.. function will do for now */
				draw_actuator_header(col, &ptr, &logic_ptr);

				/* draw the brick contents */
				draw_brick_actuator(col, &ptr, C);

				// Reset color (the current color is constantly received from the controller).
				if (U.themes.first) {
					bTheme *btheme = U.themes.first;
					copy_v3_v3_char(act->color, btheme->tui.wcol_box.inner);
				}

			}
		}
	}
	UI_block_layout_resolve(block, NULL, &yco);	/* stores final height in yco */
	height = MIN2(height, yco);

	UI_view2d_totRect_set(&ar->v2d, 57.5f * U.widget_unit, height - U.widget_unit);

	/* set the view */
	UI_view2d_view_ortho(&ar->v2d);

	UI_block_links_compose(block);

	UI_block_end(C, block);
	UI_block_draw(C, block);

	/* restore view matrix */
	UI_view2d_view_restore(C);

	if (idar) MEM_freeN(idar);
}
