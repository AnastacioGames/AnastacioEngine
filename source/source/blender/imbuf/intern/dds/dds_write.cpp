/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <mutex>
#include <vector>
#define RGBCX_IMPLEMENTATION
#define RGBCX_USE_SMALLER_TABLES 1
#include "../../../../../extern/rgbcx/rgbcx.h"
#ifdef WITH_KTX2_ENCODER
#  include "basisu_comp.h"
#endif
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
/* Working pixels: linear straight-alpha. Alpha-weighted color prevents dark fringes.
 * Normal maps (BC5) average the decoded vectors and renormalize them, so mips keep unit length. */
void renormalize(float *p)
{
    float v[3], len = 0;
    for (int c = 0; c < 3; ++c) { v[c] = p[c] * 2.f - 1.f; len += v[c] * v[c]; }
    if (len < 1e-12f) { p[0] = p[1] = .5f; p[2] = 1.f; return; }
    len = 1.f / sqrtf(len);
    for (int c = 0; c < 3; ++c) p[c] = v[c] * len * .5f + .5f;
}
std::vector<float> reduce(const std::vector<float>& src, int w, int h, bool color, bool normal = false)
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
        if (normal) renormalize(d);
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
        max_size < 0 || quality < 0 || quality > 18 || (format != 0 && format != 1 && format != 3 && format != 5)) return false;
    /* BC5 stores tangent-space X/Y only; Z is rebuilt by the loader and the shader. */
    const bool normal = format == 5;
    if (normal) srgb = false;
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
        if (normal) renormalize(&pixels[i * 4]);
    }
    if (format == 0) format = alpha ? 3 : 1;
    if (format == 1 && alpha) return false;
    if (normal) alpha = false;
    while (max_size && (w > max_size || h > max_size)) {
        pixels = reduce(pixels, w, h, srgb, normal);
        w = std::max(1, w / 2); h = std::max(1, h / 2);
    }
    int levels = 1;
    for (int n = std::max(w, h); n > 1; n /= 2) ++levels;
    const int blocksize = format == 1 ? 8 : 16;
    uint32_t header[32] = {0};
    header[0] = 0x20534444; header[1] = 124; header[2] = 0x000a1007;
    header[3] = h; header[4] = w; header[5] = ((w + 3) / 4) * ((h + 3) / 4) * blocksize;
    header[7] = levels; header[19] = 32; header[20] = normal ? 0x80000004u : 4;
    header[21] = format == 1 ? 0x31545844 : normal ? 0x32495441 : 0x35545844;
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
            else if (normal) rgbcx::encode_bc5(encoded, block, 0, 1, 4);
            else rgbcx::encode_bc3(quality, encoded, block);
            ok = fwrite(encoded, 1, blocksize, f) == size_t(blocksize);
        }
        if (level + 1 < levels) {
            pixels = reduce(pixels, w, h, srgb, normal);
            w = std::max(1, w / 2); h = std::max(1, h / 2);
        }
    }
    if (fclose(f) != 0) ok = false;
    if (!ok) BLI_delete(path, false, false);
    return ok;
}

/* KTX2 / Basis Universal. Colour: ETC1S (transcodes losslessly to ETC1/ETC2, also BC1/BC3/ASTC).
 * Tangent-space normal: UASTC with X in RGB and Y in alpha, the layout Basis turns into BC5 / EAC RG11.
 * Rows are written in ImBuf order (bottom first), the orientation the loader hands to OpenGL, and
 * KTXorientation says so; AnastacioNormalXY marks that X/Y layout, which UASTC alone does not imply.
 * quality is 0-100 (higher = better, larger); mipmaps come from the same filter as the DDS path. */
