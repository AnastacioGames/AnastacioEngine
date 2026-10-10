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

/** \file ghost/intern/GHOST_WindowX11.cpp
 *  \ingroup GHOST
 */

/* For standard X11 cursors */
#include <X11/cursorfont.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#ifdef WITH_X11_ALPHA
#include <X11/extensions/Xrender.h>
#endif
#include "GHOST_WindowX11.h"
#include "GHOST_SystemX11.h"
#include "STR_String.h"
#include "GHOST_Debug.h"

#ifdef WITH_XDND
#  include "GHOST_DropTargetX11.h"
#endif

#if defined(WITH_GL_EGL)
#  include "GHOST_ContextEGL.h"
#else
#  include "GHOST_ContextGLX.h"
#endif

/* for XIWarpPointer */
#ifdef WITH_X11_XINPUT
#  include <X11/extensions/XInput2.h>
#endif

//For DPI value
#include <X11/Xresource.h>

#include <cstring>
#include <cstdio>

/* gethostname */
#include <unistd.h>

#include <algorithm>
#include <string>
#include <math.h>

/* For obscure full screen mode stuff
 * lifted verbatim from blut. */

typedef struct {
	long flags;
	long functions;
	long decorations;
	long input_mode;
} MotifWmHints;

#define MWM_HINTS_DECORATIONS         (1L << 1)

#ifndef HOST_NAME_MAX
#  define HOST_NAME_MAX 64
#endif

// #define GHOST_X11_GRAB

/*
 * A Client can't change the window property, that is
 * the work of the window manager. In case, we send
 * a ClientMessage to the RootWindow with the property
 * and the Action (WM-spec define this):
 */
#define _NET_WM_STATE_REMOVE 0
#define _NET_WM_STATE_ADD 1
// #define _NET_WM_STATE_TOGGLE 2 // UNUSED

/*
 * import bpy
 * ima = bpy.data.images["blender.png"]
 * w, h = ima.size
 * print("%d,%d," % (w, h))
 * for y in range(h - 1, -1, -1):
 *     px = []
 *     for x in range(w):
 *         p = ((y * w) + x) * 4
 *         rgba = ima.pixels[p : p + 4]
 *         rgba = rgba[2], rgba[1], rgba[0], rgba[3]
 *         px.append(sum((int(p * 255) << (8 * i)) for i, p in enumerate(rgba)))
 *     print(", ".join([str(p) for p in px]), end=",\n")
 */

/**
 * Anastacio Engine cube icon (release/windows/icons/winrange.ico resized to 48x48, pixels 0xAARRGGBB, top row first).
 *
 * \note Using 'unsigned' to avoid `-Wnarrowing` warning.
 */
