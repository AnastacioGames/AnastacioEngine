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
 * Range Engine icon (release/windows/icons/winrange.ico resized to 48x48, pixels 0xAARRGGBB, top row first).
 *
 * \note Using 'unsigned' to avoid `-Wnarrowing` warning.
 */
static const unsigned long BLENDER_ICON_48x48x32[] = {
	48, 48,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 67065173, 821310762, 871705891, 855189534, 855188254, 854859294, 872031011, 267273284, 0, 33488896, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 67065173, 0, 1324436282, 4294914087, 4294647322, 4294778395, 4294646296, 4277605653, 4294906902, 2448693274, 0, 83820544, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 79642431, 50298751, 0, 0, 0, 0, 0, 83836735, 0, 2583052082, 4294909980, 4177204501, 4232513286, 4231398917, 4210167826, 4278127631, 3455192336, 16777216, 33488896, 0, 0, 0, 0, 0, 50266112, 67065173, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 33488896, 0, 0, 67065173, 0, 0, 0, 0, 33488896, 97281638, 3589550888, 4294843161, 4222881807, 4247457294, 4247983380, 4238806543, 4278127888, 4109241615, 500896017, 0, 50266112, 0, 0, 0, 67043328, 0, 0, 50266112, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 33488896, 33488896, 0, 1592871742, 569344891, 0, 67065173, 33488896, 33488896, 117396778, 0, 720126512, 4243990818, 4261353752, 4249684489, 4254735901, 4256634903, 4250012942, 4211019024, 4294446609, 1223495185, 0, 134161444, 33488896, 33488896, 50266112, 0, 921711407, 1375025205, 0, 67065088, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 33488896, 67065173, 0, 2348105781, 4294916397, 3892135483, 1458991204, 0, 0, 0, 0, 257, 2180201261, 4294911008, 4191162641, 4246736397, 4257094938, 4251781641, 4245818894, 4191489295, 4278127888, 2515342871, 514, 0, 0, 0, 0, 1811231282, 4160296984, 4294907926, 1659975990, 0, 97268531, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 67065173, 0, 2331722293, 4294914599, 4171436814, 4294123288, 4294916144, 2600098127, 251644086, 184510054, 1828472383, 3405461554, 4243924771, 4243855642, 4258142232, 4256964381, 4258666520, 4254274578, 4255193111, 4258468371, 4259712014, 4259975700, 3438616612, 1828664120, 167735693, 352275532, 2868127786, 4294906900, 4257219844, 4206560001, 4294317844, 1542338613, 0, 83836735, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 50298751, 0, 2314418994, 4294914599, 4184608010, 4246605325, 4232908557, 4226882071, 4294912294, 3640212535, 3623498800, 4294912810, 4294909986, 4261354783, 4261223967, 4260567836, 4259518231, 4258272276, 4259124244, 4259713556, 4260172564, 4260631060, 4260237073, 4293594640, 4294251542, 3589085724, 3706396191, 4294905358, 4206494209, 4228645377, 4236314887, 4243981826, 4277278482, 1425159728, 0, 50266112, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 50298751, 61472768, 2197371441, 4294913829, 4183952393, 4232188175, 4261359140, 4246016016, 4253947155, 4210170394, 4294515742, 4294515743, 4211022880, 4226817312, 4255585043, 4250206722, 4246798336, 4245356544, 4245094400, 4244897792, 4245422080, 4247060480, 4250796289, 4256041997, 4226158608, 4209249035, 4292545033, 4293331207, 4204725507, 4247390472, 4248965390, 4254862599, 4221634049, 4236379393, 4193720849, 1358048291, 0, 61494613, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 16777216, 33488896, 160242716, 3889568535, 4244577048, 4221377819, 4247721236, 4250470919, 4250868249, 4248967190, 4256832541, 4227799581, 4227341343, 4254994450, 4246863872, 4244703240, 4247731261, 4251611763, 4254176405, 4255162785, 4254965150, 4253518474, 4250624353, 4246809644, 4244635904, 4247846912, 4255648266, 4225829898, 4225698310, 4254403848, 4256634641, 4254338053, 4248963074, 4247718920, 4171307024, 4293725696, 2662600198, 0, 79626240, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 61472768, 0, 1484326146, 4293531157, 4211021336, 4255653150, 4244706067, 4257487127, 4261354268, 4261090842, 4259386904, 4249354754, 4244636676, 4250229853, 4257070013, 4259833061, 4260162540, 4260030954, 4259965162, 4259767782, 4259569888, 4259371737, 4258581449, 4255094934, 4248190009, 4244635648, 4251583746, 4258991366, 4259187972, 4260171522, 4253420802, 4246867463, 4223539468, 4293990402, 3837137922, 371326976, 33488896, 16777216, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 61472768, 0, 2846099978, 4294775061, 4211019283, 4255324699, 4254996249, 4261351187, 4258271251, 4246667264, 4246217508, 4256346032, 4260359663, 4259965676, 4259965676, 4259635938, 4258582734, 4257924288, 4257989823, 4258779082, 4259305684, 4258779341, 4258712518, 4258908867, 4253580146, 4244966408, 4249879552, 4259059716, 4259387905, 4257487616, 4242036249, 4244599580, 4124585472, 1046872064, 131841, 97281536, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 41877504, 33488896, 371326976, 3804104972, 4277537554, 4243983121, 4261350675, 4258860562, 4246405120, 4247664440, 4258714324, 4260031468, 4259702505, 4259043544, 4254502537, 4249765440, 4247330842, 4246475533, 4246738190, 4248250913, 4251671118, 4256473749, 4259040451, 4258316468, 4259564725, 4256274297, 4246410762, 4251388672, 4260445185, 4261253931, 4244628806, 4277924669, 3891711037, 1140315468, 0, 0, 97294643, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 83820544, 0, 1975194391, 4294577684, 4192733711, 4259908625, 4247977984, 4246941231, 4258846167, 4259570661, 4259702247, 4255950499, 4247397408, 4244635648, 4244635648, 4245095941, 4245556234, 4245489927, 4245095168, 4244635648, 4245487616, 4251273786, 4258379164, 4258905243, 4260547482, 4257059930, 4253703705, 4260810566, 4261147448, 4260943113, 4244291840, 4294891541, 4294893881, 2633750855, 518957610, 0, 79675199, 50331392, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 33488896, 97281638, 3371374622, 4293658895, 4226943504, 4252304390, 4244836882, 4257135549, 4259373539, 4259504868, 4253844864, 4244635648, 4245754130, 4248780607, 4248911936, 4249043521, 4249108800, 4249174077, 4249305147, 4249435959, 4249040942, 4247724055, 4252325951, 4260283794, 4260677493, 4261403488, 4261409097, 4261209370, 4261069824, 4261066241, 4261065220, 4244220672, 4244289793, 4294958884, 3841842751, 1677315650, 16777216, 0, 100636979, 33488896, 0, 0, 0, 0,
	0, 33488896, 67065173, 134161444, 41877504, 1223235615, 4294053141, 4225959692, 4257875982, 4245094400, 4252531580, 4259570403, 4259110368, 4254831759, 4244635648, 4246478110, 4256873146, 4258846679, 4258254027, 4258319305, 4258318788, 4258449344, 4258645434, 4258907312, 4259497383, 4260351136, 4260284036, 4260941925, 4261209425, 4260947499, 4260941318, 4261067520, 4277843205, 4261064964, 4260997891, 4260996100, 4260929026, 4210597888, 4294884619, 4294958127, 3019757632, 787725361, 0, 33554176, 67086848, 0, 0, 0,
	33488896, 0, 0, 0, 0, 2766803480, 4276553999, 4192733454, 4251451651, 4246086692, 4258253773, 4258649816, 4257595582, 4246212877, 4246543903, 4257136061, 4260293868, 4259175129, 4259306199, 4259371217, 4259567307, 4259763396, 4260090808, 4260022951, 4260415892, 4261007478, 4261273948, 4261145147, 4261075734, 4277781253, 4261001224, 4261000456, 4277776134, 4260997380, 4260930563, 4260864003, 4260797186, 4260533251, 4243623168, 4210334208, 4294952985, 4093498676, 2113588797, 215252736, 0, 83869503, 33554176, 0,
	0, 234840674, 1056324925, 2079468847, 3119325990, 4175433748, 4258596620, 4258531598, 4246601728, 4251282541, 4258780631, 4258780888, 4251541336, 4244635649, 4248648249, 4251542369, 4251146323, 4251802449, 4252261966, 4252852298, 4253640522, 4254033734, 4254688826, 4258306635, 4261206629, 4277856333, 4261078310, 4261072139, 4261068298, 4261067274, 4261000201, 4260998407, 4260997638, 4260930565, 4260797699, 4260665602, 4260467458, 4260137986, 4259743746, 4259611650, 4209345024, 4294024453, 4294955047, 3456094774, 1207417390, 0, 1, 61516288,
	1239816991, 3857586976, 4293400090, 4293660693, 4293003791, 4275046156, 4258727949, 4255974665, 4245161479, 4255162530, 4258386388, 4257463997, 4246936598, 4246017044, 4246147600, 4244832256, 4245225472, 4245618944, 4246144256, 4246800384, 4247389184, 4250739968, 4256400166, 4260420174, 4261080121, 4261075220, 4261070092, 4261002512, 4261001485, 4261000202, 4261064457, 4260931848, 4260865030, 4260863748, 4260600067, 4260336387, 4260072450, 4259809026, 4259414274, 4259151362, 4258822915, 4242044673, 4209148160, 4294684945, 4294889517, 2566637876, 451643648, 0,
	1859717901, 4293396237, 4191159562, 4191094282, 4207805964, 4257875467, 4258858764, 4253679876, 4245888028, 4256872377, 4258254803, 4255095189, 4245555718, 4246739996, 4247068701, 4247462686, 4247724826, 4248249367, 4248971283, 4250546187, 4256333864, 4261077085, 4261411924, 4261210413, 4261007636, 4261070099, 4261003282, 4261001742, 4261000461, 4260999435, 4260932105, 4260865544, 4260798470, 4260600067, 4260270595, 4260007170, 4259809282, 4259414274, 4258887938, 4258756354, 4258361858, 4258230786, 4258231043, 4225201152, 4243296512, 4294957085, 3757956419, 921739282,
	1758791436, 4258924300, 4224386571, 4257809930, 4257678602, 4257481738, 4258727436, 4252303361, 4246809645, 4257398464, 4258123215, 4253844606, 4245489927, 4247068703, 4247133980, 4247462171, 4247855641, 4248511508, 4248772877, 4254226436, 4261404996, 4261079421, 4260951117, 4261075999, 4277783065, 4261070102, 4261003026, 4261001487, 4261000205, 4260932619, 4260865801, 4260864775, 4260732164, 4260336642, 4260138754, 4259809282, 4259414530, 4258953730, 4258624770, 4258361601, 4258099202, 4258033667, 4257901826, 4258624256, 4260404487, 4160079394, 4294953267, 2062061576,
	1775109900, 4292150795, 4224124170, 4257547273, 4257481737, 4257350665, 4258530827, 4252106753, 4247072817, 4257332671, 4257925836, 4253646968, 4245621513, 4247068702, 4247265308, 4247527707, 4247921176, 4248642835, 4248969224, 4254818316, 4261403174, 4260735252, 4260806482, 4261013859, 4277855796, 4277782803, 4261003027, 4261067281, 4260999693, 4260932362, 4260865288, 4277509638, 4260534788, 4260336387, 4259941122, 4259480578, 4259150850, 4258887938, 4258427394, 4258033154, 4257836290, 4258097920, 4259546624, 4260672538, 4259359016, 4208030478, 4260798223, 1910740765,
	1808729867, 4225238539, 4157015306, 4240638985, 4257416201, 4257350666, 4258399755, 4252893700, 4246546473, 4257003706, 4257860043, 4254634119, 4245884684, 4247068702, 4247265308, 4247527706, 4247855639, 4248577042, 4248968967, 4254555404, 4261399838, 4260794624, 4260862471, 4260801326, 4260876382, 4261145423, 4261008926, 4261002511, 4261000721, 4260999181, 4260931080, 4260731909, 4260468483, 4260204803, 4259809282, 4259348994, 4259019522, 4258690562, 4258296323, 4258032385, 4258755840, 4260405775, 4260016934, 4258104091, 4256913665, 4206185728, 4293758487, 1893830427,
	1756824585, 4292019466, 4291888138, 4291494921, 4224123913, 4240442634, 4257940746, 4254598664, 4245887000, 4256017068, 4257662408, 4256213925, 4246673942, 4246805531, 4247133979, 4247396121, 4247789590, 4248511249, 4248837382, 4254424075, 4261398816, 4260132608, 4259803650, 4260662786, 4260864272, 4260804161, 4261011041, 4261078331, 4261004559, 4260999948, 4260932877, 4260864775, 4260534788, 4260204803, 4259743747, 4259217410, 4259019779, 4258756099, 4258952448, 4260206084, 4260608032, 4258764837, 4257112585, 4255927040, 4254351362, 4204346624, 4293166868, 1876723993,
	306577408, 1936065026, 3112174085, 3952411141, 4289528583, 4290642953, 4257284873, 4256696844, 4245882888, 4253583499, 4257398979, 4257530303, 4249239867, 4246016273, 4247199772, 4247330328, 4247723797, 4248445713, 4248705797, 4254292747, 4261397280, 4259541248, 4258753026, 4259343105, 4260462593, 4260995588, 4260933152, 4261004884, 4261078613, 4261074210, 4261000968, 4260997898, 4260798471, 4260467715, 4260007171, 4259743748, 4259610880, 4260205056, 4260935704, 4259556394, 4257575700, 4256518144, 4254744832, 4253169666, 4253170178, 4203887616, 4292903699, 1876395801,
	0, 0, 0, 369098752, 1261371392, 3617980935, 4257546760, 4224584205, 4248504070, 4249176909, 4257398464, 4257004220, 4254371722, 4245884684, 4247134237, 4247199000, 4247526676, 4248183313, 4248574726, 4254095883, 4261395999, 4259081216, 4257964546, 4258358529, 4259278081, 4260395520, 4261060865, 4261000971, 4261067831, 4261141088, 4261143616, 4261004045, 4260932868, 4260930568, 4260665602, 4260600320, 4261132814, 4260479531, 4258500386, 4257242116, 4255860992, 4253628673, 4252447489, 4252316673, 4252579329, 4203559168, 4292706067, 1876001305,
	16777216, 75431936, 50266112, 262144, 0, 1906573828, 4291298056, 4190700296, 4253815571, 4245295892, 4255358111, 4256280754, 4257003962, 4250950485, 4245687048, 4247330843, 4247461397, 4248051728, 4248377605, 4253898507, 4261395486, 4258620928, 4257307650, 4257635841, 4258424321, 4259410178, 4260528642, 4261059073, 4261067523, 4261070107, 4261138255, 4261144668, 4261075494, 4261003008, 4261135627, 4261008431, 4259622194, 4258296335, 4257371648, 4255072768, 4253103361, 4252381953, 4251922433, 4251791361, 4252119553, 4203164928, 4292508691, 1842511895,
	0, 0, 0, 55902208, 55902208, 528154624, 4155834887, 4273668102, 4240903696, 4247522058, 4248649794, 4256806071, 4255622566, 4256806067, 4250094920, 4245818119, 4247198226, 4248117522, 4248246535, 4253701643, 4261394718, 4258161152, 4256913922, 4257044737, 4257832962, 4258818562, 4259870466, 4260660738, 4261058817, 4261067521, 4261139723, 4261074999, 4261080167, 4261147758, 4260944205, 4259878691, 4258950144, 4257174528, 4254547458, 4253169153, 4252250369, 4251593985, 4251331328, 4251462657, 4251791105, 4202639616, 4292311827, 1808891927,
	0, 0, 0, 0, 67043328, 0, 2392588549, 4290839304, 4190109957, 4255258134, 4244768262, 4251674216, 4256477619, 4255293344, 4256345258, 4251871074, 4247330583, 4247065350, 4247523072, 4253438216, 4261393693, 4257766912, 4256453634, 4256584705, 4257241601, 4258160897, 4259212801, 4260264961, 4260859394, 4261060866, 4261067521, 4261141766, 4261081938, 4261147791, 4260933649, 4259934976, 4257239810, 4254875393, 4253497345, 4252381440, 4251528193, 4234422529, 4250937345, 4251134465, 4251528705, 4202377216, 4292114450, 1825405463,
	0, 0, 0, 0, 79626240, 0, 2530154265, 4290905097, 4205969669, 4257416457, 4252702485, 4244637191, 4252133996, 4255950760, 4254832278, 4256146592, 4255618957, 4252591958, 4250024233, 4254097174, 4261261853, 4257438208, 4255862274, 4256124673, 4256913153, 4257701377, 4258686977, 4259607553, 4260397825, 4260926721, 4261062915, 4261068544, 4261146915, 4260941112, 4260662784, 4257764354, 4255532289, 4253891329, 4252644097, 4251790593, 4250937345, 4250609153, 4250609153, 4250871809, 4251331841, 4202245888, 4291982866, 1825077271,
	0, 0, 0, 61472768, 0, 1491543333, 4291824656, 4222812164, 4256432903, 4255973637, 4257351691, 4252046869, 4244636933, 4249963855, 4255028630, 4255094676, 4255684494, 4257260685, 4258178940, 4259423557, 4260669464, 4257043712, 4255336962, 4255599361, 4256256001, 4257109761, 4257964033, 4258950145, 4259936770, 4260595457, 4260993794, 4261064960, 4261143058, 4260476714, 4259540224, 4256516866, 4254613249, 4253168897, 4251987457, 4251200001, 4250543360, 4250412033, 4250412289, 4250543360, 4251134721, 4201983232, 4291785490, 1808431383,
	0, 0, 50266112, 0, 553072439, 4023456533, 4256497668, 4239590151, 4256170502, 4255974150, 4255580164, 4257089546, 4253619989, 4245816580, 4246216223, 4251476321, 4254895237, 4256536707, 4258045813, 4259685445, 4260537111, 4256715008, 4254877186, 4254877185, 4255599105, 4256387585, 4257372929, 4258424577, 4259344641, 4260134145, 4260728322, 4260995328, 4261139727, 4260147494, 4258751488, 4255597570, 4253760257, 4252578305, 4251462401, 4250674688, 4250280704, 4250149376, 4250083840, 4250346752, 4250872065, 4201720576, 4291588370, 1808300311,
	0, 16777216, 41877504, 117385770, 3302364954, 4290642695, 4205707782, 4256039431, 4255777286, 4255711750, 4255777287, 4255252484, 4239655685, 4256043281, 4250209035, 4245619201, 4245952021, 4248844592, 4251931967, 4256397870, 4260734232, 4256517888, 4254745602, 4254417409, 4254745601, 4255664641, 4256584449, 4257635841, 4258621441, 4259476481, 4260398338, 4260926464, 4261202957, 4259883556, 4258159872, 4254941186, 4253300481, 4251921921, 4250871553, 4250280705, 4249952257, 4249821185, 4249952769, 4250346497, 4250674945, 4201523456, 4291522577, 1808102421,
	0, 16777216, 41877504, 111804416, 3181117700, 4290642182, 4188733959, 4255711750, 4255580678, 4255646214, 4238606854, 4238868742, 4289462533, 4188733443, 4223075848, 4255648780, 4252305415, 4249486336, 4247322624, 4252252934, 4260996892, 4256123392, 4254286082, 4254088961, 4254286081, 4255008001, 4255730177, 4256781569, 4257701633, 4258687490, 4259871234, 4260727552, 4261201165, 4259751458, 4257568000, 4254350338, 4252709889, 4251527937, 4250674433, 4250018049, 4249755393, 4249689857, 4249821185, 4250018305, 4250543617, 4201260800, 4291391250, 1791128341,
	0, 0, 33488896, 0, 218103808, 3281322243, 4290249223, 4188340742, 4255384070, 4204986886, 4289593605, 4288348420, 3833987332, 4289462789, 4289528067, 4238802946, 4222550531, 4256565253, 4256630020, 4258349066, 4260471580, 4255926016, 4253957890, 4253761025, 4253826562, 4254154497, 4254876417, 4255861761, 4256978945, 4257899009, 4259213569, 4260331776, 4261199116, 4259554337, 4257042944, 4253628418, 4252119041, 4251068417, 4250280449, 4249755393, 4249624065, 4249492737, 4232781313, 4233175297, 4250543617, 4217972480, 4291325712, 1774351381,
	0, 0, 0, 41877504, 65536, 253886464, 3348562179, 4289855750, 4137746694, 4289593605, 4019257603, 1531838466, 301989888, 1868562434, 3498377475, 4288217347, 4288807170, 4255122177, 4255449088, 4258152201, 4260537883, 4256056064, 4254089219, 4253563649, 4253367298, 4253695233, 4254154497, 4255073793, 4256256001, 4257307393, 4258556417, 4260067584, 4261197580, 4259488288, 4256714240, 4253103362, 4251659521, 4250543104, 4249886464, 4249558529, 4249361409, 4249427457, 4249624065, 4250083841, 4250740738, 4184744960, 4258361872, 1858435095,
	0, 0, 0, 0, 41877504, 65536, 303824896, 3365208323, 4289855748, 3246194946, 672727040, 0, 131072, 0, 50331648, 960102400, 3331129602, 4272489218, 4221304833, 4256836613, 4261264165, 4258951688, 4255005440, 4253497858, 4253235713, 4253301249, 4253826305, 4254548225, 4255467521, 4256715777, 4257899010, 4259475456, 4261130251, 4259356447, 4256385792, 4252643842, 4251265281, 4250346241, 4249820672, 4249361408, 4249427201, 4249624065, 4250083841, 4250346241, 4184614144, 4290205448, 4293036826, 1404198671,
	0, 0, 0, 0, 0, 41877504, 0, 340525056, 1684865026, 50331648, 0, 75431936, 16777216, 61472768, 83820544, 0, 1854865410, 4289135106, 4187423233, 4253549312, 4254743817, 4259682079, 4259941397, 4255992065, 4236588032, 4252907522, 4253366785, 4253892097, 4254876673, 4256058881, 4257176065, 4258751744, 4260997130, 4259356188, 4256254464, 4252315393, 4251002625, 4250083585, 4249623808, 4249492481, 4249624065, 4250018049, 4216790528, 4219811074, 4291916565, 3838869019, 1537365006, 33554432,
	0, 0, 0, 0, 0, 0, 16777216, 0, 0, 65536, 41877504, 0, 0, 0, 75431936, 55902208, 1149435907, 4288413954, 4203806977, 4235985409, 4215996416, 4216851968, 4239812371, 4260535582, 4291717899, 4187043328, 4236194817, 4253761026, 4254417153, 4255467521, 4256781826, 4258357504, 4260930826, 4259224604, 4255860480, 4252052994, 4250805761, 4250083328, 4249755137, 4249821185, 4232912128, 4184286208, 4289681164, 4291984154, 2579065881, 390201344, 0, 33554176,
	0, 0, 0, 0, 0, 0, 0, 33488896, 75431936, 16777216, 0, 0, 0, 16777216, 33488896, 0, 410255360, 4137353474, 4288217345, 4287103233, 4285137665, 4282646528, 4282122240, 4235798790, 3856961822, 4293824279, 4256189955, 4220269824, 4254088706, 4255139330, 4256453378, 4258094848, 4260732937, 4259289882, 4255532032, 4251856130, 4250805504, 4250214913, 4249886721, 4183169792, 4253760516, 4291917336, 3502863898, 1167280395, 0, 0, 61494528, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33488896, 16777216, 3079405569, 4052680961, 3917938945, 3950510337, 3915514112, 4015129089, 2906587136, 376635392, 2463991320, 4277180702, 4292507151, 4188356864, 4238295040, 4256256258, 4257831680, 4260667145, 4259289882, 4255531776, 4251855873, 4251002881, 4233568000, 4201326080, 4290273039, 4157504027, 2158977813, 150994944, 0, 67086848, 33488896, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 134217728, 354680832, 303824896, 304742400, 289144832, 323158016, 79658752, 1, 0, 1036806156, 3387856925, 4294548252, 4274873606, 4206250752, 4257502720, 4260535306, 4259289627, 4255597824, 4251790082, 4201128704, 4288366087, 4292114713, 3166991387, 813643013, 0, 65792, 61494528, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33488896, 67086848, 0, 83886080, 2011399191, 4059537951, 4294350356, 4208419072, 4243690503, 4259224092, 4221976064, 4203755777, 4291653395, 3973086236, 1789549331, 0, 0, 79658752, 16777216, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16777216, 16777216, 16777216, 16777216, 16777216, 16777216, 16777216, 0, 0, 61494528, 65793, 0, 684875520, 3035996189, 4294945820, 4294949908, 4192247842, 4292440076, 4292443674, 2831578137, 544151296, 0, 33554431, 41910016, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16777216, 79658752, 0, 0, 1643219727, 3875390247, 4294420257, 3721691673, 1420186895, 0, 0, 79658752, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 50298624, 50331519, 0, 451631104, 1591307264, 273612800, 0, 67086848, 41877504, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 67086848, 1, 1, 1, 61494528, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
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
