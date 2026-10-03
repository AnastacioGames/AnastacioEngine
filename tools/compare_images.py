"""Compare two screenshots pixel by pixel.

Run with:  python tools/compare_images.py a.png b.png [diff.png]
Prints how many pixels differ and the largest channel difference; writes an amplified diff image when a
third path is given. Needs Pillow.
"""
import sys
from PIL import Image, ImageChops

a = Image.open(sys.argv[1]).convert("RGB")
b = Image.open(sys.argv[2]).convert("RGB")
if a.size != b.size:
    sys.exit("different sizes: %s vs %s" % (a.size, b.size))
diff = ImageChops.difference(a, b)
pixels = list(diff.get_flattened_data())
changed = sum(1 for p in pixels if max(p) > 2)
print("pixels: %d, differing (>2/255): %d (%.3f%%), max channel diff: %d" % (
    len(pixels), changed, 100.0 * changed / len(pixels), max(max(p) for p in pixels)))
if len(sys.argv) > 3:
    diff.point(lambda v: min(255, v * 10)).save(sys.argv[3])
sys.exit(1 if changed else 0)