static const unsigned long BLENDER_ICON_48x48x32[] = {
	48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33554176, 33554176,
	83869503, 117440426, 117429418, 83869503, 33554176, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 33554176, 67086933, 131774097,
	79691775, 131745792, 165835008, 100663244, 131774061, 61516373, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 41910016, 131774061, 114611412, 114578688,
	971876931, 2834684551, 2851461508, 938255941, 114578688, 131783350, 148881279, 50298624, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 33554176, 114600533, 131783350, 61472768, 669752372, 2415186551,
	4059687059, 4294964371, 4294963854, 4042909067, 2347945843, 636131127, 79642431, 117440468, 114600533, 41910016, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 33488896, 97294643, 131783350, 75464575, 450988307, 1978648689, 3774473358, 4294965402,
	4294829702, 4210808693, 4210808436, 4294828417, 4294964372, 3774407562, 1945225066, 450330407, 61516373, 148881311, 79675199, 33554176,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 67086933, 131783313, 79675327, 333740032, 1676853604, 3522683020, 4294964378, 4294961544, 4210743672,
	4244363644, 4261141373, 4261141374, 4244363386, 4210809981, 4294961802, 4294964374, 3505905541, 1559150433, 265053696, 75464575, 131783313,
	67086933, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 50298624, 131774061, 79675391, 181167616, 1374664277, 3220626576, 4294963615, 4294962316, 4210809979, 4227586681, 4261140858,
	4261073780, 4261140343, 4261141372, 4261141112, 4261140081, 4227585653, 4210877059, 4294963601, 4294830991, 3119896444, 1156362322, 93913088,
	67108863, 131774061, 50298624, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33488896,
	97307750, 79691775, 93926144, 938584892, 2818037636, 4244369063, 4294965926, 4244365699, 4227586169, 4261139828, 4261140600, 4261142401,
	4261141889, 4261139057, 4261138797, 4261140340, 4261141368, 4261140339, 4261140599, 4227520890, 4244363897, 4294964117, 4177127049, 2633224047,
	736206919, 41877504, 131783313, 114600533, 33554176, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 16777216, 97294643, 131783350,
	61494528, 619289379, 2448740212, 4076530079, 4294966699, 4261209995, 4210875772, 4261140604, 4261139831, 4261140602, 4261140858, 4261140856,
	4261141371, 4261141370, 4261140340, 4261140856, 4261141372, 4261141113, 4261139571, 4261073261, 4261140084, 4210809983, 4277919102, 4294963083,
	3891847297, 2163328867, 484086070, 55924053, 148881279, 79675199, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 67086933, 131783313, 41910271, 349729292,
	1827718764, 3724141715, 4294966697, 4294830735, 4210809977, 4261075322, 4261141633, 4261141374, 4261140602, 4261139572, 4261138797, 4261139054,
	4261140598, 4261075834, 4244363895, 4261075062, 4261141112, 4261140598, 4261139826, 4261139569, 4261138796, 4261139571, 4244362355, 4210742386,
	4294958458, 4294963080, 3573013109, 1693433694, 282029871, 41910271, 131783277, 50331392, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 97294694, 75481023, 179457024, 1357888604, 3304578690,
	4294964377, 4294963087, 4210809977, 4244363644, 4261141114, 4261140855, 4261140600, 4261141116, 4244363642, 4261073004, 4261073001, 4261138796,
	4261140085, 4261141110, 4261076086, 4261074804, 4261139564, 4261139310, 4261139313, 4261138795, 4261137509, 4261138798, 4261140081, 4261073002,
	4244296044, 4210807661, 4294958192, 4294958703, 3187004007, 1223274833, 111815168, 61538303, 97294694, 0, 0, 0,
	0, 0, 0, 0, 0, 33488896, 114600533, 146767711, 954770235, 2851395191, 4261079434, 4294962565,
	4227586677, 4227585906, 4261073263, 4261139059, 4261139314, 4261139566, 4261139570, 4261139313, 4261139568, 4261074290, 4261139309, 4261139306,
	4261140848, 4261209981, 4261209728, 4261140335, 4261139563, 4261139051, 4261139566, 4261138537, 4261072487, 4261139311, 4261139307, 4261137763,
	4261137247, 4261071455, 4227450461, 4227449945, 4294957415, 4227456109, 2666909285, 836736558, 146775935, 97294694, 0, 0,
	0, 0, 0, 0, 0, 97294694, 75464639, 1710406990, 4059885983, 4294966677, 4244363627, 4227518827,
	4261139312, 4261138537, 4261139822, 4261138798, 4261072746, 4261074034, 4261139054, 4261071973, 4261139050, 4261204848, 4261139309, 4261139047,
	4261141099, 4261143929, 4261142651, 4261140338, 4261138793, 4261072999, 4261139565, 4261138278, 4261071714, 4261071972, 4261137763, 4261137245,
	4261004891, 4260872792, 4260873048, 4261071971, 4210740835, 4261074276, 4294966674, 4009751193, 1592899657, 61516543, 67086933, 0,
	0, 0, 0, 0, 0, 114600490, 75464703, 2633218097, 4294490166, 4159819385, 4261408148, 4261207929,
	4261073768, 4261139047, 4261139822, 4261138796, 4261072489, 4261140083, 4261138277, 4261071970, 4261073772, 4261138277, 4261137505, 4261138019,
	4261074028, 4261140080, 4261074285, 4261140078, 4261206382, 4261140589, 4261138791, 4261138017, 4261071449, 4261071196, 4261071197, 4261070680,
	4261005662, 4261071969, 4261138532, 4261074025, 4261011578, 4244633761, 4160018314, 4292648501, 2464589097, 33554431, 97294643, 0,
	0, 0, 0, 0, 0, 114600533, 111837098, 2482091058, 4276129802, 4206653702, 4258766400, 4260946323,
	4261410722, 4261077369, 4261074542, 4261140853, 4261140336, 4261139308, 4261138021, 4261071973, 4261005919, 4261071970, 4261139563, 4261138793,
	4261137249, 4261138279, 4261072485, 4261071712, 4261139559, 4261140332, 4261138019, 4261071197, 4261071710, 4261005659, 4261070938, 4261137247,
	4261139049, 4261074282, 4260944753, 4261410462, 4261408674, 4258044748, 4202446592, 4270870016, 2229904940, 41943039, 97294643, 0,
	0, 0, 0, 0, 0, 114600533, 93952460, 2532554547, 4293105686, 4189484304, 4256328452, 4257117198,
	4259492958, 4261408932, 4261409689, 4261076600, 4261073771, 4261139049, 4261138792, 4261072488, 4261005404, 4261138278, 4261139821, 4261140336,
	4261139562, 4261071968, 4261071968, 4261071969, 4261005919, 4261071709, 4261139303, 4261137248, 4261004631, 4261071196, 4261138532, 4261073253,
	4260943724, 4261211794, 4261411243, 4259625578, 4254356750, 4250347264, 4199623425, 4288043785, 2297473581, 55945983, 97294643, 0,
	0, 0, 0, 0, 0, 114600533, 111848148, 2532620083, 4293105426, 4189615119, 4256790548, 4256724240,
	4255867392, 4256921114, 4260021365, 4261409702, 4261209735, 4261074794, 4261140852, 4261075573, 4261007204, 4261138021, 4261138791, 4261072739,
	4261071968, 4261072997, 4261139305, 4261138532, 4261137503, 4261004628, 4261071711, 4261072482, 4261138279, 4261139564, 4261074279, 4261077886,
	4261411755, 4260682122, 4256002596, 4251003904, 4249297920, 4249824259, 4182977536, 4288503560, 2348135219, 75481087, 97294643, 0,
	0, 0, 0, 0, 0, 117429333, 146775999, 2566307636, 4293171476, 4189680655, 4256461327, 4256658447,
	4255804175, 4255408907, 4255735296, 4257975601, 4260747916, 4261410468, 4261144711, 4261077115, 4261140074, 4261137764, 4261071972, 4261071970,
	4261072740, 4261138273, 4261072741, 4261138792, 4261071454, 4261006176, 4261139051, 4261139306, 4261074277, 4261011062, 4261410987, 4261409187,
	4258241347, 4252646656, 4249428736, 4249167875, 4249495553, 4250021121, 4199491840, 4288897800, 2348529973, 75464703, 97294643, 0,
	0, 0, 0, 0, 0, 131774024, 164007309, 2583348279, 4293632790, 4189878031, 4256066572, 4256723986,
	4256395279, 4255869968, 4256132885, 4255079424, 4255998723, 4258964813, 4261144992, 4261411239, 4261077624, 4261074799, 4261140850, 4261139047,
	4261138793, 4261073514, 4261073772, 4261138535, 4261071712, 4261073258, 4261139561, 4261010289, 4261212312, 4261412020, 4260218220, 4255276296,
	4250609920, 4249101826, 4249036290, 4249036032, 4249364224, 4249889793, 4200082688, 4289489160, 2348662323, 93939404, 97294643, 0,
	0, 0, 0, 0, 0, 131774024, 131764662, 2616771895, 4293895959, 4206655503, 4256527378, 4256987154,
	4256330004, 4255672333, 4256198160, 4255541265, 4255212300, 4255801856, 4257248784, 4259757164, 4261410477, 4261277586, 4261076338, 4261141105,
	4261140850, 4261141110, 4261140591, 4261074542, 4261075828, 4261008999, 4261078404, 4261412016, 4260747141, 4256659486, 4252448768, 4249823232,
	4249298947, 4248970240, 4248773120, 4248904704, 4249101568, 4249496065, 4200148224, 4290343689, 2399125812, 71254015, 97294643, 0,
	0, 0, 0, 0, 0, 131774024, 164000141, 2633681209, 4293764634, 4206523922, 4256855568, 4257052946,
	4256395538, 4255935504, 4255409163, 4255277578, 4256526607, 4239421199, 4255737609, 4255735040, 4257645349, 4260615047, 4261410987, 4261144967,
	4261075566, 4261141107, 4261141105, 4261075825, 4261012609, 4261411241, 4261209752, 4257779765, 4252514816, 4249428480, 4232652803, 4232652801,
	4231864576, 4248641792, 4248904704, 4249167104, 4249167360, 4249955841, 4183633664, 4290475786, 2449459256, 71254015, 97294643, 0,
	0, 0, 0, 0, 0, 131774024, 198222475, 2700658745, 4294159641, 4207246867, 4257184020, 4256789520,
	4256066830, 4256001297, 4255080714, 4255737867, 4256657934, 4256132108, 4255409162, 4255606797, 4254816512, 4256129536, 4259095109, 4261210525,
	4261278365, 4261077880, 4261078398, 4261410467, 4261409704, 4258702930, 4253698304, 4250150144, 4248839171, 4249233154, 4249035776, 4248838656,
	4248641536, 4248773377, 4249101568, 4249167104, 4249101568, 4249890049, 4200213760, 4290936332, 2499792444, 90584012, 97307699, 0,
	0, 0, 0, 0, 0, 146775871, 230984073, 2717567289, 4294093590, 4207378191, 4257249553, 4256789524,
	4255869711, 4255015179, 4255277578, 4256066572, 4256789263, 4256000524, 4255146506, 4255803660, 4255672078, 4256132624, 4256458496, 4257773837,
	4260612199, 4261213874, 4261411769, 4260416112, 4255342862, 4250544128, 4249035777, 4249101826, 4249298689, 4248970496, 4248707584, 4231733248,
	4248576000, 4248707328, 4248576256, 4248904704, 4249495809, 4249955841, 4200608000, 4291593741, 2533347646, 109008298, 97307699, 0,
	0, 0, 0, 0, 0, 148881215, 215252863, 2717633852, 4294159639, 4206983181, 4256658189, 4256395021,
	4255672333, 4255804173, 4256461075, 4256132113, 4256921362, 4256855573, 4255278092, 4256395281, 4256395023, 4256526349, 4257381396, 4256789004,
	4258035200, 4261270344, 4259556149, 4253761280, 4250348544, 4249102083, 4248773120, 4248969984, 4248707328, 4248444672, 4248576000, 4248576256,
	4248904192, 4248379136, 4248444928, 4231864832, 4249233152, 4250284033, 4201067520, 4291528205, 2516570175, 109008298, 97307699, 0,
	0, 0, 0, 0, 0, 148881247, 249205119, 2784743229, 4294291479, 4207049228, 4256855311, 4256395020,
	4255868937, 4256658191, 4256723727, 4256000523, 4256067088, 4257184280, 4256263700, 4256460559, 4256000521, 4239026443, 4256657933, 4257250579,
	4257840653, 4261200425, 4256790286, 4250545155, 4250284290, 4249429760, 4249101312, 4248773120, 4248182016, 4248444672, 4248247808, 4248773120,
	4232324096, 4248773120, 4248773120, 4249167616, 4249561600, 4250021377, 4200541952, 4291660046, 2533347904, 108997290, 97307699, 0,
	0, 0, 0, 0, 0, 131774024, 249205119, 2818231357, 4294094362, 4207049487, 4256724243, 4256526611,
	4255671817, 4256066573, 4256132366, 4256001295, 4256132623, 4256132108, 4255737612, 4256526354, 4256592144, 4255869452, 4256592913, 4257381908,
	4258103562, 4261201976, 4256659737, 4249954048, 4249233153, 4248838912, 4249101312, 4248707072, 4248313344, 4231536384, 4231733504, 4248707328,
	4249035776, 4248838656, 4248773120, 4249298688, 4249364480, 4249955841, 4200541696, 4291857168, 2583679812, 126961809, 97294643, 0,
	0, 0, 0, 0, 0, 131774024, 216634495, 2767769150, 4294621471, 4207575574, 4256657676, 4256657935,
	4256000783, 4255803402, 4255672330, 4256330000, 4256395280, 4256395278, 4255803145, 4255934988, 4256855315, 4256526864, 4256526605, 4257118738,
	4258103562, 4261400382, 4256725273, 4249822464, 4232324609, 4248969984, 4248773120, 4248707328, 4248904448, 4248904704, 4248641792, 4248182016,
	4248904192, 4248510464, 4231930368, 4249101568, 4249233153, 4250086913, 4200673024, 4292317714, 2650789961, 144654207, 83869503, 0,
	0, 0, 0, 0, 0, 131774024, 215258239, 2700659769, 4294488341, 4207377935, 4256723985, 4256263178,
	4256132623, 4256395284, 4256197903, 4256000781, 4256395536, 4256395278, 4256132109, 4256461331, 4239355406, 4255540488, 4256592658, 4257118741,
	4258169609, 4261401157, 4257251354, 4250347520, 4232390145, 4248904448, 4248773120, 4248970241, 4248904192, 4248313344, 4248182016, 4231601920,
	4231864576, 4248444672, 4248773120, 4249036032, 4249626880, 4250284289, 4201592832, 4292646161, 2617234758, 144662399, 97294643, 0,
	0, 0, 0, 0, 0, 148873023, 182819225, 2684013110, 4294159124, 4206852364, 4256790292, 4256921106,
	4256132366, 4255737613, 4255869199, 4255934737, 4255672334, 4255869709, 4255934989, 4256066317, 4255606539, 4239158029, 4256592399, 4257381656,
	4258827027, 4261402700, 4257448731, 4250544640, 4249233153, 4249035776, 4249167104, 4249035776, 4248904448, 4248772864, 4248707328, 4249692930,
	4248576000, 4248313344, 4248576000, 4249036032, 4249495808, 4250480897, 4201198592, 4292054801, 2550126150, 126961809, 100650086, 0,
	0, 0, 0, 0, 0, 117429333, 215258260, 2734345013, 4294225170, 4190469390, 4257184528, 4256855311,
	4255803147, 4255080713, 4254883592, 4255475469, 4256395539, 4255738127, 4255606797, 4255803917, 4256132623, 4256855313, 4256526864, 4257053201,
	4258827538, 4261405021, 4257449243, 4250479104, 4249495809, 4249298688, 4232193024, 4248641536, 4231733248, 4248378880, 4248641536, 4249429761,
	4248838656, 4248576000, 4248576256, 4232324352, 4249495808, 4233506561, 4201067264, 4291988754, 2583679814, 144662399, 114600533, 0,
	0, 0, 0, 0, 0, 131774024, 198216610, 2700790326, 4293698835, 4190403085, 4257315855, 4256000522,
	4255211785, 4255343630, 4255475213, 4255934987, 4256263179, 4255278090, 4256066578, 4256592406, 4256658449, 4256723984, 4256657935, 4257118740,
	4259091733, 4261406821, 4257646620, 4250544896, 4249430273, 4248838912, 4248576256, 4248707328, 4231536384, 4248379136, 4248641536, 4248838656,
	4248641792, 4248904448, 4249101568, 4249101568, 4249298688, 4250152961, 4201133312, 4292251664, 2550125379, 108997290, 100650086, 0,
	0, 0, 0, 0, 0, 131774024, 232229257, 2751122232, 4293962261, 4207509261, 4257315085, 4239486477,
	4255474954, 4255869454, 4255869456, 4255343371, 4255475211, 4255934988, 4238698250, 4256132112, 4256526866, 4256592656, 4256657936, 4257513751,
	4259353871, 4261406307, 4257646621, 4233832960, 4249233153, 4248641792, 4231733248, 4248576000, 4248247808, 4248444672, 4248707584, 4249101568,
	4231864832, 4248970497, 4248969984, 4248904448, 4249298688, 4250350081, 4201198848, 4291791631, 2449462079, 109008298, 97307699, 0,
	0, 0, 0, 0, 0, 131774024, 265062536, 2767899190, 4260539156, 4207772174, 4240406798, 4256066317,
	4255606025, 4255803146, 4256000782, 4255212301, 4255672330, 4256460814, 4238632716, 4255474955, 4256000781, 4256526865, 4257053204, 4257447955,
	4258827532, 4261405795, 4257778204, 4251004416, 4249758721, 4249430017, 4249627137, 4248510208, 4248510208, 4248444672, 4248707328, 4232324352,
	4249036032, 4232061696, 4248707584, 4249101568, 4249692672, 4250678017, 4184159232, 4257645582, 2382351929, 126961846, 97294643, 0,
	0, 0, 0, 0, 0, 114600490, 179463833, 2885143098, 4294949397, 4157176587, 4240143888, 4256395278,
	4255934475, 4256066059, 4255737867, 4256000523, 4256591886, 4256131850, 4255540748, 4255672078, 4255803918, 4256526607, 4256855571, 4257118484,
	4258761481, 4261406053, 4257778204, 4234292736, 4249627137, 4249561344, 4248838912, 4248510208, 4248772864, 4248772864, 4249167105, 4249955585,
	4248969984, 4248707584, 4248904448, 4249101568, 4249889792, 4234229250, 4150735104, 4291856397, 2432682296, 33554687, 97294643, 0,
	0, 0, 0, 0, 0, 79658815, 162172245, 1442038603, 3690710059, 4293763089, 4274288905, 4206457614,
	4240209424, 4240209677, 4256395020, 4256789007, 4257315349, 4258105118, 4256395282, 4256197902, 4255803404, 4256198157, 4256592398, 4257381658,
	4259288081, 4261406306, 4257777948, 4234424064, 4232981249, 4248904448, 4248641792, 4248773120, 4248773120, 4248510208, 4249167105, 4248904448,
	4248969984, 4249363968, 4249561088, 4249692929, 4199557888, 4251268096, 4290146058, 3639586340, 1190445381, 93952358, 61516373, 0,
	0, 0, 0, 0, 0, 16777216, 114600533, 162165077, 702983767, 2482551604, 4159546907, 4292446989,
	4206654217, 4239683340, 4256066057, 4256066315, 4256526861, 4240867091, 4256723478, 4256132366, 4239026442, 4239420942, 4256658191, 4256789518,
	4259156501, 4261407081, 4258238492, 4251267072, 4249430273, 4249101568, 4232193024, 4231995904, 4248510464, 4248838656, 4249232897, 4248970496,
	4249167360, 4249692416, 4232981249, 4199951104, 4286727939, 4173562390, 2482617138, 620216156, 144670591, 111837013, 0, 0,
	0, 0, 0, 0, 0, 0, 16777216, 114600533, 164014677, 162172301, 1207220811, 3304370984,
	4293499922, 4290934535, 4206457869, 4257052431, 4239683596, 4256592140, 4256394766, 4256658457, 4255934990, 4255869195, 4256263694, 4256790034,
	4258762258, 4261407855, 4258370334, 4251332608, 4249824257, 4249561088, 4248969984, 4248576000, 4248707584, 4249232897, 4249364224, 4249758208,
	4249955585, 4199820288, 4285019392, 4289489933, 3303580965, 1241500229, 162172301, 146775903, 97294643, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 61516373, 165849656, 93952409, 417969258,
	2062858808, 3924798493, 4292709900, 4240274186, 4222906380, 4256920846, 4256329484, 4256395022, 4256461077, 4256067090, 4256593171, 4257447447,
	4258827789, 4261407079, 4257975324, 4251004416, 4249824257, 4248904448, 4231930368, 4248772864, 4249101568, 4249364224, 4249758464, 4216400896,
	4216990464, 4288371206, 4007171100, 2181021497, 402641518, 87241574, 146775871, 50298751, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 33488896, 114600533, 181180748,
	129405366, 888191571, 2901717802, 4293369109, 4291657481, 4206916874, 4240078095, 4239749903, 4256789777, 4256395282, 4257052951, 4257315860,
	4258498571, 4261405538, 4257712156, 4251332864, 4249758721, 4249035776, 4232127488, 4232455680, 4249823745, 4249758721, 4199557120, 4286070784,
	4290936596, 3019224624, 1006620493, 106255786, 146767679, 97294643, 33488896, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 41910143,
	148873023, 129405293, 232239241, 1626979391, 3673403427, 4293895184, 4258038028, 4223432209, 4256592142, 4238829320, 4256263438, 4257447963,
	4258695950, 4261405279, 4258304029, 4251661056, 4250021377, 4249626880, 4249429760, 4249824257, 4216400640, 4251267584, 4289160458, 3789857316,
	1744817474, 249214591, 106255701, 146775871, 41910016, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 79658815, 148873023, 93939353, 636598880, 2549859643, 4176653338, 4292380939, 4206457355, 4239617548, 4256526605, 4256986639,
	4258827539, 4261406825, 4258172700, 4251398656, 4250086913, 4250021120, 4233243905, 4199557120, 4286268162, 4224419607, 2734670645, 771738714,
	71237823, 131764552, 79658815, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 33554176, 129405256, 146775903, 162165133, 1274330695, 3337925414, 4293631506, 4291394569, 4206852367, 4257512979,
	4259025169, 4261406568, 4257712155, 4251201792, 4250152962, 4199820288, 4284822528, 4289357836, 3437535781, 1358941254, 179470207, 126971208,
	131764552, 33554176, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 67086933, 148881215, 111837055, 401128558, 2079898165, 3975326492, 4293433873, 4224878355,
	4225206536, 4261403993, 4257514781, 4217384704, 4217056768, 4287451397, 3989604634, 2181020469, 452971874, 71237759, 146775871, 67086933,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 33554176, 114600490, 148873023, 111837140, 955367249, 3019488560, 4294225433,
	4293432580, 4211072084, 4206854426, 4286528512, 4290147345, 3018631212, 973065548, 90597068, 146767679, 114600490, 33488896, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 50298751, 164014648, 131764589, 300004487, 1777844806,
	3791306015, 4294963809, 4293436708, 3738865433, 1711261503, 317769343, 109019007, 131774024, 50298751, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 33554176, 97294694, 182825548, 148873151,
	821344591, 2717439071, 2650655556, 721406030, 75464703, 146775871, 83869503, 33554176, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 50298751, 148881247,
	148881279, 199723845, 181180825, 146775935, 117418581, 33554176, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33554176,
	97294643, 134208109, 114600533, 67086933, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0,
};

