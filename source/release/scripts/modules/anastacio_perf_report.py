# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Performance Report: reads the trace of one game run (RANGE_TRACE folder: trace.jsonl and, when
present, shaders.txt / objects.txt) and writes report.html next to it.

Generic for any game. Usable without Blender: python anastacio_perf_report.py <folder>.
"""

import html
import json
import re
import os
import sys
from collections import defaultdict

# The first frames finish loading the start scene: they are "load", not gameplay.
LOAD_FRAMES = 5
# The start-up ends when the game has run this many frames in a row without a spike.
STABLE_FRAMES = 60
# A spike: above SPIKE_FACTOR x the median frame and above 1/30 s.
SPIKE_FACTOR = 2.0
SPIKE_MIN_MS = 1000.0 / 30.0
# Idle wait of the main loop (frame limiter / vsync); not counted as cost.
IDLE = ('Sleeping',)
MAX_ROWS = 40


# GPU budget per frame at 60 FPS; a step above a quarter of it on a weak GPU is worth a look.
GPU_BUDGET_MS = 1000.0 / 60.0
# Without the simulator, the weak GPU column assumes an old notebook (Intel HD 4400) next to a
# strong dedicated card: ~16x measured on an RX 6800M.
WEAK_GPU_DEFAULT = 16
GPU_STEP_NAMES = {
    'render.begin': 'Frame start (clear, sky)',
    'render.shadows': 'Shadows',
    'render.camera_setup': 'Camera setup',
    'render.sky': 'Sky (background, stars, moon)',
    'render.cameras': 'Objects and materials',
    'render.filters': '2D filters and effects',
    'render.present': 'Final copy to the screen',
}


# Old beige PC (CRT monitor + tower) for the weak PC simulator badge in the report header.
OLD_PC_SVG = (
    '<svg viewBox="0 0 58 46" aria-hidden="true">'
    '<rect x="1" y="2" width="36" height="30" rx="4" fill="#e9e2cf" stroke="#8a826d" stroke-width="1.5"/>'
    '<rect x="6" y="6" width="26" height="20" rx="3" fill="#1d3a2a"/>'
    '<path d="M9 11h12M9 15h17M9 19h8" stroke="#7dff9e" stroke-width="1.6" stroke-linecap="round"/>'
    '<rect x="17" y="21" width="4" height="2" fill="#7dff9e"><animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/></rect>'
    '<rect x="12" y="32" width="14" height="4" fill="#d6ceb8" stroke="#8a826d" stroke-width="1"/>'
    '<rect x="6" y="36" width="26" height="5" rx="1.5" fill="#e9e2cf" stroke="#8a826d" stroke-width="1.2"/>'
    '<rect x="41" y="8" width="15" height="33" rx="2" fill="#e9e2cf" stroke="#8a826d" stroke-width="1.5"/>'
    '<rect x="44" y="12" width="9" height="3" rx="1" fill="#bdb49c"/>'
    '<rect x="44" y="18" width="9" height="2" rx="1" fill="#bdb49c"/>'
    '<circle cx="48.5" cy="35" r="1.6" fill="#ffb347"/>'
    '</svg>')


# Small line icons for the section titles and the navigation bar (24x24, drawn in currentColor).
SECTION_ICONS = {
    'What to do': '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    'Compared with the previous run': '<path d="M4 7h13l-3-3M20 17H7l3 3"/>',
    'Frame time': '<path d="M3 17l5-6 4 4 4-7 5 5"/><path d="M3 21h18"/>',
    'Memory': '<rect x="4" y="7" width="16" height="10" rx="1.5"/><path d="M8 7V4M12 7V4M16 7V4M8 20v-3M12 20v-3M16 20v-3"/>',
    'Where the frame time goes (average)': '<path d="M12 3v9l6.5 6.5"/><circle cx="12" cy="12" r="9"/>',
    'GPU time by step': '<rect x="3" y="7" width="18" height="11" rx="1.5"/><circle cx="9" cy="12.5" r="2.5"/><circle cx="16" cy="12.5" r="2.5"/><path d="M6 18v3"/>',
    'Scripts': '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
    'Spikes': '<path d="M3 15h4l2-9 4 14 2-7h6"/>',
    'Loading during play': '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
    'Shaders and images prepared during play': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="16" cy="9" r="1.5"/>',
    'Scene loading': '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 12l9 4 9-4M3 17l9 4 9-4"/>',
    'Heaviest objects': '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    'Loaded but never drawn': '<path d="M3 3l18 18M10.6 6.1A10 10 0 0 1 12 6c5 0 9 6 9 6a17 17 0 0 1-3 3.5M6.5 7.6C4.3 9.2 3 12 3 12s4 6 9 6c1.5 0 2.9-.5 4.1-1.2"/>',
    'Sounds': '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
    'Work per frame': '<path d="M9 5h6M9 12h6M9 19h6"/><rect x="3" y="3" width="4" height="4" rx="1"/><rect x="3" y="10" width="4" height="4" rx="1"/><rect x="3" y="17" width="4" height="4" rx="1"/>',
}


def _section_icon(paths):
    return ('<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>' % paths)


def _(text):
    """Translated text when running inside the editor."""
    try:
        from bpy.app.translations import pgettext_iface
        return pgettext_iface(text)
    except Exception:
        return text


# ----------------------------------------------------------------------------- reading

def read_events(path):
    events = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # last line cut when the game is killed
    return events


def _median(values):
    v = sorted(values)
    return v[len(v) // 2] if v else 0.0


def _percentile(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0.0


def _cost(frame):
    return frame['ms'] - sum(frame['c'].get(k, 0.0) for k in IDLE)


def _top(categories, n=3):
    items = sorted(((k, v) for k, v in categories.items() if k not in IDLE), key=lambda x: x[1], reverse=True)
    return items[:n]


def _image_mb(ev):
    return ev['w'] * ev['h'] * 4 * (4 / 3 if ev.get('mipmap') else 1) / (1024 * 1024)


def analyze(events):
    session = next((e for e in events if e['ev'] == 'session'), {})
    frames = {e['f']: e for e in events if e['ev'] == 'frame'}
    ordered = [fr for f, fr in sorted(frames.items()) if f > LOAD_FRAMES]
    median = _median([_cost(fr) for fr in ordered])
    limit = max(SPIKE_FACTOR * median, SPIKE_MIN_MS)
    # Start-up: everything before the first STABLE_FRAMES frames in a row under the spike limit
    # (the start scene and its first loads); spikes there are loading, not gameplay.
    start = 0
    run = 0
    for i, fr in enumerate(ordered):
        run = run + 1 if _cost(fr) <= limit else 0
        if run >= STABLE_FRAMES:
            start = i - run + 1
            break
    load_end = ordered[start]['f'] - 1 if ordered else LOAD_FRAMES
    play = ordered[start:]
    costs = [_cost(fr) for fr in play]
    median = _median(costs)
    limit = max(SPIKE_FACTOR * median, SPIKE_MIN_MS)
    startup_s = play[0]['t'] if play else 0.0

    # What loaded at each frame, to explain spikes.
    loads = defaultdict(list)
    for e in events:
        if e['ev'] == 'scene_load':
            loads[e['f']].append('%s %s (%.0f ms)' % (_('scene'), e['scene'], e['ms']))
        elif e['ev'] == 'load_shaders':
            ms = e.get('textures_ms', 0) + e.get('shaders_ms', 0)
            if ms >= 1:
                loads[e['f']].append('%s %s (%.0f ms)' % (_('textures+shaders'), e['scene'], ms))
        elif e['ev'] == 'convert_object':
            loads[e['f']].append('%s %s (%.0f ms)' % (_('On Demand'), e['name'], e['ms']))
        elif e['ev'] == 'image' and e['ms'] >= 1:
            loads[e['f']].append('%s %s (%.0f ms)' % (_('image'), e['name'], e['ms']))

    script_frames = {e['f']: e['c'] for e in events if e['ev'] == 'scripts'}
    script_tot = defaultdict(lambda: [0.0, 0, 0.0, 0])  # ms, calls, worst frame ms, frames with it
    for f, c in script_frames.items():
        if f <= load_end:
            continue
        for name, (ms, calls) in c.items():
            t = script_tot[name]
            t[0] += ms
            t[1] += calls
            t[2] = max(t[2], ms)
            t[3] += 1
    nplay = max(len(play), 1)
    scripts = sorted(((n, v[0] / nplay, v[2], v[1], v[0]) for n, v in script_tot.items()), key=lambda r: r[1], reverse=True)

    spikes = []
    for fr in sorted(play, key=_cost, reverse=True):
        if _cost(fr) <= limit:
            break
        sc = script_frames.get(fr['f'], {})
        top_script = max(sc.items(), key=lambda x: x[1][0]) if sc else None
        spikes.append(dict(f=fr['f'], t=fr['t'], ms=_cost(fr), cats=_top(fr['c']),
                           script=(top_script[0], top_script[1][0]) if top_script and top_script[1][0] >= 1.0 else None,
                           loads=loads.get(fr['f'], []) + loads.get(fr['f'] - 1, []),
                           allcats=_top(fr['c'], 12), scripts=sorted(((n, v[0], v[1]) for n, v in sc.items()), key=lambda r: r[1], reverse=True)[:10]))

    # Average time per profiler category during play.
    cat_sum = defaultdict(float)
    for fr in play:
        for k, v in fr['c'].items():
            if k not in IDLE:
                cat_sum[k] += v
    categories = sorted(((k, v / len(play)) for k, v in cat_sum.items()), key=lambda x: x[1], reverse=True) if play else []

    # Loaded vs drawn.
    objects = [e for e in events if e['ev'] == 'object']
    meshes = {}
    materials = {}
    images = {}
    for e in events:
        if e['ev'] == 'mesh':
            # Mesh materials come with the ID prefix ("MAStone"; a bare "MA" is no material),
            # material events without it.
            e['materials'] = [m[2:] if m.startswith('MA') else m for m in e.get('materials', []) if m != 'MA']
            meshes.setdefault(e['name'], e)
        elif e['ev'] == 'material':
            materials.setdefault(e['name'], e)
        elif e['ev'] == 'image':
            images.setdefault(e['name'], e)
    seen = {'camera': set(), 'shadow': set()}
    for e in events:
        if e['ev'] == 'visible':
            seen[e['pass']].add(e['name'])
    has_usage = 'usage' in session.get('modules', []) and (seen['camera'] or seen['shadow'])

    def tris(o):
        return sum(meshes.get(m, {}).get('tris', 0) for m in o['meshes'])

    with_mesh = {}
    for o in objects:
        if o['meshes']:
            with_mesh.setdefault((o['scene'], o['name']), o)
    never = []
    shadow_only = []
    if has_usage:
        for o in with_mesh.values():
            if o['name'] in seen['camera'] or o.get('navmesh') or o.get('visible') is False:
                continue
            (shadow_only if o['name'] in seen['shadow'] else never).append(o)
    never.sort(key=tris, reverse=True)
    shadow_only.sort(key=tris, reverse=True)

    used = set()
    for o in with_mesh.values():
        if o['name'] in seen['camera'] or o['name'] in seen['shadow']:
            used.update(o['meshes'])
    unused_meshes = sorted((m for m in {m for o in never for m in o['meshes']} if m not in used),
                           key=lambda m: meshes.get(m, {}).get('tris', 0), reverse=True)
    used_mats = {mat for m in used for mat in meshes.get(m, {}).get('materials', [])}
    unused_mats = sorted({mat for m in unused_meshes for mat in meshes.get(m, {}).get('materials', [])} - used_mats)
    used_imgs = {i for mat in used_mats for i in materials.get(mat, {}).get('images', [])}
    unused_imgs = sorted(({i for mat in unused_mats for i in materials.get(mat, {}).get('images', [])} - used_imgs),
                         key=lambda i: _image_mb(images[i]) if i in images else 0, reverse=True)

    # Heaviest objects: triangles, materials and texture memory per object, and where it was drawn.
    heavy = []
    for o in with_mesh.values():
        mats = sorted({mat for m in o['meshes'] for mat in meshes.get(m, {}).get('materials', [])})
        imgs = {i for mat in mats for i in materials.get(mat, {}).get('images', []) if i in images}
        if not has_usage:
            drawn = None
        elif o['name'] in seen['camera']:
            drawn = 'camera'
        elif o['name'] in seen['shadow']:
            drawn = 'shadow'
        else:
            drawn = 'never'
        heavy.append(dict(name=o['name'], scene=o['scene'], tris=tris(o), mats=len(mats),
                          tex_mb=sum(_image_mb(images[i]) for i in imgs), drawn=drawn,
                          static_batch=o.get('static_batch', False)))
    heavy.sort(key=lambda h: (h['tris'], h['tex_mb']), reverse=True)

    # Loading during play (after the first frames): stalls the game.
    late = []
    for e in events:
        if e['f'] <= load_end:
            continue
        if e['ev'] == 'convert_object':
            late.append((_('On Demand object'), e['name'], e['ms'], e['f'], e['t']))
        elif e['ev'] == 'scene_load' and not e['scene'].startswith('..'):
            late.append((_('LibLoad') if e.get('libload') else _('Scene'), e['scene'], e['ms'], e['f'], e['t']))
    for e in images.values():
        if e['f'] > load_end:
            late.append((_('Image upload'), e['name'], e['ms'], e['f'], e['t']))
    late.sort(key=lambda x: x[2], reverse=True)

    work = [e for e in events if e['ev'] == 'work' and e['f'] > load_end]
    work_rows = []
    if work:
        for k in sorted({k for e in work for k in e if k not in ('t', 'f', 'ev')}):
            v = sorted(e.get(k, 0) for e in work)
            work_rows.append((k, _median(v), _percentile(v, 0.95), v[-1]))

    memory = [(e['t'], e['mb']) for e in events if e['ev'] == 'memory']
    sounds = defaultdict(lambda: [0, '', 0.0])
    for e in events:
        if e['ev'] == 'sound':
            snd = sounds[e['name']]
            snd[0] += 1
            snd[1] = e.get('from', '')
            snd[2] = snd[2] or e['t']
    marks = [(e['t'], e['ev'], e['scene']) for e in events if e['ev'] in ('scene_add', 'scene_remove')]
    marks += [(e['t'], 'sound', e['name']) for e in events if e['ev'] == 'sound']
    return dict(session=session, play=play, load_end=load_end, startup_s=startup_s, scripts=scripts,
                memory=memory, sounds=sorted(sounds.items(), key=lambda x: x[1][0], reverse=True), marks=marks,
                has_runtime='runtime' in session.get('modules', []),
                has_scripts='scripts' in session.get('modules', []), median=median, limit=limit, spikes=spikes, categories=categories,
                p95=_percentile(costs, 0.95), p99=_percentile(costs, 0.99), worst=max(costs) if costs else 0.0,
                scenes=[e for e in events if e['ev'] == 'scene_load'],
                scene_shaders={e['scene']: e for e in events if e['ev'] == 'load_shaders'},
                has_usage=has_usage, never=never, shadow_only=shadow_only, tris=tris,
                unused_meshes=unused_meshes, unused_mats=unused_mats, unused_imgs=unused_imgs, images=images,
                meshes=meshes, heavy=heavy, late=late, work=work_rows,
                duration=events[-1]['t'] if events else 0.0)


def read_gpu_profile(folder):
    """Average GPU ms per render step from the AVG lines of RANGE_PROFILE (KX_EngineProfiler)."""
    path = os.path.join(folder, 'profile.txt')
    if not os.path.isfile(path):
        return []
    sums, lines = {}, 0
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if not line.startswith('AVG ') or ' | gpu:' not in line:
                continue
            lines += 1
            part = line.split(' | gpu:', 1)[1].split(' | ', 1)[0]
            for item in part.split():
                name, _sep, value = item.partition('=')
                try:
                    sums[name] = sums.get(name, 0.0) + float(value)
                except ValueError:
                    pass
    if not lines:
        return []
    steps = [(name, total / lines) for name, total in sums.items()]
    # filter.* passes are already inside render.filters: list them under it, not as extra time.
    steps.sort(key=lambda s: (s[0].startswith('filter.'), -s[1]))
    return steps


def read_settings(folder):
    try:
        with open(os.path.join(folder, 'settings.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _gpu_section(steps, weak):
    factor = weak if weak > 1 else WEAK_GPU_DEFAULT
    total = sum(ms for name, ms in steps if not name.startswith('filter.')) or 1.0
    filters = [s for s in steps if s[0].startswith('filter.')]
    ordered = []
    for step in steps:
        if not step[0].startswith('filter.'):
            ordered.append(step)
            if step[0] == 'render.filters':
                ordered += filters
                filters = []
    rows = []
    for name, ms in ordered + filters:
        sub = name.startswith('filter.')
        est = ms * factor
        label = ('&nbsp;&nbsp;&nbsp;' + _esc(name[7:])) if sub else _esc(_(GPU_STEP_NAMES.get(name, name)))
        rows.append((Markup(label), _colored('%.2f' % ms, _level(ms, GPU_BUDGET_MS / 8, GPU_BUDGET_MS / 4)),
                     '-' if sub else '%.0f%%' % (ms / total * 100),
                     _colored('%.1f' % est, _level(est, GPU_BUDGET_MS / 4, GPU_BUDGET_MS / 2))))
    if weak > 1:
        note = _('Measured with the weak PC simulator on (GPU about %dx slower): FPS and frame times above are '
                 'those of the slower GPU; the ms here are this GPU, the last column the slower one.') % weak
    else:
        note = _('GPU time of each render step on this computer. The last column estimates a GPU %dx slower '
                 '(an old notebook): red steps would not fit 60 FPS there. Turn on Simulate Weak PC to feel it.') % factor
    head = (_('Step'), _('GPU ms'), '%', _('Weak GPU ms (x%d)') % factor)
    return '<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>' % (
        _esc(_('GPU time by step')), _table(head, rows, numeric=(1, 2, 3)), _esc(note))


def sky_advice(steps, settings, weak):
    """Tip naming the costly sky options when the sky alone is heavy on a weak GPU."""
    sky = dict(steps).get('render.sky', 0.0)
    flare = dict(steps).get('filter.lensflare', 0.0)
    factor = weak if weak > 1 else WEAK_GPU_DEFAULT
    world = settings.get('world', {})
    if (sky + flare) * factor < GPU_BUDGET_MS / 4:
        return None
    on = []
    if world.get('use_sky_stars'):
        on.append(_('realistic stars') if world.get('star_style') in ('REAL', 'REALISTIC', 'CONSTELLATIONS') else _('stars'))
    if world.get('use_sky_moon'):
        on.append(_('moon'))
    if world.get('use_lens_flare') or flare > 0.0:
        on.append(_('lens flare'))
    if world.get('sky_quality') == 'HIGH':
        on.append(_('High sky quality'))
    level = 'bad' if (sky + flare) * factor >= GPU_BUDGET_MS / 2 else 'warn'
    text = _('The sky costs %.2f ms on this GPU (sky %.2f + lens flare %.2f), about %.0f ms on a GPU %dx slower.') % (
        sky + flare, sky, flare, (sky + flare) * factor, factor)
    if on:
        text += ' ' + _('Turned on: %s. Turn them off for weak PCs or set Sky Quality to Low.') % ', '.join(on)
    else:
        text += ' ' + _('Set Sky Quality to Low for weak PCs.')
    return level, text


def read_shader_log(folder, load_end=LOAD_FRAMES):
    """shaders.txt (RANGE_SHADER_LOG): compilations and image uploads during play, slowest first."""
    path = os.path.join(folder, 'shaders.txt')
    if not os.path.isfile(path):
        return []
    items = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4 or not parts[0].startswith('t=') or not parts[2].startswith('ms='):
                continue
            try:
                frame = int(parts[1].split('=')[1])
                ms = float(parts[2][3:])
            except (ValueError, IndexError):
                continue
            kind = parts[3]
            if frame > load_end and kind != 'prefetch' and ms >= 1.0:
                name = ' '.join(parts[5:]) if kind == 'image' else parts[-1]
                items.append((kind, name or '-', ms, frame))
    items.sort(key=lambda x: x[2], reverse=True)
    return items


# ----------------------------------------------------------------------------- html

def _esc(v):
    return html.escape(str(v))


def _level(value, warn, bad):
    return 'bad' if value >= bad else 'warn' if value >= warn else 'good'


def _table(headers, rows, numeric=()):
    out = ['<div class="tscroll"><table><tr>']
    out += ['<th%s>%s</th>' % (' class="n"' if i in numeric else '', _esc(h)) for i, h in enumerate(headers)]
    out.append('</tr>')
    for r in rows[:MAX_ROWS]:
        out.append('<tr>' + ''.join('<td%s>%s</td>' % (' class="n"' if i in numeric else (' class="barcell"' if isinstance(c, Markup) and 'class="bar ' in c else ''),
                                                         c if isinstance(c, Markup) else _esc(c))
                                    for i, c in enumerate(r)) + '</tr>')
    out.append('</table></div>')
    if len(rows) > MAX_ROWS:
        out.append('<p class="note">%s</p>' % _esc(_('%d more not shown') % (len(rows) - MAX_ROWS)))
    return ''.join(out)


class Markup(str):
    pass


def _chart(a):
    """Frame time over the run (SVG), the 1/60 and 1/30 s lines and the spikes in red."""
    play = a['play']
    if not play:
        return ''
    w, h = 1000, 180
    # Scale by the usual frames: a multi-second spike would flatten everything (it is clipped at the top).
    top = max(40.0, a['p99'] * 1.5)
    t0, t1 = play[0]['t'], max(play[-1]['t'], play[0]['t'] + 0.001)

    def x(t):
        return (t - t0) / (t1 - t0) * w

    def y(ms):
        return h - min(ms, top) / top * h
    step = max(1, len(play) // 2000)
    pts = ' '.join('%.1f,%.1f' % (x(fr['t']), y(_cost(fr))) for fr in play[::step])
    lines = ''.join('<line x1="0" x2="%d" y1="%.1f" y2="%.1f" class="ref"/><text x="4" y="%.1f" class="lbl">%s</text>'
                    % (w, y(ms), y(ms), y(ms) - 3, label) for ms, label in ((1000 / 60, '60 FPS'), (1000 / 30, '30 FPS')))
    # Each spike is clickable (a wider invisible circle makes it easy to hit) and opens its frame below the chart.
    dots = ''.join('<g class="spk" onclick="showFrame(%d)"><circle cx="%.1f" cy="%.1f" r="9" class="hit"/>'
                   '<circle cx="%.1f" cy="%.1f" r="3.5" class="spike"/><title>%.1f ms @ %.1f s</title></g>'
                   % (i, x(s['t']), y(s['ms']), x(s['t']), y(s['ms']), s['ms'], s['t']) for i, s in enumerate(a['spikes'][:200]))
    labels = {'scene_add': _('scene added'), 'scene_remove': _('scene removed'), 'sound': _('sound')}
    for t, kind, name in a.get('marks', [])[:400]:
        if t0 <= t <= t1:
            cls = 'msnd' if kind == 'sound' else 'mscn'
            dots += ('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" class="%s"><title>%s: %s @ %.1f s</title></line>'
                     % (x(t), x(t), h - (8 if kind == 'sound' else 0), h if kind == 'sound' else 0, cls,
                        _esc(labels[kind]), _esc(name), t))
    first = pts.split(' ', 1)[0].split(',')[0]
    last = pts.rsplit(' ', 1)[-1].split(',')[0]
    area = '<polygon points="%s,%d %s %s,%d" class="area"/>' % (first, h, pts, last, h)
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="chart">%s%s<polyline points="%s" class="line"/>%s</svg>'
            % (w, h, lines, area, pts, dots))


def _frame_details(a):
    """Hidden detail of each spike frame, shown by clicking its dot in the chart."""
    out = ['<div id="framebox" class="framebox" hidden></div>']
    for i, s in enumerate(a['spikes'][:200]):
        top = s['allcats'][0][1] if s['allcats'] else 1.0
        cats = _table((_('Part'), '', 'ms'), [(k, Markup('<div class="bar %s" style="width:%.0f%%"></div>' % (_level(v, 5.0, 15.0), v / (top or 1) * 100)),
                                               _colored('%.1f' % v, _level(v, 5.0, 15.0))) for k, v in s['allcats']], numeric=(2,))
        scripts = (_table((_('Script'), 'ms', _('Calls')), [(n, '%.1f' % ms, c) for n, ms, c in s['scripts']], numeric=(1, 2))
                   if s['scripts'] else '<p class="mut">%s</p>' % _esc(_('No script took noticeable time.')))
        loads = ('<ul class="loads">%s</ul>' % ''.join('<li>%s</li>' % _esc(l) for l in s['loads'])
                 if s['loads'] else '<p class="mut">%s</p>' % _esc(_('Nothing loaded in this frame.')))
        out.append('<template id="frame%d"><div class="fhead"><b>%s</b><button class="fclose" onclick="showFrame(-1)">&times;</button></div>'
                   '<div class="fgrid"><div><h3>%s</h3>%s</div><div><h3>%s</h3>%s<h3>%s</h3>%s</div></div></template>'
                   % (i, _esc(_('Frame %d at %.1f s: %.0f ms') % (s['f'], s['t'], s['ms'])),
                      _esc(_('Slowest parts')), cats, _esc(_('Scripts')), scripts, _esc(_('Loading at that moment')), loads))
    return ''.join(out)


# Advice per profiler category: what usually makes it heavy.
CATEGORY_ADVICE = {
    'Physics': 'Fewer dynamic bodies, simpler collision shapes (box/sphere/convex hull instead of triangle mesh), or a lower physics step rate.',
    'Components': 'Python components: avoid work every frame (use timers or run every N frames).',
    'Logic': 'Logic bricks and Python controllers: reduce Always sensors in pulse mode and scripts that run every frame.',
    'Actuators': 'Many actuators firing every frame (motion, property, message): fire them only when something changes.',
    'MainRender': 'Rendering: fewer draw calls (Static Batch for objects that do not move), fewer materials, lower geometry far away.',
    'Shadows': 'Shadows: fewer lamps with shadows, smaller shadow maps, Shadow Culling, or fewer cascades on the Sun.',
    'Skinning': 'Skinned characters: GPU Skinning, fewer bones, lower polygon meshes for characters far away.',
    'Animations': 'Animations: fewer armatures playing at once, or Half Animations for characters far away.',
    'Filters2D': '2D filters run on every pixel: fewer filters or a lower Dynamic Resolution.',
    'GPU Latency': 'The CPU waits for the graphics card: the GPU is the limit (resolution, anti-aliasing, effects, shadows).',
    'ParticleUpdate': 'Particles: fewer emitters or fewer particles per emitter.',
    'Overhead': 'Engine housekeeping, usually loading: see Loading during play.',
}


def _colored(text, level):
    """A value colored by how bad it is (good / warn / bad)."""
    return Markup('<span class="v%s">%s</span>' % (level, _esc(text)))


def _ms_level(ms):
    return _level(ms, 1000.0 / 60.0, 1000.0 / 30.0)


def advice(a, shader_items):
    """Plain recommendations, most important first: (level, text)."""
    out = []
    frame_budget = 1000.0 / 60.0
    if a['median'] > frame_budget and a['categories']:
        total = sum(v for _k, v in a['categories']) or 1.0
        for name, ms in a['categories'][:3]:
            share = ms / total
            if share >= 0.2 and name in CATEGORY_ADVICE:
                out.append(('bad' if share >= 0.35 else 'warn',
                            _('%s takes %d%% of the frame (%.1f ms).') % (name, share * 100, ms) + ' ' + _(CATEGORY_ADVICE[name])))
    for name, avg, worst, _calls, _total in a['scripts'][:3]:
        if avg >= 1.0:
            out.append(('bad' if avg >= 3.0 else 'warn',
                        _('Script "%s" takes %.1f ms per frame on average (worst frame %.0f ms). '
                          'Avoid work every frame: cache lookups, run it every few frames or only when something changes.')
                        % (name, avg, worst)))
    script_spikes = [sp for sp in a['spikes'] if sp.get('script')]
    if script_spikes:
        sp = script_spikes[0]
        out.append(('warn', _('Script "%s" took %.0f ms in one frame at %.1f s (a spike). Look for a loop or a load in it.')
                    % (sp['script'][0], sp['script'][1], sp['t'])))
    if a['late']:
        kind, name, ms, _f, t = a['late'][0]
        out.append(('bad' if ms >= 50 else 'warn',
                    _('%d things loaded during play; the slowest is %s "%s" (%.0f ms at %.1f s). '
                      'Preload them (Load Mode, Preload) or load them behind a loading screen.') % (len(a['late']), kind, name, ms, t)))
    if shader_items:
        out.append(('warn', _('%d shaders or images were prepared during play (slowest %.0f ms). '
                              'Cook the game (Cook button) so compiled shaders are kept.') % (len(shader_items), shader_items[0][2])))
    quiet = [sp for sp in a['spikes'] if not sp['loads'] and not sp.get('script')]
    if quiet:
        top = quiet[0]
        part = top['cats'][0][0] if top['cats'] else '?'
        out.append(('warn', _('%d spikes without any loading; the worst (%.0f ms at %.1f s) is mostly %s. '
                              'Check scripts or effects that start at that moment.') % (len(quiet), top['ms'], top['t'], part)))
    if a['has_usage'] and a['never']:
        tris = sum(a['tris'](o) for o in a['never'])
        if tris >= 10000 or len(a['never']) >= 20:
            out.append(('warn', _('%d objects (%d triangles) were loaded but never seen by the camera. '
                                  'If they are not needed, remove them or set Load Mode to On Demand.') % (len(a['never']), tris)))
    grow, base = memory_growth(a)
    if base and grow > max(100.0, base * 0.3):
        out.append(('warn', _('Memory grew %.0f MB during play (from %.0f MB). If it keeps growing in longer runs, '
                              'something is created and never freed (objects added without being ended, sounds, images).')
                    % (grow, base)))
    if not out:
        out.append(('good', _('Nothing to fix in this run: the frame time is even and nothing loads during play.')))
    order = {'bad': 0, 'warn': 1, 'good': 2}
    out.sort(key=lambda x: order[x[0]])
    return out


def _heavy_hint(h):
    """What to reduce on one object, most useful first."""
    out = []
    if h['drawn'] == 'never':
        out.append(_('never drawn: remove it or use On Demand'))
    elif h['drawn'] == 'shadow':
        out.append(_('only in shadows: a simpler mesh can cast them'))
    if h['tris'] >= 20000:
        out.append(_('many triangles: Decimate or a lighter version'))
    if h['tex_mb'] >= 32:
        out.append(_('large textures: reduce their size'))
    if h['mats'] >= 4 and not h['static_batch']:
        out.append(_('many materials: each one is drawn apart, merge them or use Static Batch'))
    return '; '.join(out)


def summary(a, shader_items):
    return dict(median=a['median'], p95=a['p95'], worst=a['worst'], spikes=len(a['spikes']), late=len(a['late']),
                shaders=len(shader_items), never=len(a['never']), duration=a['duration'],
                categories=dict(a['categories'][:10]))


def previous_summary(folder):
    """summary.json of the last earlier report of the same game (folders <game>-<date>-<time>)."""
    parent, name = os.path.split(os.path.normpath(folder))
    game = name.rsplit('-', 2)[0]
    try:
        older = sorted(n for n in os.listdir(parent) if n.rsplit('-', 2)[0] == game and n < name)
    except OSError:
        return None
    for n in reversed(older):
        path = os.path.join(parent, n, 'summary.json')
        if os.path.isfile(path):
            try:
                with open(path, encoding='utf-8') as f:
                    return n, json.load(f)
            except (OSError, ValueError):
                pass
    return None


def _compare(prev, now):
    name, old = prev
    rows = []
    for key, label, fmt in (('median', _('Median frame'), '%.1f ms'), ('p95', _('95% of frames under'), '%.1f ms'),
                            ('worst', _('Worst frame'), '%.0f ms'), ('spikes', _('Spikes'), '%d'),
                            ('late', _('Loads during play'), '%d'), ('shaders', _('Shaders prepared during play'), '%d'),
                            ('never', _('Objects never drawn'), '%d')):
        if key not in old:
            continue
        a, b = old[key], now[key]
        if abs(b - a) < (0.5 if isinstance(b, float) else 1):
            tag = _colored(_('same'), 'mut')
        else:
            tag = _colored(_('better') if b < a else _('worse'), 'good' if b < a else 'bad')
        rows.append((label, fmt % a, fmt % b, tag))
    return name, rows


def _memory_chart(a):
    mem = a['memory']
    if len(mem) < 2:
        return ''
    w, h = 1000, 90
    t0, t1 = mem[0][0], max(mem[-1][0], mem[0][0] + 0.001)
    lo = min(mb for _t, mb in mem)
    hi = max(mb for _t, mb in mem)
    span = max(hi - lo, 1.0)
    pts = ' '.join('%.1f,%.1f' % ((t - t0) / (t1 - t0) * w, h - 4 - (mb - lo) / span * (h - 8)) for t, mb in mem)
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="chart mem"><polyline points="%s" class="memline"/></svg>'
            '<p class="note">%s</p>' % (w, h, pts, _esc(_('Process memory: %.0f MB at the start, %.0f MB at the peak, %.0f MB at the end.')
                                                         % (mem[0][1], hi, mem[-1][1]))))


# Per frame counters: (worth a look, fix first). Unknown counters stay neutral.
WORK_LIMITS = {
    'draws': (800, 2000), 'matBinds': (300, 800), 'lightBinds': (200, 600), 'passUniforms': (3000, 10000),
    'syncs': (60, 200), 'bounds': (200, 1000), 'matrices': (500, 2000), 'nodes': (500, 2000),
    'instancing': (500, 2000), 'notifies': (100, 500),
}


def _work_level(name, value):
    limits = WORK_LIMITS.get(name)
    return _level(value, *limits) if limits else 'mut'


def memory_growth(a):
    """MB gained from the end of start-up to the end of the run (a steady climb may be a leak)."""
    mem = [mb for t, mb in a['memory'] if t >= a['startup_s']]
    return (mem[-1] - mem[0], mem[0]) if len(mem) >= 10 else (0.0, 0.0)


THEME_JS = """
(function(){try{var t=localStorage.getItem('perfTheme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})();
function toggleTheme(){var r=document.documentElement,cur=r.getAttribute('data-theme');
if(!cur){cur=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}
var next=cur==='dark'?'light':'dark';r.setAttribute('data-theme',next);try{localStorage.setItem('perfTheme',next);}catch(e){}}
function showFrame(i){var b=document.getElementById('framebox'),t=document.getElementById('frame'+i);if(!b)return;
if(!t){b.hidden=true;b.innerHTML='';return;}b.innerHTML=t.innerHTML;b.hidden=false;b.scrollIntoView({block:'nearest'});}
"""


CSS = """
:root{--bg:#f4f6fa;--card:#ffffff;--card2:#f7f8fb;--fg:#162033;--mut:#5d6b82;--line:#e2e7ef;
--good:#17924a;--warn:#c27a00;--bad:#d7263d;--acc:#3466e0;--acc2:#7c4dff;--shadow:0 1px 2px rgba(16,24,40,.06),0 4px 14px rgba(16,24,40,.06);
--goodbg:rgba(23,146,74,.10);--warnbg:rgba(194,122,0,.12);--badbg:rgba(215,38,61,.10)}
:root[data-theme="dark"]{--bg:#0f1218;--card:#181c24;--card2:#1e232d;--fg:#e8ebf1;--mut:#94a0b4;--line:#2a313d;
--good:#4cd07d;--warn:#ffb547;--bad:#ff6b7d;--acc:#7aa2ff;--acc2:#b39dff;--shadow:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.25);
--goodbg:rgba(76,208,125,.12);--warnbg:rgba(255,181,71,.12);--badbg:rgba(255,107,125,.12)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1218;--card:#181c24;--card2:#1e232d;--fg:#e8ebf1;--mut:#94a0b4;--line:#2a313d;
--good:#4cd07d;--warn:#ffb547;--bad:#ff6b7d;--acc:#7aa2ff;--acc2:#b39dff;--shadow:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.25);
--goodbg:rgba(76,208,125,.12);--warnbg:rgba(255,181,71,.12);--badbg:rgba(255,107,125,.12)}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif}
main{max-width:1120px;margin:0 auto;padding:0 16px 64px}
.hero{background:linear-gradient(120deg,var(--acc),var(--acc2));color:#fff;border-radius:0 0 18px 18px;padding:26px 24px 22px;margin:0 -16px 0;box-shadow:var(--shadow);position:relative}
.hero h1{font-size:24px;margin:0;letter-spacing:.2px}.hero .sub{opacity:.9;margin-top:4px;font-size:13px}
.verdict{display:inline-flex;align-items:center;gap:8px;margin-top:14px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.18);font-weight:600}
.verdict i{width:10px;height:10px;border-radius:50%;display:inline-block}
.weakpc{display:flex;align-items:center;gap:12px;margin-top:12px;padding:8px 14px 8px 10px;border-radius:14px;background:rgba(0,0,0,.16);width:max-content;max-width:100%}
.weakpc svg{width:58px;height:46px;flex:none}.weakpc span{display:flex;flex-direction:column;font-size:13px;line-height:1.35}
.weakpc b{font-size:14px}
.verdict.good i{background:#5cf09a}.verdict.warn i{background:#ffd27a}.verdict.bad i{background:#ff9aa8}
.theme{position:absolute;top:18px;right:18px;border:0;border-radius:999px;padding:7px 12px;background:rgba(255,255,255,.2);color:#fff;cursor:pointer;font:inherit}
.theme:hover{background:rgba(255,255,255,.3)}
nav{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 0;margin-top:14px;display:flex;flex-wrap:wrap;gap:6px;border-bottom:1px solid var(--line)}
nav a{color:var(--mut);text-decoration:none;font-size:12px;padding:4px 10px;border-radius:999px;background:var(--card);border:1px solid var(--line)}
nav a:hover{color:var(--fg);border-color:var(--acc)}
h2{font-size:16px;margin:30px 0 10px;scroll-margin-top:60px;display:flex;align-items:center;gap:8px}
h2 .ic{width:20px;height:20px;color:var(--acc);flex:none}
nav a{display:inline-flex;align-items:center;gap:5px}nav a .ic{width:13px;height:13px;flex:none}
.mut,.note{color:var(--mut)}.note{font-size:12px;margin:8px 0 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-top:18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;box-shadow:var(--shadow);border-top:4px solid var(--line)}
.kpi b{display:block;font-size:24px;line-height:1.2}.kpi span{color:var(--mut);font-size:12px}
.kpi.good{border-top-color:var(--good)}.kpi.good b{color:var(--good)}
.kpi.warn{border-top-color:var(--warn)}.kpi.warn b{color:var(--warn)}
.kpi.bad{border-top-color:var(--bad)}.kpi.bad b{color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;overflow-x:auto;box-shadow:var(--shadow)}
.tscroll{max-height:460px;overflow:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}tbody tr:hover td,tr:hover td{background:var(--card2)}
th{position:sticky;top:0;background:var(--card);z-index:1;color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
td:first-child{white-space:nowrap}td.barcell{width:55%}.n{text-align:right;font-variant-numeric:tabular-nums}
.chart{width:100%;height:190px;display:block}.line{fill:none;stroke:var(--acc);stroke-width:1.2}.area{fill:var(--acc);opacity:.10}
.ref{stroke:var(--mut);stroke-dasharray:4 4;stroke-width:.6}.lbl{fill:var(--mut);font-size:10px}.spike{fill:var(--bad);stroke:var(--card);stroke-width:1}
.spk{cursor:pointer}.hit{fill:transparent}.spk:hover .spike{r:5}
.framebox{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}.fhead{display:flex;justify-content:space-between;align-items:center}
.fclose{border:0;background:var(--card2);color:var(--fg);border-radius:999px;width:28px;height:28px;cursor:pointer;font-size:16px}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.framebox h3{font-size:13px;margin:10px 0 4px;color:var(--mut)}
.loads{margin:0;padding-left:18px}
.mscn{stroke:var(--warn);stroke-width:1.5;stroke-dasharray:3 3}.msnd{stroke:var(--good);stroke-width:2}
.chart.mem{height:90px}.memline{fill:none;stroke:var(--warn);stroke-width:1.6}
.bar{height:10px;background:var(--acc);border-radius:6px;min-width:3px}
.bar.warn{background:var(--warn)}.bar.bad{background:var(--bad)}.bar.good{background:var(--good)}
.ok,.vgood{color:var(--good)}.vwarn{color:var(--warn);font-weight:600}.vbad{color:var(--bad);font-weight:700}.vmut{color:var(--mut)}
.adv{list-style:none;padding:0;margin:0}
.adv li{padding:10px 12px;border-left:4px solid var(--line);margin:8px 0;border-radius:8px;background:var(--card2)}
.adv li:first-child{margin-top:0}.adv li:last-child{margin-bottom:0}
.adv li.good{border-left-color:var(--good);background:var(--goodbg)}.adv li.warn{border-left-color:var(--warn);background:var(--warnbg)}
.adv li.bad{border-left-color:var(--bad);background:var(--badbg)}
.legend{font-size:12px;color:var(--mut);margin-top:10px;display:flex;gap:14px}
.legend b{font-weight:600}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:middle;background:var(--mut)}
.dot.good{background:var(--good)}.dot.warn{background:var(--warn)}.dot.bad{background:var(--bad)}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;background:var(--card2);border:1px solid var(--line)}
.chip.speaker{color:var(--acc);border-color:var(--acc)}.chip.actuator{color:var(--acc2);border-color:var(--acc2)}
.chip.world{color:var(--good);border-color:var(--good)}
footer{margin-top:36px;color:var(--mut);font-size:12px;word-break:break-all}
"""


def write_html(folder, title=None):
    events = read_events(os.path.join(folder, 'trace.jsonl'))
    a = analyze(events)
    shader_items = read_shader_log(folder, a['load_end'])
    game = title or a['session'].get('file') or os.path.basename(folder)
    fps = 1000.0 / a['median'] if a['median'] > 0 else 0.0
    settings = read_settings(folder)
    weak = int(settings.get('weak_gpu', 1))

    w = []
    w.append('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    w.append('<title>%s</title><style>%s</style><script>%s</script></head><body><main>' % (_esc(_('Performance Report')), CSS, THEME_JS))
    tips = advice(a, shader_items)
    sky_tip = sky_advice(read_gpu_profile(folder), settings, weak)
    if sky_tip:
        tips.insert(0, sky_tip)
        tips.sort(key=lambda t: {'bad': 0, 'warn': 1}.get(t[0], 2))
    worst_level = tips[0][0] if tips else 'good'
    verdict = {'good': _('Runs smoothly'), 'warn': _('Some things worth a look'), 'bad': _('Needs work')}[worst_level]
    w.append('<header class="hero"><button class="theme" onclick="toggleTheme()" title="%s">&#9680;</button>'
             '<h1>%s</h1><div class="sub">%s &middot; %.1f s &middot; %d %s &middot; %s</div>'
             '<div class="verdict %s"><i></i>%s</div>%s</header><!--NAV-->'
             % (_esc(_('Light / dark theme')), _esc(_('Performance Report')), _esc(os.path.basename(game)), a['duration'],
                len(a['play']), _esc(_('frames')), _esc(_('start-up (not counted): %.1f s') % a['startup_s']),
                worst_level, _esc(verdict),
                ('<div class="weakpc">%s<span><b>%s</b>%s</span></div>'
                 % (OLD_PC_SVG, _esc(_('Weak PC simulator')), _esc(_('GPU about %dx slower') % weak))) if weak > 1 else ''))

    kpis = [
        (_('Typical FPS'), '%.0f' % fps, _level(a['median'], 1000 / 55, 1000 / 30)),
        (_('Median frame'), '%.1f ms' % a['median'], _level(a['median'], 1000 / 55, 1000 / 30)),
        (_('95% of frames under'), '%.1f ms' % a['p95'], _level(a['p95'], 1000 / 45, 1000 / 25)),
        (_('Worst frame'), '%.0f ms' % a['worst'], _level(a['worst'], 50, 100)),
        (_('Spikes'), '%d' % len(a['spikes']), _level(len(a['spikes']), 1, 10)),
        (_('Loads during play'), '%d' % len(a['late']), _level(len(a['late']), 1, 5)),
        (_('Objects never drawn'), '%d' % len(a['never']) if a['has_usage'] else '-', _level(len(a['never']), 1, 1000)),
    ]
    w.append('<div class="kpis">' + ''.join('<div class="kpi %s"><b>%s</b><span>%s</span></div>' % (lvl, _esc(v), _esc(k))
                                             for k, v, lvl in kpis) + '</div>')

    w.append('<div class="legend"><b class="vgood">&#9632; %s</b> &nbsp; <b class="vwarn">&#9632; %s</b> &nbsp; <b class="vbad">&#9632; %s</b></div>'
             % (_esc(_('good')), _esc(_('worth a look')), _esc(_('fix first'))))
    w.append('<h2>%s</h2><div class="card"><ul class="adv">%s</ul></div>'
             % (_esc(_('What to do')), ''.join('<li class="%s">%s</li>' % (lvl, _esc(t)) for lvl, t in tips)))

    now = summary(a, shader_items)
    prev = previous_summary(folder)
    if prev:
        name, rows = _compare(prev, now)
        w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
                 % (_esc(_('Compared with the previous run')), _table((_('Measure'), _('Before'), _('Now'), ''), rows, numeric=(1, 2)),
                    _esc(_('Previous report: %s. Runs differ in what you played, so compare similar sessions.') % name)))

    w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
             % (_esc(_('Frame time')), _chart(a) + _frame_details(a),
                _esc(_('Lower is better. Red dots are spikes: frames much slower than the rest. '
                       'Orange dashed lines: scenes added or removed; green ticks at the bottom: sounds (hover for details). '
                       'Click a red dot to see that frame.'))))
    if a['has_runtime'] and a['memory']:
        w.append('<h2>%s</h2><div class="card">%s</div>' % (_esc(_('Memory')), _memory_chart(a)))

    if a['categories']:
        total = sum(v for _k, v in a['categories']) or 1.0
        rows = [(k, Markup('<div class="bar %s" style="width:%.0f%%"></div>'
                           % (_level(v, 2.0, 5.0), v / a['categories'][0][1] * 100)),
                 _colored('%.2f' % v, _level(v, 2.0, 5.0))) for k, v in a['categories'][:15]]
        w.append('<h2>%s</h2><div class="card">%s</div>' % (_esc(_('Where the frame time goes (average)')),
                                                            _table((_('Part'), '', 'ms'), rows, numeric=(2,))))

    gpu_steps = read_gpu_profile(folder)
    if gpu_steps:
        w.append(_gpu_section(gpu_steps, int(settings.get('weak_gpu', 1))))

    if a['has_scripts']:
        w.append('<h2>%s</h2><div class="card">' % _esc(_('Scripts')))
        if a['scripts']:
            rows = [(n, _colored('%.2f' % avg, _level(avg, 1.0, 3.0)), _colored('%.1f' % worst, _level(worst, 5.0, 16.0)),
                     calls, '%.0f' % total) for n, avg, worst, calls, total in a['scripts']]
            w.append(_table((_('Script'), _('ms per frame'), _('Worst frame ms'), _('Calls'), _('Total ms')), rows,
                            numeric=(1, 2, 3, 4)))
            w.append('<p class="note">%s</p>' % _esc(_('Python components (by class) and Python controllers (by script or module). '
                                                      'Calls under 0.02 ms in a frame are not counted.')))
        else:
            w.append('<p class="ok">%s</p>' % _esc(_('No script took noticeable time.')))
        w.append('</div>')

    w.append('<h2>%s</h2><div class="card">' % _esc(_('Spikes')))
    if a['spikes']:
        rows = [('%.1f s' % s['t'], s['f'], _colored('%.0f' % s['ms'], _level(s['ms'], 50, 100)), ', '.join('%s %.0f' % c for c in s['cats']),
                 ('%s %.0f ms' % s['script']) if s.get('script') else '-', '; '.join(s['loads']) or '-') for s in a['spikes']]
        w.append(_table((_('Time'), _('Frame'), 'ms', _('Slowest parts'), _('Heaviest script'), _('Loading at that moment')),
                        rows, numeric=(1, 2)))
    else:
        w.append('<p class="ok">%s</p>' % _esc(_('No spikes: the frame time stays even.')))
    w.append('</div>')

    w.append('<h2>%s</h2><div class="card">' % _esc(_('Loading during play')))
    if a['late']:
        w.append(_table((_('What'), _('Name'), 'ms', _('Frame'), _('Time')),
                        [(k, n, _colored('%.0f' % ms, _level(ms, 10, 50)), f, '%.1f s' % t) for k, n, ms, f, t in a['late']], numeric=(2, 3)))
        w.append('<p class="note">%s</p>' % _esc(_('Each of these stalls the game while it loads. Preload them or load them behind a loading screen.')))
    else:
        w.append('<p class="ok">%s</p>' % _esc(_('Nothing loaded during play.')))
    w.append('</div>')

    if shader_items:
        w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
                 % (_esc(_('Shaders and images prepared during play')),
                    _table((_('Kind'), _('Name'), 'ms', _('Frame')), [(k, n, _colored('%.1f' % ms, _level(ms, 10, 50)), f) for k, n, ms, f in shader_items],
                           numeric=(2, 3)),
                    _esc(_('First use of a material or image after the start. Cooking the game (Cook button) keeps compiled shaders.'))))

    if a['scenes']:
        rows = []
        for e in a['scenes']:
            sh = a['scene_shaders'].get(e['scene'], {})
            tex, shd = sh.get('textures_ms', 0), sh.get('shaders_ms', 0)
            total = e['ms'] + tex + shd
            late = e['f'] > a['load_end']
            rows.append((Markup('<span class="dot %s"></span>%s' % (_level(total, 50, 200), _esc(e['scene']))),
                         _colored('%.0f' % e['ms'], _level(e['ms'], 50, 200)), _colored('%.0f' % tex, _level(tex, 50, 200)),
                         _colored('%.0f' % shd, _level(shd, 50, 200)), e.get('objects', '-'),
                         _colored('%.1f s' % e['t'], 'warn' if late else 'mut')))
        w.append('<h2>%s</h2><div class="card">%s</div>'
                 % (_esc(_('Scene loading')), _table((_('Scene'), _('Convert ms'), _('Textures ms'), _('Shaders ms'),
                                                      _('Objects'), _('At')), rows, numeric=(1, 2, 3, 4))))

    if a['heavy']:
        drawn = {'camera': ('good', _('camera')), 'shadow': ('warn', _('shadow only')), 'never': ('bad', _('never'))}
        rows = []
        for h in a['heavy']:
            lv, label = drawn.get(h['drawn'], ('mut', '-'))
            rows.append((h['name'], _colored(h['scene'], 'mut'), _colored(h['tris'], _level(h['tris'], 5000, 20000)),
                         _colored(h['mats'], _level(h['mats'], 4, 8)),
                         _colored('%.1f' % h['tex_mb'], _level(h['tex_mb'], 16, 64)), _colored(label, lv),
                         _colored(_heavy_hint(h), 'mut')))
        w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
                 % (_esc(_('Heaviest objects')),
                    _table((_('Object'), _('Scene'), _('Triangles'), _('Materials'), _('Textures MB'), _('Drawn'), _('What to reduce')),
                           rows, numeric=(2, 3, 4)),
                    _esc(_('Sorted by triangles. Texture memory counts each image the object uses, even when shared with others.'))))

    if a['has_usage']:
        w.append('<h2>%s</h2><div class="card">' % _esc(_('Loaded but never drawn')))
        if a['never']:
            w.append(_table((_('Object'), _('Scene'), _('Triangles')),
                            [(o['name'], _colored(o['scene'], 'mut'), _colored(a['tris'](o), _level(a['tris'](o), 1000, 5000)))
                             for o in a['never']], numeric=(2,)))
            if a['unused_imgs']:
                w.append('<p>%s %s</p>' % (_esc(_('Images only used by them:')), _esc(', '.join(a['unused_imgs'][:20]))))
            w.append('<p class="note">%s</p>' % _esc(_('Never seen by the camera in this run. If they are never needed, '
                                                      'remove them or set their Load Mode to On Demand.')))
        else:
            w.append('<p class="ok">%s</p>' % _esc(_('Everything loaded was drawn.')))
        if a['shadow_only']:
            w.append('<p class="note">%s %s</p>' % (_esc(_('Only drawn in shadows:')),
                                                    _esc(', '.join(o['name'] for o in a['shadow_only'][:30]))))
        w.append('</div>')

    if a['has_runtime']:
        w.append('<h2>%s</h2><div class="card">' % _esc(_('Sounds')))
        if a['sounds']:
            w.append(_table((_('Sound'), _('From'), _('Times played'), _('First at')),
                            [(n, Markup('<span class="chip %s">%s</span>' % (_esc(v[1]), _esc(v[1]))),
                              _colored(v[0], _level(v[0], 50, 500)), _colored('%.1f s' % v[2], 'mut')) for n, v in a['sounds']],
                            numeric=(2,)))
            w.append('<p class="note">%s</p>' % _esc(_('Sounds started by the Sound actuator, speakers and World Sound. '
                                                      'Sounds played directly with the aud module are not listed.')))
        else:
            w.append('<p class="mut">%s</p>' % _esc(_('No sound was started by the engine in this run.')))
        w.append('</div>')

    if a['work']:
        w.append('<h2>%s</h2><div class="card">%s</div>'
                 % (_esc(_('Work per frame')), _table((_('Counter'), _('Typical'), '95%', _('Max')),
                                                      [(Markup('<span class="dot %s"></span>%s' % (_work_level(k, p), _esc(k))),
                                                        _colored('%g' % m, _work_level(k, m)), _colored('%g' % p, _work_level(k, p)),
                                                        _colored('%g' % mx, _work_level(k, mx))) for k, m, p, mx in a['work']],
                                                      numeric=(1, 2, 3))))

    w.append('<footer>%s %s</footer></main></body></html>' % (_esc(_('Raw data:')), _esc(os.path.join(folder, 'trace.jsonl'))))
    page = ''.join(w)
    # Anchors on the section titles and the navigation bar under the header.
    links = []

    icons = {_esc(_(title)): _section_icon(paths) for title, paths in SECTION_ICONS.items()}

    def anchor(m):
        links.append(m.group(1))
        return '<h2 id="s%d">%s%s</h2>' % (len(links), icons.get(m.group(1), ''), m.group(1))
    page = re.sub(r'<h2>(.*?)</h2>', anchor, page)
    nav = '<nav>' + ''.join('<a href="#s%d">%s%s</a>' % (i + 1, icons.get(t, ''), t) for i, t in enumerate(links)) + '</nav>'
    page = page.replace('<!--NAV-->', nav, 1)
    w = [page]
    with open(os.path.join(folder, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(now, f)
    out = os.path.join(folder, 'report.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(w))
    return out


if __name__ == '__main__':
    print(write_html(sys.argv[1]))
