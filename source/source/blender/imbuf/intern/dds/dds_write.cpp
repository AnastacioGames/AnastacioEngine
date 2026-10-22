/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <mutex>
#include <vector>
#define RGBCX_IMPLEMENTATION
#define RGBCX_USE_SMALLER_TABLES 1
#include "../../../../../extern/rgbcx/rgbcx.h"
extern "C" {
#include "BLI_fileops.h"
#include "IMB_imbuf_types.h"
#include "dds_api.h"
}
namespace {
float linear(float v) { return v <= .04045f ? v / 12.92f : powf((v + .055f) / 1.055f, 2.4f); }
float srgb_encode(float v) { return v <= .0031308f ? v * 12.92f : 1.055f * powf(v, 1.f / 2.4f) - .055f; }
unsigned char byte(float v) { return (unsigned char)(std::max(0.f, std::min(1.f, v)) * 255.f + .5f); }
bool pot(int v) { return v > 0 && (v & (v - 1)) == 0; }
/* Working pixels: linear straight-alpha. Alpha-weighted color prevents dark fringes. */
std::vector<float> reduce(const std::vector<float>& src, int w, int h, bool color)
{
    const int nw = std::max(1, w / 2), nh = std::max(1, h / 2);
    std::vector<float> dst(size_t(nw) * nh * 4);
    for (int y = 0; y < nh; ++y) for (int x = 0; x < nw; ++x) {
        float sum[4] = {0, 0, 0, 0};
        for (int dy = 0; dy < 2; ++dy) for (int dx = 0; dx < 2; ++dx) {
            const float *p = &src[(size_t(std::min(h - 1, y * 2 + dy)) * w + std::min(w - 1, x * 2 + dx)) * 4];
            for (int c = 0; c < 3; ++c) sum[c] += p[c] * (color ? p[3] : 1.f);
            sum[3] += p[3];
        }
        float *d = &dst[(size_t(y) * nw + x) * 4];
        for (int c = 0; c < 3; ++c) d[c] = color ? (sum[3] > 0 ? sum[c] / sum[3] : 0) : sum[c] / 4;
        d[3] = sum[3] / 4;
    }
    return dst;
}
bool write_u32(FILE *f, uint32_t v)
{
    const unsigned char b[4] = {(unsigned char)v, (unsigned char)(v >> 8), (unsigned char)(v >> 16), (unsigned char)(v >> 24)};
    return fwrite(b, 1, 4, f) == 4;
}
}
extern "C" bool imb_dds_write_dxt(const ImBuf *ibuf, const char *path, int format,
                                  int max_size, int quality, bool srgb)
{
    if (!ibuf || !ibuf->rect || ibuf->rect_float || !pot(ibuf->x) || !pot(ibuf->y) ||
        max_size < 0 || quality < 0 || quality > 18 || (format != 0 && format != 1 && format != 3)) return false;
    static std::once_flag initialized;
    std::call_once(initialized, []() { rgbcx::init(); });
    int w = ibuf->x, h = ibuf->y;
    const unsigned char *src = (const unsigned char *)ibuf->rect;
    bool alpha = false;
    std::vector<float> pixels(size_t(w) * h * 4);
    for (size_t i = 0; i < size_t(w) * h; ++i) {
        const float a = src[i * 4 + 3] / 255.f;
        alpha |= src[i * 4 + 3] != 255;
        for (int c = 0; c < 3; ++c) {
            float v = src[i * 4 + c] / 255.f;
            pixels[i * 4 + c] = srgb ? linear(v) : v;
        }
        pixels[i * 4 + 3] = a;
    }
    if (format == 0) format = alpha ? 3 : 1;
    if (format == 1 && alpha) return false;
    while (max_size && (w > max_size || h > max_size)) {
        pixels = reduce(pixels, w, h, srgb);
        w = std::max(1, w / 2); h = std::max(1, h / 2);
    }
    int levels = 1;
    for (int n = std::max(w, h); n > 1; n /= 2) ++levels;
    const int blocksize = format == 1 ? 8 : 16;
    uint32_t header[32] = {0};
    header[0] = 0x20534444; header[1] = 124; header[2] = 0x000a1007;
    header[3] = h; header[4] = w; header[5] = ((w + 3) / 4) * ((h + 3) / 4) * blocksize;
    header[7] = levels; header[19] = 32; header[20] = 4;
    header[21] = format == 1 ? 0x31545844 : 0x35545844;
    header[27] = levels > 1 ? 0x00401008 : 0x1000;
    FILE *f = BLI_fopen(path, "wb");
    if (!f) return false;
    bool ok = true;
    for (int i = 0; i < 32; ++i) ok = write_u32(f, header[i]) && ok;
    for (int level = 0; level < levels && ok; ++level) {
        for (int by = 0; by < (h + 3) / 4 && ok; ++by) for (int bx = 0; bx < (w + 3) / 4 && ok; ++bx) {
            unsigned char block[64], encoded[16];
            for (int y = 0; y < 4; ++y) for (int x = 0; x < 4; ++x) {
                /* DDS top-down, imbuf bottom-up, including partial mip blocks. */
                const float *p = &pixels[(size_t(h - 1 - std::min(h - 1, by * 4 + y)) * w + std::min(w - 1, bx * 4 + x)) * 4];
                unsigned char *d = &block[(y * 4 + x) * 4];
                for (int c = 0; c < 3; ++c) {
                    float v = srgb ? srgb_encode(p[c]) : p[c];
                    d[c] = byte(v);
                }
                d[3] = byte(p[3]);
            }
            if (format == 1) rgbcx::encode_bc1(quality, encoded, block, false, false);
            else rgbcx::encode_bc3(quality, encoded, block);
            ok = fwrite(encoded, 1, blocksize, f) == size_t(blocksize);
        }
        if (level + 1 < levels) {
            pixels = reduce(pixels, w, h, srgb);
            w = std::max(1, w / 2); h = std::max(1, h / 2);
        }
    }
    if (fclose(f) != 0) ok = false;
    if (!ok) BLI_delete(path, false, false);
    return ok;
}