static XVisualInfo *x11_visualinfo_from_glx(
        Display *display,
        bool stereoVisual,
        GHOST_TUns16 *r_numOfAASamples,
        bool needAlpha,
        GLXFBConfig *fbconfig)
{
	XVisualInfo *visual = NULL;
	GHOST_TUns16 numOfAASamples = *r_numOfAASamples;
	int glx_major, glx_minor, glx_version; /* GLX version: major.minor */
	GHOST_TUns16 actualSamples;
	int glx_attribs[64];

	*fbconfig = NULL;

	/* Set up the minimum attributes that we require and see if
	 * X can find us a visual matching those requirements. */

	if (!glXQueryVersion(display, &glx_major, &glx_minor)) {
		fprintf(stderr,
		        "%s:%d: X11 glXQueryVersion() failed, "
		        "verify working openGL system!\n",
		        __FILE__, __LINE__);

		return NULL;
	}
	glx_version = glx_major*100 + glx_minor;

	if (glx_version >= 104) {
		actualSamples = numOfAASamples;
	}
	else {
		numOfAASamples = 0;
		actualSamples = 0;
	}

#ifdef WITH_X11_ALPHA
	if (   needAlpha
	    && glx_version >= 103
	    && (glXChooseFBConfig ||
	        (glXChooseFBConfig = (PFNGLXCHOOSEFBCONFIGPROC)glXGetProcAddressARB((const GLubyte *)"glXChooseFBConfig")) != NULL)
	    && (glXGetVisualFromFBConfig ||
	        (glXGetVisualFromFBConfig = (PFNGLXGETVISUALFROMFBCONFIGPROC)glXGetProcAddressARB((const GLubyte *)"glXGetVisualFromFBConfig")) != NULL)
	    ) {
		GLXFBConfig *fbconfigs;
		int nbfbconfig;
		int i;

		for (;;) {

			GHOST_X11_GL_GetAttributes(glx_attribs, 64, actualSamples, stereoVisual, needAlpha, true);

			fbconfigs = glXChooseFBConfig(display, DefaultScreen(display), glx_attribs, &nbfbconfig);

			/* Any sample level or even zero, which means oversampling disabled, is good
			 * but we need a valid visual to continue */
			if (nbfbconfig > 0) {
				/* take a frame buffer config that has alpha cap */
				for (i=0 ;i<nbfbconfig; i++) {
					visual = (XVisualInfo*)glXGetVisualFromFBConfig(display, fbconfigs[i]);
					if (!visual)
						continue;
					/* if we don't need a alpha background, the first config will do, otherwise
					 * test the alphaMask as it won't necessarily be present */
					if (needAlpha) {
						XRenderPictFormat *pict_format = XRenderFindVisualFormat(display, visual->visual);
						if (!pict_format)
							continue;
						if (pict_format->direct.alphaMask <= 0)
							continue;
					}
					*fbconfig = fbconfigs[i];
					break;
				}
				XFree(fbconfigs);
				if (i<nbfbconfig) {
					if (actualSamples < numOfAASamples) {
						fprintf(stderr,
						        "Warning! Unable to find a multisample pixel format that supports exactly %d samples. "
						        "Substituting one that uses %d samples.\n",
						        numOfAASamples, actualSamples);
					}
					break;
				}
				visual = NULL;
			}

			if (actualSamples == 0) {
				/* All options exhausted, cannot continue */
				fprintf(stderr,
				        "%s:%d: X11 glXChooseVisual() failed, "
				        "verify working openGL system!\n",
				        __FILE__, __LINE__);

				return NULL;
			}
			else {
				--actualSamples;
			}
		}
	}
	else
#endif
	{
		/* legacy, don't use extension */
		for (;;) {
			GHOST_X11_GL_GetAttributes(glx_attribs, 64, actualSamples, stereoVisual, needAlpha, false);

			visual = glXChooseVisual(display, DefaultScreen(display), glx_attribs);

			/* Any sample level or even zero, which means oversampling disabled, is good
			 * but we need a valid visual to continue */
			if (visual != NULL) {
				if (actualSamples < numOfAASamples) {
					fprintf(stderr,
					        "Warning! Unable to find a multisample pixel format that supports exactly %d samples. "
					        "Substituting one that uses %d samples.\n",
					        numOfAASamples, actualSamples);
				}
				break;
			}

			if (actualSamples == 0) {
				/* All options exhausted, cannot continue */
				fprintf(stderr,
				        "%s:%d: X11 glXChooseVisual() failed, "
				        "verify working openGL system!\n",
				        __FILE__, __LINE__);

				return NULL;
			}
			else {
				--actualSamples;
			}
		}
	}
	*r_numOfAASamples = actualSamples;
	return visual;
}

