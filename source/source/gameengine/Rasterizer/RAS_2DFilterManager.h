/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
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
 * Contributor(s): Pierluigi Grassi, Porteries Tristan.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file RAS_2DFilterManager.h
 *  \ingroup bgerast
 */

#ifndef __RAS_2DFILTERMANAGER_H__
#define __RAS_2DFILTERMANAGER_H__

#include "RAS_2DFilterData.h"
#include "RAS_2DFilter.h"
#include <map>
#include <vector>

class RAS_ICanvas;
class RAS_Rasterizer;
class RAS_OffScreen;
class RAS_2DFilter;

typedef std::map<unsigned int, RAS_2DFilter *> RAS_PassTo2DFilter;

class RAS_2DFilterManager
{
public:
	/// Profiler hook (set by the game engine): called with -1 before the filters, then with
	/// each filter pass index after it renders, to time every pass on the GPU.
	static void (*ProfilePassHook)(int pass);

	/* Note: Keep it in order of pass index!! These values are internal keys (custom filters are
	 * offset by reservedPassIndex and the profiler reports them); the *render* order is given by
	 * RenderOrderKey(), which runs fog/clouds/rain/camera DOF before Tonemap (HDR) and FXAA
	 * after it, without renumbering anything. */
	enum FILTER_RESERVED_PASS {
		FILTERPASS_SSGI         = 0,
        FILTERPASS_SSGI_IMAGE   = 1,
		FILTERPASS_SSR          = 2,
		FILTERPASS_SSR_BLUR     = 3,
		FILTERPASS_SSAO         = 4,
		FILTERPASS_BLOOM        = 5,
		/* BLOOM HAS EXTRA PASSES .. [5 ~ 12] */
		FILTERPASS_LIGHTSCATTER = 13,
		/* LIGHTSCATTER HAS ONE EXTRA PASS = 14 */
		FILTERPASS_FXAA         = 15,
		FILTERPASS_TONEMAP      = 16,
		FILTERPASS_RAIN         = 17,
		FILTERPASS_CLOUDS       = 18,
		/* Volumetric Fog after the clouds: the fog also covers the sky and the clouds behind it */
		FILTERPASS_VFOG         = 19,
		/* At Half/Quarter resolution the fog pass renders into a small offscreen and this pass
		 * upscales it onto the image */
		FILTERPASS_VFOG_IMAGE   = 20,
		FILTERPASS_LENSFLARE    = 21,
		/* Camera FX (KX_Camera game_fx), only present while their effects are on */
		FILTERPASS_CAMERA_DOF   = 22,
		FILTERPASS_CAMERA_LENS  = 23,
		/* Half resolution color + circle of confusion read by the half resolution DOF gather
		 * (desktop); runs right before it, see RenderOrderKey() */
		FILTERPASS_CAMERA_DOF_REDUCE = 24,
		/* The scene's compositor nodes (KX_CompositorFilter), last of the built-in passes */
		FILTERPASS_COMPOSITOR   = 25,
		/* Temporal anti-aliasing (RAS_TAA2DFilter.glsl), right after Tonemap, before FXAA */
		FILTERPASS_TAA          = 26
	};
	/* Number of steps reserved for BuildInFilters, this means that any filters added later will be relocated to later steps.
	 * It must be past the last reserved pass: with 17 the custom filter of index 0 landed on FILTERPASS_LENSFLARE. */
	const int reservedPassIndex = FILTERPASS_TAA + 1;
	/* Textures drawn before the compositor pass (input chains of its Blur / Lens Distortion nodes):
	 * reserved indices far past any custom filter, rendered right before FILTERPASS_COMPOSITOR. */
	static const unsigned int FILTERPASS_COMPOSITOR_CACHE = 0x40000000;

	enum FILTER_MODE {
		FILTER_ENABLED = -2,
		FILTER_DISABLED = -1,
		FILTER_NOFILTER = 0,
		FILTER_MOTIONBLUR,
		FILTER_BLUR,
		FILTER_SHARPEN,
		FILTER_DILATION,
		FILTER_EROSION,
		FILTER_LAPLACIAN,
		FILTER_SOBEL,
		FILTER_PREWITT,
		FILTER_GRAYSCALE,
		FILTER_SEPIA,
		FILTER_INVERT,
		FILTER_CUSTOMFILTER,
		FILTER_FXAA,

		FILTER_BLOOM,
		FILTER_TONEMAP,
		FILTER_SSAO,

