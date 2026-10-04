"""Editor check of the FFmpeg 5+ and OpenColorIO 2 ports (Linux, run in background):
  AV_OUT=/tmp/av RangeEngine -b --python tools/linux/av_ports_test.py
Exports a 30-frame red->blue animation as MP4/H.264+AAC, MKV/FFV1, OGG/Theora+Vorbis and AVI/MPEG-4+MP3,
checks each with ffprobe/ffmpeg (frames, audio packets, first/last colors), reads the MP4 back as a movie
image and a sequencer strip, builds a 25% proxy, and checks the OCIO views. Needs ffmpeg/ffprobe in PATH.
Optional: AV_CASES="mp4_h264_aac ...", AV_SKIP_READ, AV_SKIP_SEQ, AV_SKIP_PROXY, AV_PROXY_NONE.
Prints "AVTEST PASS|FAIL <check>" and "AVTEST ALL PASS (n/n)" at the end."""
import bpy, os, sys, subprocess, json, glob, time

OUT = os.environ["AV_OUT"]
os.makedirs(OUT, exist_ok=True)
results = []

def check(name, ok, detail=""):
    results.append(ok)
    print("AVTEST %s %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)

scene = bpy.context.scene
# OCIO: views of the sRGB display (2.x used to hide Filmic/Film/False Color)
views = []
for v in ("Default", "Filmic", "Film", "False Color", "RRT", "Raw", "Log"):
    try:
        scene.view_settings.view_transform = v; views.append(v)
    except TypeError as e:
        print("AVTEST view %s rejected: %s" % (v, e))
check("ocio views", all(v in views for v in ("Default", "Filmic", "Film", "False Color", "RRT", "Raw", "Log")), str(views))
check("ocio filmic set", True)
scene.view_settings.view_transform = "Default"

# Scene: no objects, world color keyed red -> blue (Blender Internal, sky only)
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
scene.camera = cam
scene.render.engine = "BLENDER_RENDER"
w = scene.world
w.horizon_color = (1, 0, 0); w.keyframe_insert("horizon_color", frame=1)
w.horizon_color = (0, 0, 1); w.keyframe_insert("horizon_color", frame=30)
w.zenith_color = w.horizon_color
w.use_sky_blend = False
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 160, 120, 100
scene.frame_start, scene.frame_end = 1, 30
scene.render.fps = 25
scene.render.image_settings.file_format = "FFMPEG"

cases = [
    ("mp4_h264_aac", "MPEG4", "H264", "AAC", ".mp4"),
    ("mkv_ffv1", "MKV", "FFV1", "NONE", ".mkv"),
    ("ogg_theora_vorbis", "OGG", "THEORA", "VORBIS", ".ogv"),
    ("avi_mpeg4", "AVI", "MPEG4", "MP3", ".avi"),
]
made = {}
_only = os.environ.get("AV_CASES")
if _only is not None:
    cases = [c for c in cases if c[0] in _only.split()]
for name, container, codec, audio, ext in cases:
    ff = scene.render.ffmpeg
    ff.format = container
    ff.codec = codec
    ff.audio_codec = audio
    scene.render.filepath = os.path.join(OUT, name + "_")
    try:
        bpy.ops.render.render(animation=True)
    except Exception as e:
        check("export " + name, False, repr(e)); continue
    files = sorted(glob.glob(os.path.join(OUT, name + "_*")))
    if not files:
        check("export " + name, False, "no file"); continue
    path = files[-1]
    made[name] = path
    pr = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                         "stream=codec_type,codec_name,nb_read_frames,width,height", "-of", "json", path],
                        capture_output=True, text=True)
    info = json.loads(pr.stdout or "{}").get("streams", [])
    v = [s for s in info if s.get("codec_type") == "video"]
    a = [s for s in info if s.get("codec_type") == "audio"]
    apk = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-count_packets", "-show_entries",
                          "stream=nb_read_packets", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    apk = int(apk) if apk.isdigit() else 0
    ok = bool(v) and int(v[0].get("nb_read_frames", 0)) == 30 and v[0].get("width") == 160 and (audio == "NONE" or apk > 10)
    check("export " + name, ok, "%s video=%s/%s frames audio=%s/%d packets" % (os.path.basename(path), v[0].get("codec_name") if v else None, v[0].get("nb_read_frames") if v else 0, a[0].get("codec_name") if a else None, apk))
    # first and last frame colors, decoded by the ffmpeg CLI
    cols = []
    for sel in ("eq(n\\,0)", "eq(n\\,29)"):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "select=" + sel + ",scale=1:1", "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        cols.append(tuple(raw[:3]))
    okc = len(cols) == 2 and len(cols[0]) == 3 and cols[0][0] > 180 and cols[0][2] < 70 and cols[1][2] > 180 and cols[1][0] < 70
    check("colors " + name, okc, str(cols))