GHOST_WindowX11::
GHOST_WindowX11(GHOST_SystemX11 *system,
        Display *display,
        const STR_String &title,
        GHOST_TInt32 left,
        GHOST_TInt32 top,
        GHOST_TUns32 width,
        GHOST_TUns32 height,
        GHOST_TWindowState state,
        const GHOST_TEmbedderWindowID parentWindow,
        GHOST_TDrawingContextType type,
        const bool stereoVisual,
        const bool exclusive,
        const bool alphaBackground,
        const GHOST_TUns16 numOfAASamples, const bool is_debug)
    : GHOST_Window(width, height, state, stereoVisual, exclusive, numOfAASamples),
      m_display(display),
      m_visualInfo(NULL),
      m_fbconfig(NULL),
      m_normal_state(GHOST_kWindowStateNormal),
      m_system(system),
      m_invalid_window(false),
      m_empty_cursor(None),
      m_custom_cursor(None),
      m_visible_cursor(None),
      m_taskbar("blender.desktop"),
#ifdef WITH_XDND
      m_dropTarget(NULL),
#endif
#if defined(WITH_X11_XINPUT) && defined(X_HAVE_UTF8_STRING)
      m_xic(NULL),
#endif
      m_valid_setup(false),
      m_is_debug_context(is_debug)
{
	if (type == GHOST_kDrawingContextTypeOpenGL) {
		m_visualInfo = x11_visualinfo_from_glx(m_display, stereoVisual, &m_wantNumOfAASamples, alphaBackground, (GLXFBConfig*)&m_fbconfig);
	}
	else {
		XVisualInfo tmp = {0};
		int n;
		m_visualInfo = XGetVisualInfo(m_display, 0, &tmp, &n);
	}

	/* caller needs to check 'getValid()' */
	if (m_visualInfo == NULL) {
		fprintf(stderr, "initial window could not find the GLX extension\n");
		return;
	}

	unsigned int xattributes_valuemask = 0;

	XSetWindowAttributes xattributes;
	memset(&xattributes, 0, sizeof(xattributes));

	xattributes_valuemask |= CWBorderPixel;
	xattributes.border_pixel = 0;

	/* Specify which events we are interested in hearing. */

	xattributes_valuemask |= CWEventMask;
	xattributes.event_mask =
	        ExposureMask | StructureNotifyMask |
	        KeyPressMask | KeyReleaseMask |
	        EnterWindowMask | LeaveWindowMask |
	        ButtonPressMask | ButtonReleaseMask |
	        PointerMotionMask | FocusChangeMask |
	        PropertyChangeMask | KeymapStateMask;

	if (exclusive) {
		xattributes_valuemask |= CWOverrideRedirect;
		xattributes.override_redirect = True;
	}

	xattributes_valuemask |= CWColormap;
	xattributes.colormap = XCreateColormap(
	        m_display,
	        RootWindow(m_display, m_visualInfo->screen),
	        m_visualInfo->visual,
	        AllocNone
	        );

	/* create the window! */
	if (parentWindow == 0) {
		m_window =  XCreateWindow(
		        m_display,
		        RootWindow(m_display, m_visualInfo->screen),
		        left, top, width, height,
		        0, /* no border. */
		        m_visualInfo->depth,
		        InputOutput,
		        m_visualInfo->visual,
		        xattributes_valuemask,
		        &xattributes);
	}
	else {
		Window root_return;
		int x_return, y_return;
		unsigned int w_return, h_return, border_w_return, depth_return;

		XGetGeometry(m_display, parentWindow, &root_return, &x_return, &y_return,
		             &w_return, &h_return, &border_w_return, &depth_return);

		left = 0;
		top = 0;
		width = w_return;
		height = h_return;


		m_window = XCreateWindow(
		        m_display,
		        parentWindow, /* reparent against embedder */
		        left, top, width, height,
		        0, /* no border. */
		        m_visualInfo->depth,
		        InputOutput,
		        m_visualInfo->visual,
		        xattributes_valuemask,
		        &xattributes);

		XSelectInput(m_display, parentWindow, SubstructureNotifyMask);

	}

#ifdef WITH_XDND
	/* initialize drop target for newly created window */
	m_dropTarget = new GHOST_DropTargetX11(this, m_system);
	GHOST_PRINT("Set drop target\n");
#endif

	if (state == GHOST_kWindowStateMaximized || state == GHOST_kWindowStateFullScreen) {
		Atom atoms[2];
		int count = 0;
		if (state == GHOST_kWindowStateMaximized) {
			atoms[count++] = m_system->m_atom._NET_WM_STATE_MAXIMIZED_VERT;
			atoms[count++] = m_system->m_atom._NET_WM_STATE_MAXIMIZED_HORZ;
		}
		else {
			atoms[count++] = m_system->m_atom._NET_WM_STATE_FULLSCREEN;
		}

		XChangeProperty(m_display, m_window, m_system->m_atom._NET_WM_STATE, XA_ATOM, 32,
		                PropModeReplace, (unsigned char *)atoms, count);
		m_post_init = False;
	}
	/*
	 * One of the problem with WM-spec is that can't set a property
	 * to a window that isn't mapped. That is why we can't "just
	 * call setState" here.
	 *
	 * To fix this, we first need know that the window is really
	 * map waiting for the MapNotify event.
	 *
	 * So, m_post_init indicate that we need wait for the MapNotify
	 * event and then set the Window state to the m_post_state.
	 */
	else if ((state != GHOST_kWindowStateNormal) && (state != GHOST_kWindowStateMinimized)) {
		m_post_init = True;
		m_post_state = state;
	}
	else {
		m_post_init = False;
		m_post_state = GHOST_kWindowStateNormal;
	}


	/* Create some hints for the window manager on how
	 * we want this window treated. */
	{
		XSizeHints *xsizehints = XAllocSizeHints();
		xsizehints->flags = PPosition | PSize | PMinSize | PMaxSize;
		xsizehints->x = left;
		xsizehints->y = top;
		xsizehints->width = width;
		xsizehints->height = height;
		xsizehints->min_width = 320;     /* size hints, could be made apart of the ghost api */
		xsizehints->min_height = 240;    /* limits are also arbitrary, but should not allow 1x1 window */
		xsizehints->max_width = 65535;
		xsizehints->max_height = 65535;
		XSetWMNormalHints(m_display, m_window, xsizehints);
		XFree(xsizehints);
	}


	/* XClassHint, title */
	{
		XClassHint *xclasshint = XAllocClassHint();
		const int len = title.Length() + 1;
		char *wmclass = (char *)malloc(sizeof(char) * len);
		memcpy(wmclass, title.ReadPtr(), len * sizeof(char));
		xclasshint->res_name = wmclass;
		xclasshint->res_class = wmclass;
		XSetClassHint(m_display, m_window, xclasshint);
		free(wmclass);
		XFree(xclasshint);
	}


	/* The basic for a good ICCCM "work" */
	if (m_system->m_atom.WM_PROTOCOLS) {
		Atom atoms[2];
		int natom = 0;

		if (m_system->m_atom.WM_DELETE_WINDOW) {
			atoms[natom] = m_system->m_atom.WM_DELETE_WINDOW;
			natom++;
		}

		if (m_system->m_atom.WM_TAKE_FOCUS && m_system->m_windowFocus) {
			atoms[natom] = m_system->m_atom.WM_TAKE_FOCUS;
			natom++;
		}

		if (natom) {
			/* printf("Register atoms: %d\n", natom); */
			XSetWMProtocols(m_display, m_window, atoms, natom);
		}
	}

	/* Set the window hints */
	{
		XWMHints *xwmhints = XAllocWMHints();
		xwmhints->initial_state = NormalState;
		xwmhints->input = (m_system->m_windowFocus) ? True : False;
		xwmhints->flags = InputHint | StateHint;
		XSetWMHints(display, m_window, xwmhints);
		XFree(xwmhints);
	}


	/* set the icon */
	{
		Atom _NET_WM_ICON     = XInternAtom(m_display, "_NET_WM_ICON", False);
		XChangeProperty(m_display, m_window, _NET_WM_ICON, XA_CARDINAL,
		                32, PropModeReplace, (unsigned char *)BLENDER_ICON_48x48x32,
		                BLENDER_ICON_48x48x32[0] * BLENDER_ICON_48x48x32[1] + 2);
	}

	/* set the process ID (_NET_WM_PID) */
	{
		Atom _NET_WM_PID = XInternAtom(m_display, "_NET_WM_PID", False);
		pid_t pid = getpid();
		XChangeProperty(m_display, m_window, _NET_WM_PID, XA_CARDINAL,
		                32, PropModeReplace, (unsigned char *)&pid, 1);
	}


	/* set the hostname (WM_CLIENT_MACHINE) */
	{
		char  hostname[HOST_NAME_MAX];
		char *text_array[1];
		XTextProperty text_prop;

		gethostname(hostname, sizeof(hostname));
		hostname[sizeof(hostname) - 1] = '\0';
		text_array[0] = hostname;

		XStringListToTextProperty(text_array, 1, &text_prop);
		XSetWMClientMachine(m_display, m_window, &text_prop);
		XFree(text_prop.value);
	}

#ifdef WITH_X11_XINPUT
	refreshXInputDevices();

	m_tabletData.Active = GHOST_kTabletModeNone;
#endif


	/* now set up the rendering context. */
	if (setDrawingContextType(type) == GHOST_kSuccess) {
		m_valid_setup = true;
		GHOST_PRINT("Created window\n");
	}

	setTitle(title);

	if (exclusive && system->m_windowFocus) {
		XMapRaised(m_display, m_window);
	}
	else {
		XMapWindow(m_display, m_window);

		if (!system->m_windowFocus) {
			XLowerWindow(m_display, m_window);
		}
	}
	GHOST_PRINT("Mapped window\n");

	XFlush(m_display);
}