        FILTER_OUTLINE,
		FILTER_LIGHTSCATTER,
		FILTER_SSR,
		FILTER_NUMBER_OF_FILTERS
	};

	RAS_2DFilterManager(BuildInFilters filters);
	virtual ~RAS_2DFilterManager();

	/** Applies the filters to the scene.
	 * \param rasty The rasterizer used for draw commands.
	 * \param canvas The canvas containing the screen viewport.
	 * \param inputofs The off screen used as input of the first filter.
	 * \param targetofs The off screen used as output of the last filter.
	 * \return The last used off screen, if none filters were rendered it's the
	 * same off screen than inputofs.
	 */
	RAS_OffScreen *RenderFilters(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *inputofs, RAS_OffScreen *targetofs, const float (&sun_screen_pos)[2]);

	/// Add a filter to the stack of filters managed by this object.
	RAS_2DFilter *AddFilter(RAS_2DFilterData& filterData, bool use_reserved);

	/// Removes the filters at a given pass index.
	void RemoveFilterPass(unsigned int passIndex);
	/// Removes a built-in filter at a reserved pass index (FILTERPASS_*).
	void RemoveReservedFilterPass(unsigned int passIndex);

	/// Get the existing filter for the given pass index.
	RAS_2DFilter *GetFilterPass(unsigned int passIndex, bool use_reserved);

	/** Returns the Tonemap filter, creating it on the fly (with the given
	 * parameters) if the scene didn't have it enabled at load time.
	 * This lets filterManager.changeTonemapValues() turn the filter on from
	 * Python even when its "Post Processing Shaders" checkbox started off.
	 */
	RAS_2DFilter *EnsureTonemapFilter(const BuildInFilters& filters);

	/// Same as EnsureTonemapFilter(), but for the SSAO (Ambient Occlusion) filter.
	RAS_2DFilter *EnsureSSAOFilter(const BuildInFilters& filters);

	/// Same as EnsureTonemapFilter(), but for the FXAA filter.
	RAS_2DFilter *EnsureFxaaFilter(const BuildInFilters& filters);

	/// Same as EnsureTonemapFilter(), but for the TAA filter.
	RAS_2DFilter *EnsureTaaFilter(const BuildInFilters& filters);

	/** Sub-pixel offset (in pixels, -0.5..0.5) the cameras must add to their projection for
	 * the frame about to be drawn. False when TAA is off or unsupported: no jitter at all. */
	bool GetTaaJitter(float jitter[2]) const;

	/** False while the frame can't use the TAA history (split screen cameras, stereo, wireframe):
	 * no jitter, and the pass only sharpens. Set by the render pipeline before drawing. */
	void SetTaaAllowed(bool allowed);

	/** Temporal upscaling (RANGE_TAAU, proof of concept): with a reduced render scale and TAA as
	 * the last pass, the TAA pass draws at the window size into its own off screen. Allowed only
	 * for a single scene drawn once (no overlay scene, no per eye stereo): set by the pipeline. */
	void SetTaauAllowed(bool allowed);
	/// True when at least one pass would draw (RenderFilters() would not discard).
	bool HasActiveFilters() const;
	/** The window size result of the last RenderFilters() when it upscaled, else nullptr.
	 * Valid until the next RenderFilters() of this manager. */
	RAS_OffScreen *GetUpscaledOutput() const;
	/// RANGE_TAAU as a render scale (0.25..1), 0 when off.
	static float TaauScale();

	/** Enables a built-in post-processing effect, creating its filter pass if
	 * needed. Multi-pass effects are implemented by KX_2DFilterManager.
	 */
	virtual bool SetBuiltinFilterEnabled(FILTER_MODE mode, bool enabled);

	/// Time given to the filters as bgl_Time, in seconds.
	void SetFrameTime(float time);

protected:
	RAS_PassTo2DFilter m_filters;

private:
	/// bgl_Time, bgl_Frame, bgl_PreviousTexture... shared by all the filters.
	RAS_2DFilter::FrameInputs m_frameInputs;
	/// Size of m_frameInputs.previousTexture, only allocated while a filter samples it.
	int m_previousWidth = 0;
	int m_previousHeight = 0;

	/// Copy the final image of the chain for bgl_PreviousTexture of the next frame.
	void UpdatePreviousTexture(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *finalofs, const int viewport[4]);

	/// Render order of a pass index (reserved passes remapped, custom filters keep their order after them).
	static unsigned int RenderOrderKey(unsigned int passIndex);

