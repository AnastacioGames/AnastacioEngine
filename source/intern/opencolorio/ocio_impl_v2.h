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
 */

/* Handles behind the C API when built against OpenColorIO 2.x (1.x keeps
 * using the library types directly). Include after OpenColorIO.h. */

#ifndef __OCIO_IMPL_V2_H__
#define __OCIO_IMPL_V2_H__

#define OCIO_V2

/* 2.x applies pixels through a CPU processor; keep it next to the processor so
 * the per-pixel calls don't fetch it each time. */
struct OCIO_ProcessorV2 {
	ConstProcessorRcPtr processor;
	ConstCPUProcessorRcPtr cpu;
};

/* 2.x split the 1.x DisplayTransform: display/view live in DisplayViewTransform,
 * exposure/gamma (linear and display CC) and the looks override in the
 * LegacyViewingPipeline. */
struct OCIO_DisplayTransformV2 {
	DisplayViewTransformRcPtr dvt;
	LegacyViewingPipelineRcPtr pipeline;
};

#endif  /* __OCIO_IMPL_V2_H__ */