#if defined(WITH_X11_XINPUT) && defined(X_HAVE_UTF8_STRING)
static Bool destroyICCallback(XIC /*xic*/, XPointer ptr, XPointer /*data*/)
{
	GHOST_PRINT("XIM input context destroyed\n");

	if (ptr) {
		*(XIC *)ptr = NULL;
	}
	/* Ignored by X11. */
	return True;
}

bool GHOST_WindowX11::createX11_XIC()
{
	XIM xim = m_system->getX11_XIM();
	if (!xim)
		return false;

	XICCallback destroy;
	destroy.callback = (XICProc)destroyICCallback;
	destroy.client_data = (XPointer)&m_xic;
	m_xic = XCreateIC(xim, XNClientWindow, m_window, XNFocusWindow, m_window,
	                  XNInputStyle, XIMPreeditNothing | XIMStatusNothing,
	                  XNResourceName, GHOST_X11_RES_NAME,
	                  XNResourceClass, GHOST_X11_RES_CLASS,
	                  XNDestroyCallback, &destroy,
	                  NULL);
	if (!m_xic)
		return false;

	unsigned long fevent;
	XGetICValues(m_xic, XNFilterEvents, &fevent, NULL);
	XSelectInput(m_display, m_window,
	             ExposureMask | StructureNotifyMask |
	             KeyPressMask | KeyReleaseMask |
	             EnterWindowMask | LeaveWindowMask |
	             ButtonPressMask | ButtonReleaseMask |
	             PointerMotionMask | FocusChangeMask |
	             PropertyChangeMask | KeymapStateMask | fevent);
	return true;
}
#endif

#ifdef WITH_X11_XINPUT
void GHOST_WindowX11::refreshXInputDevices()
{
	if (m_system->m_xinput_version.present) {
		std::vector<XEventClass> xevents;

		for (GHOST_SystemX11::GHOST_TabletX11& xtablet: m_system->GetXTablets()) {
			/* With modern XInput (xlib 1.6.2 at least and/or evdev 2.9.0) and some 'no-name' tablets
			 * like 'UC-LOGIC Tablet WP5540U', we also need to 'select' ButtonPress for motion event,
			 * otherwise we do not get any tablet motion event once pen is pressed... See T43367.
			 */
			XEventClass ev;

			DeviceMotionNotify(xtablet.Device, xtablet.MotionEvent, ev);
			if (ev) xevents.push_back(ev);
			DeviceButtonPress(xtablet.Device, xtablet.PressEvent, ev);
			if (ev) xevents.push_back(ev);
			ProximityIn(xtablet.Device, xtablet.ProxInEvent, ev);
			if (ev) xevents.push_back(ev);
			ProximityOut(xtablet.Device, xtablet.ProxOutEvent, ev);
			if (ev) xevents.push_back(ev);
		}

		XSelectExtensionEvent(m_display, m_window, xevents.data(), (int)xevents.size());
	}
}

#endif /* WITH_X11_XINPUT */

Window
GHOST_WindowX11::
getXWindow()
{
	return m_window;
}

bool
GHOST_WindowX11::
getValid() const
{
	return GHOST_Window::getValid() && m_valid_setup;
}

void
GHOST_WindowX11::
setTitle(
		const STR_String& title)
{
	Atom name = XInternAtom(m_display, "_NET_WM_NAME", 0);
	Atom utf8str = XInternAtom(m_display, "UTF8_STRING", 0);
	XChangeProperty(m_display, m_window,
	                name, utf8str, 8, PropModeReplace,
	                (const unsigned char *) title.ReadPtr(),
	                title.Length());

	/* This should convert to valid x11 string
	 * and getTitle would need matching change */
	XStoreName(m_display, m_window, title);

	XFlush(m_display);
}

void
GHOST_WindowX11::
getTitle(
		STR_String& title) const
{
	char *name = NULL;

	XFetchName(m_display, m_window, &name);
	title = name ? name : "untitled";
	XFree(name);
}

void
GHOST_WindowX11::
getWindowBounds(
		GHOST_Rect& bounds) const
{
	/* Getting the window bounds under X11 is not
	 * really supported (nor should it be desired). */
	getClientBounds(bounds);
}

void
GHOST_WindowX11::
getClientBounds(
		GHOST_Rect& bounds) const
{
	Window root_return;
	int x_return, y_return;
	unsigned int w_return, h_return, border_w_return, depth_return;
	GHOST_TInt32 screen_x, screen_y;

	XGetGeometry(m_display, m_window, &root_return, &x_return, &y_return,
	             &w_return, &h_return, &border_w_return, &depth_return);

	clientToScreen(0, 0, screen_x, screen_y);

	bounds.m_l = screen_x;
	bounds.m_r = bounds.m_l + w_return;
	bounds.m_t = screen_y;
	bounds.m_b = bounds.m_t + h_return;

}

