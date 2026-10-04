"""Runtime check of bge.texture.VideoFFmpeg (FFmpeg 5+ port), through the player Python main loop:
  VID_DIR=<dir> RangeRuntime -p tools/linux/video_texture_test.py <any>.range
VID_DIR holds h264.mp4 mpeg4.avi vp9.webm mjpeg.avi, each 1 s red, 1 s green, 1 s blue at 25 fps, 160x120, e.g.:
  ffmpeg -f lavfi -i color=c=red:s=160x120:d=1:r=25 -f lavfi -i color=c=lime:s=160x120:d=1:r=25 \
         -f lavfi -i color=c=blue:s=160x120:d=1:r=25 -filter_complex "[0][1][2]concat=n=3:v=1[v]" -map "[v]" \
         -c:v libx264 -pix_fmt yuv420p h264.mp4
Expected: "VIDTEST <file> ... seq=RGB"; with VID_REPEAT=-1 VID_SECONDS=7.5 the loop gives seq=RGBRGBRG."""
import os
import time
from Range import logic, texture

DIR = os.environ["VID_DIR"]
names = os.environ.get("VID_FILES", "h264.mp4 mpeg4.avi vp9.webm mjpeg.avi").split()

def dominant(img, size):
    w, h = size
    i = ((h // 2) * w + w // 2) * 4
    r, g, b = img[i], img[i + 1], img[i + 2]
    if r > 200 and g < 60 and b < 60: return "R"
    if g > 200 and r < 60 and b < 60: return "G"
    if b > 200 and r < 60 and g < 60: return "B"
    return "?(%d,%d,%d)" % (r, g, b)

for name in names:
    try:
        v = texture.VideoFFmpeg(os.path.join(DIR, name))
        v.repeat = int(os.environ.get('VID_REPEAT', '0'))
        v.play()
        seq = []
        t0 = time.time()
        while time.time() - t0 < float(os.environ.get('VID_SECONDS', '4')):
            logic.NextFrame()
            img = v.image
            v.refresh()
            if img is not None and len(img) > 0:
                c = dominant(img, v.size)
                if not seq or seq[-1] != c:
                    seq.append(c)
            time.sleep(0.01)
        print("VIDTEST %s size=%s status=%s seq=%s" % (name, tuple(v.size), v.status, "".join(seq)), flush=True)
        v.stop()
    except Exception as e:
        print("VIDTEST %s ERROR %r" % (name, e), flush=True)
print("VIDTEST done", flush=True)