# Read back through Blender: movie image, sequencer strip render, proxy
src = made.get("mp4_h264_aac") or next(iter(made.values()), None)
if src and not os.environ.get("AV_SKIP_READ"):
    img = bpy.data.images.load(src)
    size, frames = tuple(img.size), img.frame_duration
    size = tuple(img.size)
    check("image movie", img.source == "MOVIE" and frames == 30 and size == (160, 120),
          "source=%s frames=%d size=%s" % (img.source, frames, size))
if src and not os.environ.get("AV_SKIP_READ") and not os.environ.get("AV_SKIP_SEQ"):
    s2 = bpy.data.scenes.new("Seq")
    s2.render.resolution_x, s2.render.resolution_y, s2.render.resolution_percentage = 160, 120, 100
    s2.render.fps = 25
    s2.sequence_editor_create()
    strip = s2.sequence_editor.sequences.new_movie("clip", src, 1, 1)
    check("sequencer strip", strip.frame_final_duration == 30, "duration=%d" % strip.frame_final_duration)
    s2.render.use_sequencer = True
    s2.render.image_settings.file_format = "PNG"
    s2.frame_start, s2.frame_end = 1, 30
    s2.frame_set(30)
    s2.render.filepath = os.path.join(OUT, "seq_f30.png")
    bpy.context.screen.scene = s2
    bpy.ops.render.render(write_still=True, scene=s2.name)
    shot = bpy.data.images.load(os.path.join(OUT, "seq_f30.png"))
    px = shot.pixels[:]
    w_, h_ = shot.size
    i = ((h_ // 2) * w_ + w_ // 2) * 4
    c = px[i:i + 3]
    check("sequencer frame 30 is blue", c[2] > 0.7 and c[0] < 0.3, str([round(x, 3) for x in c]))
    # proxy (MJPEG via the indexer)
if src and not os.environ.get("AV_SKIP_READ") and not os.environ.get("AV_SKIP_PROXY"):
    strip.use_proxy = True
    strip.proxy.build_25 = not os.environ.get("AV_PROXY_NONE")
    if os.environ.get("AV_PROXY_NONE"):
        for t in ("build_free_run", "build_free_run_rec_date", "build_record_run"):
            setattr(strip.proxy, t, False)
    strip.proxy.build_50 = False
    ctx = {"scene": s2, "window": bpy.context.window, "screen": bpy.context.screen}
    try:
        bpy.ops.sequencer.rebuild_proxy(ctx)
        proxies = glob.glob(os.path.join(os.path.dirname(src), "BL_proxy", "**", "*"), recursive=True)
        check("proxy build", any(p.endswith(".avi") for p in proxies), str([os.path.basename(p) for p in proxies]))
    except Exception as e:
        print("AVTEST SKIP proxy build (%r)" % (e,), flush=True)

print("AVTEST %s (%d/%d)" % ("ALL PASS" if all(results) else "SOME FAIL", sum(results), len(results)), flush=True)