GHOST_TSuccess
GHOST_WindowX11::
setClientWidth(
		GHOST_TUns32 width)
{
	XWindowChanges values;
	unsigned int value_mask = CWWidth;
	values.width = width;
	XConfigureWindow(m_display, m_window, value_mask, &values);

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
setClientHeight(
		GHOST_TUns32 height)
{
	XWindowChanges values;
	unsigned int value_mask = CWHeight;
	values.height = height;
	XConfigureWindow(m_display, m_window, value_mask, &values);
	return GHOST_kSuccess;

}

GHOST_TSuccess
GHOST_WindowX11::
setClientSize(
		GHOST_TUns32 width,
		GHOST_TUns32 height)
{
	XWindowChanges values;
	unsigned int value_mask = CWWidth | CWHeight;
	values.width = width;
	values.height = height;
	XConfigureWindow(m_display, m_window, value_mask, &values);
	return GHOST_kSuccess;

}

void
GHOST_WindowX11::
screenToClient(
		GHOST_TInt32 inX,
		GHOST_TInt32 inY,
		GHOST_TInt32& outX,
		GHOST_TInt32& outY) const
{
	/* This is correct! */

	int ax, ay;
	Window temp;

	XTranslateCoordinates(m_display,
	                      RootWindow(m_display, m_visualInfo->screen),
	                      m_window,
	                      inX, inY,
	                      &ax, &ay,
	                      &temp);
	outX = ax;
	outY = ay;
}

void
GHOST_WindowX11::
clientToScreen(
		GHOST_TInt32 inX,
		GHOST_TInt32 inY,
		GHOST_TInt32& outX,
		GHOST_TInt32& outY) const
{
	int ax, ay;
	Window temp;

	XTranslateCoordinates(
	    m_display,
	    m_window,
	    RootWindow(m_display, m_visualInfo->screen),
	    inX, inY,
	    &ax, &ay,
	    &temp);
	outX = ax;
	outY = ay;
}

void GHOST_WindowX11::icccmSetState(int state)
{
	XEvent xev;

	if (state != IconicState)
		return;

	xev.xclient.type = ClientMessage;
	xev.xclient.serial = 0;
	xev.xclient.send_event = True;
	xev.xclient.display = m_display;
	xev.xclient.window = m_window;
	xev.xclient.format = 32;
	xev.xclient.message_type = m_system->m_atom.WM_CHANGE_STATE;
	xev.xclient.data.l[0] = state;
	XSendEvent(m_display, RootWindow(m_display, m_visualInfo->screen),
	           False, SubstructureNotifyMask | SubstructureRedirectMask, &xev);
}

int GHOST_WindowX11::icccmGetState(void) const
{
	struct {
		CARD32 state;
		XID    icon;
	} *prop_ret;
	unsigned long bytes_after, num_ret;
	Atom type_ret;
	int ret, format_ret;
	CARD32 st;

	prop_ret = NULL;
	ret = XGetWindowProperty(
	        m_display, m_window, m_system->m_atom.WM_STATE, 0, 2,
	        False, m_system->m_atom.WM_STATE, &type_ret,
	        &format_ret, &num_ret, &bytes_after, ((unsigned char **)&prop_ret));
	if ((ret == Success) && (prop_ret != NULL) && (num_ret == 2)) {
		st = prop_ret->state;
	}
	else {
		st = NormalState;
	}

	if (prop_ret) {
		XFree(prop_ret);
	}

	return st;
}

void GHOST_WindowX11::netwmMaximized(bool set)
{
	XEvent xev;

	xev.xclient.type = ClientMessage;
	xev.xclient.serial = 0;
	xev.xclient.send_event = True;
	xev.xclient.window = m_window;
	xev.xclient.message_type = m_system->m_atom._NET_WM_STATE;
	xev.xclient.format = 32;

	if (set == True)
		xev.xclient.data.l[0] = _NET_WM_STATE_ADD;
	else
		xev.xclient.data.l[0] = _NET_WM_STATE_REMOVE;

	xev.xclient.data.l[1] = m_system->m_atom._NET_WM_STATE_MAXIMIZED_HORZ;
	xev.xclient.data.l[2] = m_system->m_atom._NET_WM_STATE_MAXIMIZED_VERT;
	xev.xclient.data.l[3] = 0;
	xev.xclient.data.l[4] = 0;
	XSendEvent(m_display, RootWindow(m_display, m_visualInfo->screen),
	           False, SubstructureRedirectMask | SubstructureNotifyMask, &xev);
}

bool GHOST_WindowX11::netwmIsMaximized(void) const
{
	Atom *prop_ret;
	unsigned long bytes_after, num_ret, i;
	Atom type_ret;
	bool st;
	int format_ret, ret, count;

	prop_ret = NULL;
	st = False;
	ret = XGetWindowProperty(
	        m_display, m_window, m_system->m_atom._NET_WM_STATE, 0, INT_MAX,
	        False, XA_ATOM, &type_ret, &format_ret,
	        &num_ret, &bytes_after, (unsigned char **)&prop_ret);
	if ((ret == Success) && (prop_ret) && (format_ret == 32)) {
		count = 0;
		for (i = 0; i < num_ret; i++) {
			if (prop_ret[i] == m_system->m_atom._NET_WM_STATE_MAXIMIZED_HORZ) {
				count++;
			}
			if (prop_ret[i] == m_system->m_atom._NET_WM_STATE_MAXIMIZED_VERT) {
				count++;
			}
			if (count == 2) {
				st = True;
				break;
			}
		}
	}

	if (prop_ret)
		XFree(prop_ret);
	return (st);
}

void GHOST_WindowX11::netwmFullScreen(bool set)
{
	XEvent xev;

	xev.xclient.type = ClientMessage;
	xev.xclient.serial = 0;
	xev.xclient.send_event = True;
	xev.xclient.window = m_window;
	xev.xclient.message_type = m_system->m_atom._NET_WM_STATE;
	xev.xclient.format = 32;

	if (set == True)
		xev.xclient.data.l[0] = _NET_WM_STATE_ADD;
	else
		xev.xclient.data.l[0] = _NET_WM_STATE_REMOVE;

	xev.xclient.data.l[1] = m_system->m_atom._NET_WM_STATE_FULLSCREEN;
	xev.xclient.data.l[2] = 0;
	xev.xclient.data.l[3] = 0;
	xev.xclient.data.l[4] = 0;
	XSendEvent(m_display, RootWindow(m_display, m_visualInfo->screen),
	           False, SubstructureRedirectMask | SubstructureNotifyMask, &xev);
}

bool GHOST_WindowX11::netwmIsFullScreen(void) const
{
	Atom *prop_ret;
	unsigned long bytes_after, num_ret, i;
	Atom type_ret;
	bool st;
	int format_ret, ret;

	prop_ret = NULL;
	st = False;
	ret = XGetWindowProperty(
	        m_display, m_window, m_system->m_atom._NET_WM_STATE, 0, INT_MAX,
	        False, XA_ATOM, &type_ret, &format_ret,
	        &num_ret, &bytes_after, (unsigned char **)&prop_ret);
	if ((ret == Success) && (prop_ret) && (format_ret == 32)) {
		for (i = 0; i < num_ret; i++) {
			if (prop_ret[i] == m_system->m_atom._NET_WM_STATE_FULLSCREEN) {
				st = True;
				break;
			}
		}
	}

	if (prop_ret)
		XFree(prop_ret);
	return (st);
}

void GHOST_WindowX11::motifFullScreen(bool set)
{
	MotifWmHints hints;

	hints.flags = MWM_HINTS_DECORATIONS;
	if (set == True)
		hints.decorations = 0;
	else
		hints.decorations = 1;

	XChangeProperty(m_display, m_window, m_system->m_atom._MOTIF_WM_HINTS,
	                m_system->m_atom._MOTIF_WM_HINTS, 32, PropModeReplace,
	                (unsigned char *) &hints, 4);
}

bool GHOST_WindowX11::motifIsFullScreen(void) const
{
	MotifWmHints *prop_ret;
	unsigned long bytes_after, num_ret;
	Atom type_ret;
	bool state;
	int format_ret, st;

	prop_ret = NULL;
	state = False;
	st = XGetWindowProperty(
	        m_display, m_window, m_system->m_atom._MOTIF_WM_HINTS, 0, INT_MAX,
	        False, m_system->m_atom._MOTIF_WM_HINTS,
	        &type_ret, &format_ret, &num_ret,
	        &bytes_after, (unsigned char **)&prop_ret);
	if ((st == Success) && prop_ret) {
		if (prop_ret->flags & MWM_HINTS_DECORATIONS) {
			if (!prop_ret->decorations)
				state = True;
		}
	}

	if (prop_ret)
		XFree(prop_ret);
	return (state);
}

GHOST_TWindowState GHOST_WindowX11::getState() const
{
	GHOST_TWindowState state_ret;
	int state;

	state_ret = GHOST_kWindowStateNormal;
	state = icccmGetState();
	/*
	 * In the Iconic and Withdrawn state, the window
	 * is unmaped, so only need return a Minimized state.
	 */
	if ((state == IconicState) || (state == WithdrawnState))
		state_ret = GHOST_kWindowStateMinimized;
	else if (netwmIsFullScreen() == True)
		state_ret = GHOST_kWindowStateFullScreen;
	else if (motifIsFullScreen() == True)
		state_ret = GHOST_kWindowStateFullScreen;
	else if (netwmIsMaximized() == True)
		state_ret = GHOST_kWindowStateMaximized;
	return (state_ret);
}

GHOST_TSuccess GHOST_WindowX11::setState(GHOST_TWindowState state)
{
	GHOST_TWindowState cur_state;
	bool is_max, is_full, is_motif_full;

	cur_state = getState();
	if (state == (int)cur_state)
		return GHOST_kSuccess;

	if (cur_state != GHOST_kWindowStateMinimized) {
		/*
		 * The window don't have this property's
		 * if it's not mapped.
		 */
		is_max = netwmIsMaximized();
		is_full = netwmIsFullScreen();
	}
	else {
		is_max = False;
		is_full = False;
	}

	is_motif_full = motifIsFullScreen();

	if (state == GHOST_kWindowStateNormal)
		state = m_normal_state;

	if (state == GHOST_kWindowStateNormal) {
		if (is_max == True)
			netwmMaximized(False);
		if (is_full == True)
			netwmFullScreen(False);
		if (is_motif_full == True)
			motifFullScreen(False);
		icccmSetState(NormalState);
		return (GHOST_kSuccess);
	}

	if (state == GHOST_kWindowStateFullScreen) {
		/*
		 * We can't change to full screen if the window
		 * isn't mapped.
		 */
		if (cur_state == GHOST_kWindowStateMinimized)
			return (GHOST_kFailure);

		m_normal_state = cur_state;

		if (is_max == True)
			netwmMaximized(False);
		if (is_full == False)
			netwmFullScreen(True);
		if (is_motif_full == False)
			motifFullScreen(True);
		return (GHOST_kSuccess);
	}

	if (state == GHOST_kWindowStateMaximized) {
		/*
		 * We can't change to Maximized if the window
		 * isn't mapped.
		 */
		if (cur_state == GHOST_kWindowStateMinimized)
			return (GHOST_kFailure);

		if (is_full == True)
			netwmFullScreen(False);
		if (is_motif_full == True)
			motifFullScreen(False);
		if (is_max == False)
			netwmMaximized(True);
		return (GHOST_kSuccess);
	}

	if (state == GHOST_kWindowStateMinimized) {
		/*
		 * The window manager need save the current state of
		 * the window (maximized, full screen, etc).
		 */
		icccmSetState(IconicState);
		return (GHOST_kSuccess);
	}

	return (GHOST_kFailure);
}

#include <iostream>

GHOST_TSuccess
GHOST_WindowX11::
setOrder(
		GHOST_TWindowOrder order)
{
	if (order == GHOST_kWindowOrderTop) {
		XWindowAttributes attr;
		Atom atom;

		/* We use both XRaiseWindow and _NET_ACTIVE_WINDOW, since some
		 * window managers ignore the former (e.g. kwin from kde) and others
		 * don't implement the latter (e.g. fluxbox pre 0.9.9) */

		XRaiseWindow(m_display, m_window);

		atom = XInternAtom(m_display, "_NET_ACTIVE_WINDOW", True);

		if (atom != None) {
			Window root;
			XEvent xev;
			long eventmask;

			xev.xclient.type = ClientMessage;
			xev.xclient.serial = 0;
			xev.xclient.send_event = True;
			xev.xclient.window = m_window;
			xev.xclient.message_type = atom;

			xev.xclient.format = 32;
			xev.xclient.data.l[0] = 1;
			xev.xclient.data.l[1] = CurrentTime;
			xev.xclient.data.l[2] = m_window;
			xev.xclient.data.l[3] = 0;
			xev.xclient.data.l[4] = 0;

			root = RootWindow(m_display, m_visualInfo->screen);
			eventmask = SubstructureRedirectMask | SubstructureNotifyMask;

			XSendEvent(m_display, root, False, eventmask, &xev);
		}

		XGetWindowAttributes(m_display, m_window, &attr);

		/* iconized windows give bad match error */
		if (attr.map_state == IsViewable)
			XSetInputFocus(m_display, m_window, RevertToPointerRoot,
			               CurrentTime);
		XFlush(m_display);
	}
	else if (order == GHOST_kWindowOrderBottom) {
		XLowerWindow(m_display, m_window);
		XFlush(m_display);
	}
	else {
		return GHOST_kFailure;
	}

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
invalidate()
{
	/* So the idea of this function is to generate an expose event
	 * for the window.
	 * Unfortunately X does not handle expose events for you and
	 * it is the client's job to refresh the dirty part of the window.
	 * We need to queue up invalidate calls and generate GHOST events
	 * for them in the system.
	 *
	 * We implement this by setting a boolean in this class to concatenate
	 * all such calls into a single event for this window.
	 *
	 * At the same time we queue the dirty windows in the system class
	 * and generate events for them at the next processEvents call. */

	if (m_invalid_window == false) {
		m_system->addDirtyWindow(this);
		m_invalid_window = true;
	}

	return GHOST_kSuccess;
}

/**
 * called by the X11 system implementation when expose events
 * for the window have been pushed onto the GHOST queue
 */

void
GHOST_WindowX11::
validate()
{
	m_invalid_window = false;
}


/**
 * Destructor.
 * Closes the window and disposes resources allocated.
 */

GHOST_WindowX11::
~GHOST_WindowX11()
{
	std::map<unsigned int, Cursor>::iterator it = m_standard_cursors.begin();
	for (; it != m_standard_cursors.end(); ++it) {
		XFreeCursor(m_display, it->second);
	}

	if (m_empty_cursor) {
		XFreeCursor(m_display, m_empty_cursor);
	}
	if (m_custom_cursor) {
		XFreeCursor(m_display, m_custom_cursor);
	}

	if (m_valid_setup) {
		static Atom Primary_atom, Clipboard_atom;
		Window p_owner, c_owner;
		/*Change the owner of the Atoms to None if we are the owner*/
		Primary_atom = XInternAtom(m_display, "PRIMARY", False);
		Clipboard_atom = XInternAtom(m_display, "CLIPBOARD", False);


		p_owner = XGetSelectionOwner(m_display, Primary_atom);
		c_owner = XGetSelectionOwner(m_display, Clipboard_atom);

		if (p_owner == m_window) {
			XSetSelectionOwner(m_display, Primary_atom, None, CurrentTime);
		}
		if (c_owner == m_window) {
			XSetSelectionOwner(m_display, Clipboard_atom, None, CurrentTime);
		}
	}

	if (m_visualInfo) {
		XFree(m_visualInfo);
	}

#if defined(WITH_X11_XINPUT) && defined(X_HAVE_UTF8_STRING)
	if (m_xic) {
		XDestroyIC(m_xic);
	}
#endif

#ifdef WITH_XDND
	delete m_dropTarget;
#endif

	releaseNativeHandles();

	if (m_valid_setup) {
		XDestroyWindow(m_display, m_window);
	}
}


GHOST_Context *GHOST_WindowX11::newDrawingContext(GHOST_TDrawingContextType type)
{
	if (type == GHOST_kDrawingContextTypeOpenGL) {
#if !defined(WITH_GL_EGL)

#if defined(WITH_GL_PROFILE_CORE)
		GHOST_Context *context = new GHOST_ContextGLX(
		        m_wantStereoVisual,
		        m_wantNumOfAASamples,
		        m_window,
		        m_display,
		        m_visualInfo,
		        (GLXFBConfig)m_fbconfig,
		        GLX_CONTEXT_CORE_PROFILE_BIT_ARB,
		        3, 2,
		        GHOST_OPENGL_GLX_CONTEXT_FLAGS | (m_is_debug_context ? GLX_CONTEXT_DEBUG_BIT_ARB : 0),
		        GHOST_OPENGL_GLX_RESET_NOTIFICATION_STRATEGY);
#elif defined(WITH_GL_PROFILE_ES20)
		GHOST_Context *context = new GHOST_ContextGLX(
		        m_wantStereoVisual,
		        m_wantNumOfAASamples,
		        m_window,
		        m_display,
		        m_visualInfo,
		        (GLXFBConfig)m_fbconfig,
		        GLX_CONTEXT_ES2_PROFILE_BIT_EXT,
		        2, 0,
		        GHOST_OPENGL_GLX_CONTEXT_FLAGS | (m_is_debug_context ? GLX_CONTEXT_DEBUG_BIT_ARB : 0),
		        GHOST_OPENGL_GLX_RESET_NOTIFICATION_STRATEGY);
#elif defined(WITH_GL_PROFILE_COMPAT)
		GHOST_Context *context = new GHOST_ContextGLX(
		        m_wantStereoVisual,
		        m_wantNumOfAASamples,
		        m_window,
		        m_display,
		        m_visualInfo,
		        (GLXFBConfig)m_fbconfig,
		        0, // profile bit
		        0, 0,
		        GHOST_OPENGL_GLX_CONTEXT_FLAGS | (m_is_debug_context ? GLX_CONTEXT_DEBUG_BIT_ARB : 0),
		        GHOST_OPENGL_GLX_RESET_NOTIFICATION_STRATEGY);
#else
#  error
#endif

#else

#if defined(WITH_GL_PROFILE_CORE)
		GHOST_Context *context = new GHOST_ContextEGL(
		        m_wantStereoVisual,
		        m_wantNumOfAASamples,
		        m_window,
		        m_display,
		        EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT,
		        3, 2,
		        GHOST_OPENGL_EGL_CONTEXT_FLAGS,
		        GHOST_OPENGL_EGL_RESET_NOTIFICATION_STRATEGY,
		        EGL_OPENGL_API);
#elif defined(WITH_GL_PROFILE_ES20)
		GHOST_Context *context = new GHOST_ContextEGL(
		        m_wantStereoVisual,
		        m_wantNumOfAASamples,
		        m_window,
		        m_display,
		        0, // profile bit
		        2, 0,
		        GHOST_OPENGL_EGL_CONTEXT_FLAGS,
		        GHOST_OPENGL_EGL_RESET_NOTIFICATION_STRATEGY,
		        EGL_OPENGL_ES_API);
#elif defined(WITH_GL_PROFILE_COMPAT)
		GHOST_Context *context = new GHOST_ContextEGL(
		        m_wantStereoVisual,
		        m_wantNumOfAASamples,
		        m_window,
		        m_display,
		        0, // profile bit
		        0, 0,
		        GHOST_OPENGL_EGL_CONTEXT_FLAGS,
		        GHOST_OPENGL_EGL_RESET_NOTIFICATION_STRATEGY,
		        EGL_OPENGL_API);
#else
#  error
#endif

#endif
		if (context->initializeDrawingContext())
			return context;
		else
			delete context;
	}

	return NULL;
}


Cursor
GHOST_WindowX11::
getStandardCursor(
		GHOST_TStandardCursor g_cursor)
{
	unsigned int xcursor_id;

#define GtoX(gcurs, xcurs)  case gcurs: xcursor_id = xcurs
	switch (g_cursor) {
		GtoX(GHOST_kStandardCursorRightArrow, XC_arrow); break;
		GtoX(GHOST_kStandardCursorLeftArrow, XC_top_left_arrow); break;
		GtoX(GHOST_kStandardCursorInfo, XC_hand1); break;
		GtoX(GHOST_kStandardCursorDestroy, XC_pirate); break;
		GtoX(GHOST_kStandardCursorHelp, XC_question_arrow); break;
		GtoX(GHOST_kStandardCursorCycle, XC_exchange); break;
		GtoX(GHOST_kStandardCursorSpray, XC_spraycan); break;
		GtoX(GHOST_kStandardCursorWait, XC_watch); break;
		GtoX(GHOST_kStandardCursorText, XC_xterm); break;
		GtoX(GHOST_kStandardCursorCrosshair, XC_crosshair); break;
		GtoX(GHOST_kStandardCursorUpDown, XC_sb_v_double_arrow); break;
		GtoX(GHOST_kStandardCursorLeftRight, XC_sb_h_double_arrow); break;
		GtoX(GHOST_kStandardCursorTopSide, XC_top_side); break;
		GtoX(GHOST_kStandardCursorBottomSide, XC_bottom_side); break;
		GtoX(GHOST_kStandardCursorLeftSide, XC_left_side); break;
		GtoX(GHOST_kStandardCursorRightSide, XC_right_side); break;
		GtoX(GHOST_kStandardCursorTopLeftCorner, XC_top_left_corner); break;
		GtoX(GHOST_kStandardCursorTopRightCorner, XC_top_right_corner); break;
		GtoX(GHOST_kStandardCursorBottomRightCorner, XC_bottom_right_corner); break;
		GtoX(GHOST_kStandardCursorBottomLeftCorner, XC_bottom_left_corner); break;
		GtoX(GHOST_kStandardCursorPencil, XC_pencil); break;
		GtoX(GHOST_kStandardCursorCopy, XC_arrow); break;
		default:
			xcursor_id = 0;
	}
#undef GtoX

	if (xcursor_id) {
		Cursor xcursor = m_standard_cursors[xcursor_id];

		if (!xcursor) {
			xcursor = XCreateFontCursor(m_display, xcursor_id);

			m_standard_cursors[xcursor_id] = xcursor;
		}

		return xcursor;
	}
	else {
		return None;
	}
}

Cursor
GHOST_WindowX11::
getEmptyCursor(
        ) {
	if (!m_empty_cursor) {
		Pixmap blank;
		XColor dummy = {0};
		char data[1] = {0};

		/* make a blank cursor */
		blank = XCreateBitmapFromData(
		    m_display,
		    RootWindow(m_display, m_visualInfo->screen),
		    data, 1, 1
		    );

		m_empty_cursor = XCreatePixmapCursor(m_display, blank, blank, &dummy, &dummy, 0, 0);
		XFreePixmap(m_display, blank);
	}

	return m_empty_cursor;
}

GHOST_TSuccess
GHOST_WindowX11::
setWindowCursorVisibility(
		bool visible)
{
	Cursor xcursor;

	if (visible) {
		if (m_visible_cursor)
			xcursor = m_visible_cursor;
		else
			xcursor = getStandardCursor(getCursorShape() );
	}
	else {
		xcursor = getEmptyCursor();
	}

	XDefineCursor(m_display, m_window, xcursor);
	XFlush(m_display);

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
setWindowCursorGrab(
		GHOST_TGrabCursorMode mode)
{
	if (mode != GHOST_kGrabDisable) {
		if (mode != GHOST_kGrabNormal) {
			m_system->getCursorPosition(m_cursorGrabInitPos[0], m_cursorGrabInitPos[1]);
			setCursorGrabAccum(0, 0);

			if (mode == GHOST_kGrabHide)
				setWindowCursorVisibility(false);

		}
#ifdef GHOST_X11_GRAB
		XGrabPointer(m_display, m_window, False, ButtonPressMask | ButtonReleaseMask | PointerMotionMask,
		             GrabModeAsync, GrabModeAsync, None, None, CurrentTime);
#endif
	}
	else {
		if (m_cursorGrab == GHOST_kGrabHide) {
			m_system->setCursorPosition(m_cursorGrabInitPos[0], m_cursorGrabInitPos[1]);
		}

		if (m_cursorGrab != GHOST_kGrabNormal) {
			/* use to generate a mouse move event, otherwise the last event
			 * blender gets can be outside the screen causing menus not to show
			 * properly unless the user moves the mouse */

#if defined(WITH_X11_XINPUT) && defined(USE_X11_XINPUT_WARP)
			if ((m_system->m_xinput_version.present) &&
			    (m_system->m_xinput_version.major_version >= 2))
			{
				int device_id;
				if (XIGetClientPointer(m_display, None, &device_id) != False) {
					XIWarpPointer(m_display, device_id, None, None, 0, 0, 0, 0, 0, 0);
				}
			}
			else
#endif
			{
				XWarpPointer(m_display, None, None, 0, 0, 0, 0, 0, 0);
			}
		}

		/* Perform this last so to workaround XWayland bug, see: T53004. */
		if (m_cursorGrab == GHOST_kGrabHide) {
			setWindowCursorVisibility(true);
		}

		/* Almost works without but important otherwise the mouse GHOST location can be incorrect on exit */
		setCursorGrabAccum(0, 0);
		m_cursorGrabBounds.m_l = m_cursorGrabBounds.m_r = -1; /* disable */
#ifdef GHOST_X11_GRAB
		XUngrabPointer(m_display, CurrentTime);
#endif
	}

	XFlush(m_display);

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
setWindowCursorShape(
		GHOST_TStandardCursor shape)
{
	Cursor xcursor = getStandardCursor(shape);

	m_visible_cursor = xcursor;

	XDefineCursor(m_display, m_window, xcursor);
	XFlush(m_display);

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
setWindowCustomCursorShape(
		GHOST_TUns8 bitmap[16][2],
		GHOST_TUns8 mask[16][2],
		int hotX,
		int hotY)
{
	setWindowCustomCursorShape((GHOST_TUns8 *)bitmap, (GHOST_TUns8 *)mask,
	                           16, 16, hotX, hotY, 0, 1);
	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
setWindowCustomCursorShape(
		GHOST_TUns8 *bitmap,
		GHOST_TUns8 *mask,
		int sizex,
		int sizey,
		int hotX,
		int hotY,
		int /*fg_color*/,
		int /*bg_color*/)
{
	Colormap colormap = DefaultColormap(m_display, m_visualInfo->screen);
	Pixmap bitmap_pix, mask_pix;
	XColor fg, bg;

	if (XAllocNamedColor(m_display, colormap, "White", &fg, &fg) == 0) return GHOST_kFailure;
	if (XAllocNamedColor(m_display, colormap, "Black", &bg, &bg) == 0) return GHOST_kFailure;

	if (m_custom_cursor) {
		XFreeCursor(m_display, m_custom_cursor);
	}

	bitmap_pix = XCreateBitmapFromData(m_display, m_window, (char *) bitmap, sizex, sizey);
	mask_pix = XCreateBitmapFromData(m_display, m_window, (char *) mask, sizex, sizey);

	m_custom_cursor = XCreatePixmapCursor(m_display, bitmap_pix, mask_pix, &fg, &bg, hotX, hotY);
	XDefineCursor(m_display, m_window, m_custom_cursor);
	XFlush(m_display);

	m_visible_cursor = m_custom_cursor;

	XFreePixmap(m_display, bitmap_pix);
	XFreePixmap(m_display, mask_pix);

	XFreeColors(m_display, colormap, &fg.pixel, 1, 0L);
	XFreeColors(m_display, colormap, &bg.pixel, 1, 0L);

	return GHOST_kSuccess;
}


GHOST_TSuccess
GHOST_WindowX11::
beginFullScreen() const
{
	{
		Window root_return;
		int x_return, y_return;
		unsigned int w_return, h_return, border_w_return, depth_return;

		XGetGeometry(m_display, m_window, &root_return, &x_return, &y_return,
		             &w_return, &h_return, &border_w_return, &depth_return);

		m_system->setCursorPosition(w_return / 2, h_return / 2);
	}


	/* Grab Keyboard & Mouse */
	int err;

	err = XGrabKeyboard(m_display, m_window, False,
	                    GrabModeAsync, GrabModeAsync, CurrentTime);
	if (err != GrabSuccess) printf("XGrabKeyboard failed %d\n", err);

	err = XGrabPointer(m_display, m_window, False,  PointerMotionMask | ButtonPressMask | ButtonReleaseMask,
	                   GrabModeAsync, GrabModeAsync, m_window, None, CurrentTime);
	if (err != GrabSuccess) printf("XGrabPointer failed %d\n", err);

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_WindowX11::
endFullScreen() const
{
	XUngrabKeyboard(m_display, CurrentTime);
	XUngrabPointer(m_display, CurrentTime);

	return GHOST_kSuccess;
}

GHOST_TUns16
GHOST_WindowX11::
getDPIHint()
{
	/* Try to read DPI setting set using xrdb */
	char* resMan = XResourceManagerString(m_display);
	if (resMan) {
		XrmDatabase xrdb = XrmGetStringDatabase(resMan);
		if (xrdb) {
			char* type = NULL;
			XrmValue val;

			int success = XrmGetResource(xrdb, "Xft.dpi", "Xft.Dpi", &type, &val);
			if (success && type) {
				if (strcmp(type, "String") == 0) {
					return atoi((char*)val.addr);
				}
			}
		}
		XrmDestroyDatabase(xrdb);
	}

	/* Fallback to calculating DPI using X reported DPI, set using xrandr --dpi */
	XWindowAttributes attr;
	if (!XGetWindowAttributes(m_display, m_window, &attr)) {
		/* Failed to get window attributes, return X11 default DPI */
		return 96;
	}

	Screen* screen = attr.screen;
	int pixelWidth = WidthOfScreen(screen);
	int pixelHeight = HeightOfScreen(screen);
	int mmWidth = WidthMMOfScreen(screen);
	int mmHeight = HeightMMOfScreen(screen);

	double pixelDiagonal = sqrt((pixelWidth * pixelWidth) + (pixelHeight * pixelHeight));
	double mmDiagonal = sqrt((mmWidth * mmWidth) + (mmHeight * mmHeight));
	float inchDiagonal = mmDiagonal * 0.039f;
	int dpi = pixelDiagonal / inchDiagonal;
	return dpi;
}

GHOST_TSuccess GHOST_WindowX11::setProgressBar(float progress)
{
	if (m_taskbar.is_valid()) {
		m_taskbar.set_progress(progress);
		m_taskbar.set_progress_enabled(true);
		return GHOST_kSuccess;
	}

	return GHOST_kFailure;
}

GHOST_TSuccess GHOST_WindowX11::endProgressBar()
{
	if (m_taskbar.is_valid()) {
		m_taskbar.set_progress_enabled(false);
		return GHOST_kSuccess;
	}

	return GHOST_kFailure;
}