	/// Last view-projection of each viewport (split screen cameras / embedded game share this
	/// manager). Stored unpacked to avoid aligned types in a std::vector.
	struct PrevViewProjection {
		int viewport[4];
		float matrix[16];
	};
	std::vector<PrevViewProjection> m_prevViewProjections;

	/// Size and viewport of the Volumetric Clouds history; a different viewport (another
	/// split screen camera) or size invalidates it so the next frame marches every pixel.
	int m_cloudHistoryWidth = 0;
	int m_cloudHistoryHeight = 0;
	int m_cloudHistoryViewport[4] = {0, 0, 0, 0};

	/// Copy the clouds filter output (color) and the scene depth for the next frame's reuse.
	void UpdateCloudHistory(RAS_Rasterizer *rasty, RAS_OffScreen *cloudofs, RAS_OffScreen *depthofs, const int viewport[4]);

	/** Shared temporal history (Fase 2 of docs/plano-efeitos-render.md): one per (effect,
	 * viewport). color is the resolved low resolution effect buffer of the last frame (RGBA16F),
	 * depth the scene depth it was resolved against, viewProjection the camera of that frame. */
	struct TemporalHistory {
		int effect = -1;
		int viewport[4] = {0, 0, 0, 0};
		unsigned int color = 0;
		unsigned int depth = 0;
		int width = 0;
		int height = 0;
		int depthWidth = 0;
		int depthHeight = 0;
		float viewProjection[16];
		int lastFrame = 0;
		bool valid = false;
	};
	std::vector<TemporalHistory> m_temporalHistories;
	/// -1 unknown, 0 not enough texture units / unsupported, 1 available.
	int m_temporalSupported = -1;

	/** Render the temporal resolve attached to a filter (after it drew its off screen), then
	 * copy the resolved buffer and the scene depth into the history of this viewport. */
	void RenderTemporalResolve(RAS_2DFilter *filter, RAS_Rasterizer *rasty, RAS_ICanvas *canvas,
	                           RAS_OffScreen *depthofs, RAS_OffScreen *colorofs, RAS_OffScreen *targetofs,
	                           const float (&sun_screen_pos)[2], const int viewport[4]);

	/** TAA history: the output of the TAA pass of the last frame (full resolution), the
	 * viewport, view-projection and jitter it was drawn with. */
	RAS_OffScreen *m_taaHistoryOfs = nullptr;
	int m_taaWidth = 0;
	int m_taaHeight = 0;
	int m_taaViewport[4] = {0, 0, 0, 0};
	int m_taaLastFrame = 0;
	bool m_taaValid = false;
	float m_taaViewProjection[16] = {0.0f};
	float m_taaHistoryJitter[2] = {0.0f, 0.0f};
	/// -1 unknown, 0 not enough texture units / RANGE_TAA_OFF / no buffer, 1 available.
	int m_taaSupported = -1;
	bool m_taaAllowed = true;
	/// Halton phases of the jitter: 8, more when upscaling (ceil(8 / scale^2), at most 64).
	int m_taaPhases = 8;
	bool m_taauAllowed = false;
	/// Window size output of the upscaling TAA pass (also what the history copies).
	RAS_OffScreen *m_taauOfs = nullptr;
	/// Second window size off screen: ping pong for the passes after the upscaling.
	RAS_OffScreen *m_taauOfs2 = nullptr;
	RAS_OffScreen *m_upscaledOutput = nullptr;

	/// Jitter of a frame number (Halton 2,3 over 8 frames), in pixels.
	static void TaaJitterOfFrame(int frame, int phases, float jitter[2]);
	/// Before the TAA pass: (re)allocate the history and give it to the filter if still valid.
	void PrepareTaaHistory(RAS_Rasterizer *rasty, int width, int height, const int viewport[4]);
	/// After the TAA pass: copy its output into the history.
	bool EnsureTaauOffScreen(int width, int height);
	void CommitTaaHistory(RAS_Rasterizer *rasty, RAS_OffScreen *outputofs, const int viewport[4]);

	/** Creates a filter matching the given filter data. Returns nullptr if no
	 * filter can be created with such information.
	 */
	RAS_2DFilter *CreateFilter(RAS_2DFilterData& filterData);
	/// Only return a new instanced filter.
	virtual RAS_2DFilter *NewFilter(RAS_2DFilterData& filterData) = 0;
};

#endif // __RAS_2DFILTERMANAGER_H__
