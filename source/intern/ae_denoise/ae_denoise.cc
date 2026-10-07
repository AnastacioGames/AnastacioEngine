/* Lightmap denoiser for the "Baked Lighting" operator (anastacio_lightmap.py), loaded with ctypes
 * (ae_denoise.dll on Windows, libae_denoise.so on Linux, next to the executable).
 * Thin C wrapper over Intel Open Image Denoise (Apache-2.0). */

#include <OpenImageDenoise/oidn.h>

#ifdef _WIN32
#  define AE_EXPORT extern "C" __declspec(dllexport)
#else
#  define AE_EXPORT extern "C" __attribute__((visibility("default")))
#endif

AE_EXPORT int ae_denoise_version(void)
{
	return OIDN_VERSION;
}

/* color/output: width*height RGB floats (linear HDR), in place. Returns 0 on success, 1 on error. */
AE_EXPORT int ae_denoise(float *color, int width, int height)
{
	OIDNDevice device = oidnNewDevice(OIDN_DEVICE_TYPE_DEFAULT);
	oidnCommitDevice(device);
	OIDNFilter filter = oidnNewFilter(device, "RT");
	oidnSetSharedFilterImage(filter, "color", color, OIDN_FORMAT_FLOAT3, width, height, 0, 0, 0);
	oidnSetSharedFilterImage(filter, "output", color, OIDN_FORMAT_FLOAT3, width, height, 0, 0, 0);
	oidnSetFilter1b(filter, "hdr", true);
	oidnCommitFilter(filter);
	oidnExecuteFilter(filter);
	const char *message;
	int error = oidnGetDeviceError(device, &message) != OIDN_ERROR_NONE;
	oidnReleaseFilter(filter);
	oidnReleaseDevice(device);
	return error;
}