extern "C" bool imb_ktx2_write(const ImBuf *ibuf, const char *path, bool normal,
                               int max_size, int quality, bool srgb)
{
#ifdef WITH_KTX2_ENCODER
    if (!ibuf || !ibuf->rect || ibuf->rect_float || !pot(ibuf->x) || !pot(ibuf->y) ||
        max_size < 0 || quality < 0 || quality > 100) return false;
    if (normal) srgb = false;
    static std::once_flag initialized;
    std::call_once(initialized, []() { basisu::basisu_encoder_init(); });
    int w = ibuf->x, h = ibuf->y;
    const unsigned char *src = (const unsigned char *)ibuf->rect;
    std::vector<float> pixels(size_t(w) * h * 4);
    for (size_t i = 0; i < size_t(w) * h; ++i) {
        for (int c = 0; c < 3; ++c) {
            const float v = src[i * 4 + c] / 255.f;
            pixels[i * 4 + c] = srgb ? linear(v) : v;
        }
        pixels[i * 4 + 3] = src[i * 4 + 3] / 255.f;
        if (normal) renormalize(&pixels[i * 4]);
    }
    while (max_size && (w > max_size || h > max_size)) {
        pixels = reduce(pixels, w, h, srgb, normal);
        w = std::max(1, w / 2); h = std::max(1, h / 2);
    }
    basisu::vector<basisu::image> levels;
    for (;;) {
        basisu::image img(w, h);
        for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) {
            const float *p = &pixels[(size_t(y) * w + x) * 4];
            basisu::color_rgba &d = img(x, y);
            if (normal) {
                d.r = d.g = d.b = byte(p[0]);
                d.a = byte(p[1]);
            }
            else {
                d.r = byte(srgb ? srgb_encode(p[0]) : p[0]);
                d.g = byte(srgb ? srgb_encode(p[1]) : p[1]);
                d.b = byte(srgb ? srgb_encode(p[2]) : p[2]);
                d.a = byte(p[3]);
            }
        }
        levels.push_back(img);
        if (w == 1 && h == 1) break;
        pixels = reduce(pixels, w, h, srgb, normal);
        w = std::max(1, w / 2); h = std::max(1, h / 2);
    }
    /* the same settings basis_compress2() uses, which has no way to pass key/values */
    const basist::basis_tex_format mode = normal ? basist::basis_tex_format::cUASTC_LDR_4x4 :
                                                   basist::basis_tex_format::cETC1S;
    basisu::job_pool pool(std::max<uint32_t>(1, basisu::get_num_hardware_threads()));
    basisu::basis_compressor_params params;
    params.set_format_mode(mode);
    params.m_pJob_pool = &pool;
    params.m_multithreading = true;
    params.m_tex_type = basist::cBASISTexType2D;
    params.m_source_images.resize(1);
    params.m_source_images[0] = levels[0];
    if (levels.size() > 1) {
        params.m_source_mipmap_images.resize(1);
        params.m_source_mipmap_images[0].resize(levels.size() - 1);
        for (uint32_t i = 1; i < levels.size(); ++i) params.m_source_mipmap_images[0][i - 1] = levels[i];
    }
    params.m_write_output_basis_or_ktx2_files = false;
    params.set_srgb_options(srgb);
    params.set_ldr_srgb_channel_weights(srgb);
    params.m_mip_gen = false;
    params.m_create_ktx2_file = true;
    if (normal) params.m_ktx2_uastc_supercompression = basist::KTX2_SS_ZSTANDARD;
    params.set_format_mode_and_quality_effort(mode, quality, 4, false);
    /* "ru": rows go up, the ImBuf order. The loader reads both keys, see ktx2_api.cpp */
    basist::add_key_value(params.m_key_values, "KTXorientation", "ru");
    if (normal) basist::add_key_value(params.m_key_values, "AnastacioNormalXY", "1");
    basisu::basis_compressor compressor;
    if (!compressor.init(params) || compressor.process() != basisu::basis_compressor::cECSuccess) return false;
    const basisu::uint8_vec &file = compressor.get_output_ktx2_file();
    FILE *f = BLI_fopen(path, "wb");
    bool ok = f && fwrite(file.get_ptr(), 1, file.size(), f) == file.size();
    if (f && fclose(f) != 0) ok = false;
    if (!ok && f) BLI_delete(path, false, false);
    return ok;
#else
    (void)ibuf; (void)path; (void)normal; (void)max_size; (void)quality; (void)srgb;
    return false;
#endif
}
