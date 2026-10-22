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
                           loads=loads.get(fr['f'], []) + loads.get(fr['f'] - 1, [])))

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
                meshes=meshes, late=late, work=work_rows,
                duration=events[-1]['t'] if events else 0.0)


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
    out = ['<table><tr>']
    out += ['<th%s>%s</th>' % (' class="n"' if i in numeric else '', _esc(h)) for i, h in enumerate(headers)]
    out.append('</tr>')
    for r in rows[:MAX_ROWS]:
        out.append('<tr>' + ''.join('<td%s>%s</td>' % (' class="n"' if i in numeric else (' class="barcell"' if isinstance(c, Markup) and 'class="bar' in c else ''),
                                                         c if isinstance(c, Markup) else _esc(c))
                                    for i, c in enumerate(r)) + '</tr>')
    out.append('</table>')
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
    dots = ''.join('<circle cx="%.1f" cy="%.1f" r="3.5" class="spike"><title>%.1f ms @ %.1f s</title></circle>'
                   % (x(s['t']), y(s['ms']), s['ms'], s['t']) for s in a['spikes'][:200])
    labels = {'scene_add': _('scene added'), 'scene_remove': _('scene removed'), 'sound': _('sound')}
    for t, kind, name in a.get('marks', [])[:400]:
        if t0 <= t <= t1:
            cls = 'msnd' if kind == 'sound' else 'mscn'
            dots += ('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" class="%s"><title>%s: %s @ %.1f s</title></line>'
                     % (x(t), x(t), h - (8 if kind == 'sound' else 0), h if kind == 'sound' else 0, cls,
                        _esc(labels[kind]), _esc(name), t))
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="chart">%s<polyline points="%s" class="line"/>%s</svg>'
            % (w, h, lines, pts, dots))


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


def memory_growth(a):
    """MB gained from the end of start-up to the end of the run (a steady climb may be a leak)."""
    mem = [mb for t, mb in a['memory'] if t >= a['startup_s']]
    return (mem[-1] - mem[0], mem[0]) if len(mem) >= 10 else (0.0, 0.0)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--mut:#667085;--line:#e3e6eb;--good:#1a7f37;--warn:#b26b00;--bad:#c62828;--acc:#3b6fd8}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--fg:#e6e8eb;--mut:#98a2b3;--line:#2c323b;--good:#4cc76b;--warn:#f0a83a;--bad:#ff6b6b;--acc:#7aa2ff}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}
.mut,.note{color:var(--mut)}.note{font-size:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;border-left:4px solid var(--line)}
.kpi b{display:block;font-size:20px}.kpi span{color:var(--mut);font-size:12px}
.good{border-left-color:var(--good)}.warn{border-left-color:var(--warn)}.bad{border-left-color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px}td:first-child{white-space:nowrap}td.barcell{width:55%}.n{text-align:right;font-variant-numeric:tabular-nums}
.chart{width:100%;height:180px}.line{fill:none;stroke:var(--acc);stroke-width:1}.ref{stroke:var(--mut);stroke-dasharray:4 4;stroke-width:.6}
.lbl{fill:var(--mut);font-size:10px}.spike{fill:var(--bad)}
.mscn{stroke:var(--warn);stroke-width:1.5;stroke-dasharray:3 3}.msnd{stroke:var(--good);stroke-width:2}
.chart.mem{height:90px}.memline{fill:none;stroke:var(--warn);stroke-width:1.5}
.bar{height:10px;background:var(--acc);border-radius:4px;min-width:2px}
.ok,.vgood{color:var(--good)}.vwarn{color:var(--warn);font-weight:600}.vbad{color:var(--bad);font-weight:700}.vmut{color:var(--mut)}
.bar.warn{background:var(--warn)}.bar.bad{background:var(--bad)}.bar.good{background:var(--good)}
.adv{list-style:none;padding:0;margin:0}.adv li{padding:8px 10px;border-left:4px solid var(--line);margin:6px 0;background:var(--bg);border-radius:4px}
.adv li.good{border-left-color:var(--good)}.adv li.warn{border-left-color:var(--warn)}.adv li.bad{border-left-color:var(--bad)}
.legend{font-size:12px;color:var(--mut);margin-top:6px}.legend b{font-weight:600}
"""


def write_html(folder, title=None):
    events = read_events(os.path.join(folder, 'trace.jsonl'))
    a = analyze(events)
    shader_items = read_shader_log(folder, a['load_end'])
    game = title or a['session'].get('file') or os.path.basename(folder)
    fps = 1000.0 / a['median'] if a['median'] > 0 else 0.0

    w = []
    w.append('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    w.append('<title>%s</title><style>%s</style></head><body><main>' % (_esc(_('Performance Report')), CSS))
    w.append('<h1>%s</h1><div class="mut">%s &middot; %.1f s &middot; %d %s &middot; %s</div>'
             % (_esc(_('Performance Report')), _esc(os.path.basename(game)), a['duration'], len(a['play']), _esc(_('frames')),
                _esc(_('start-up (not counted): %.1f s') % a['startup_s'])))

    kpis = [
        (_('Typical FPS'), '%.0f' % fps, _level(a['median'], 1000 / 55, 1000 / 30)),
        (_('Median frame'), '%.1f ms' % a['median'], _level(a['median'], 1000 / 55, 1000 / 30)),
        (_('95% of frames under'), '%.1f ms' % a['p95'], _level(a['p95'], 1000 / 45, 1000 / 25)),
        (_('Worst frame'), '%.0f ms' % a['worst'], _level(a['worst'], 50, 100)),
        (_('Spikes'), '%d' % len(a['spikes']), _level(len(a['spikes']), 1, 10)),
        (_('Loads during play'), '%d' % len(a['late']), _level(len(a['late']), 1, 5)),
        (_('Objects never drawn'), '%d' % len(a['never']) if a['has_usage'] else '-', _level(len(a['never']), 1, 20)),
    ]
    w.append('<div class="kpis">' + ''.join('<div class="kpi %s"><b>%s</b><span>%s</span></div>' % (lvl, _esc(v), _esc(k))
                                             for k, v, lvl in kpis) + '</div>')

    w.append('<div class="legend"><b class="vgood">&#9632; %s</b> &nbsp; <b class="vwarn">&#9632; %s</b> &nbsp; <b class="vbad">&#9632; %s</b></div>'
             % (_esc(_('good')), _esc(_('worth a look')), _esc(_('fix first'))))
    w.append('<h2>%s</h2><div class="card"><ul class="adv">%s</ul></div>'
             % (_esc(_('What to do')), ''.join('<li class="%s">%s</li>' % (lvl, _esc(t)) for lvl, t in advice(a, shader_items))))

    now = summary(a, shader_items)
    prev = previous_summary(folder)
    if prev:
        name, rows = _compare(prev, now)
        w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
                 % (_esc(_('Compared with the previous run')), _table((_('Measure'), _('Before'), _('Now'), ''), rows, numeric=(1, 2)),
                    _esc(_('Previous report: %s. Runs differ in what you played, so compare similar sessions.') % name)))

    w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
             % (_esc(_('Frame time')), _chart(a),
                _esc(_('Lower is better. Red dots are spikes: frames much slower than the rest. '
                       'Orange dashed lines: scenes added or removed; green ticks at the bottom: sounds (hover for details).'))))
    if a['has_runtime'] and a['memory']:
        w.append('<h2>%s</h2><div class="card">%s</div>' % (_esc(_('Memory')), _memory_chart(a)))

    if a['categories']:
        total = sum(v for _k, v in a['categories']) or 1.0
        rows = [(k, Markup('<div class="bar %s" style="width:%.0f%%"></div>'
                           % (_level(v, 2.0, 5.0), v / a['categories'][0][1] * 100)),
                 _colored('%.2f' % v, _level(v, 2.0, 5.0))) for k, v in a['categories'][:15]]
        w.append('<h2>%s</h2><div class="card">%s</div>' % (_esc(_('Where the frame time goes (average)')),
                                                            _table((_('Part'), '', 'ms'), rows, numeric=(2,))))

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
            rows.append((e['scene'], '%.0f' % e['ms'], '%.0f' % sh.get('textures_ms', 0), '%.0f' % sh.get('shaders_ms', 0),
                         e.get('objects', '-'), '%.1f s' % e['t']))
        w.append('<h2>%s</h2><div class="card">%s</div>'
                 % (_esc(_('Scene loading')), _table((_('Scene'), _('Convert ms'), _('Textures ms'), _('Shaders ms'),
                                                      _('Objects'), _('At')), rows, numeric=(1, 2, 3, 4))))

    if a['has_usage']:
        w.append('<h2>%s</h2><div class="card">' % _esc(_('Loaded but never drawn')))
        if a['never']:
            w.append(_table((_('Object'), _('Scene'), _('Triangles')),
                            [(o['name'], o['scene'], a['tris'](o)) for o in a['never']], numeric=(2,)))
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
                            [(n, v[1], v[0], '%.1f s' % v[2]) for n, v in a['sounds']], numeric=(2,)))
            w.append('<p class="note">%s</p>' % _esc(_('Sounds started by the Sound actuator, speakers and World Sound. '
                                                      'Sounds played directly with the aud module are not listed.')))
        else:
            w.append('<p class="mut">%s</p>' % _esc(_('No sound was started by the engine in this run.')))
        w.append('</div>')

    if a['work']:
        w.append('<h2>%s</h2><div class="card">%s</div>'
                 % (_esc(_('Work per frame')), _table((_('Counter'), _('Typical'), '95%', _('Max')),
                                                      [(k, '%g' % m, '%g' % p, '%g' % mx) for k, m, p, mx in a['work']],
                                                      numeric=(1, 2, 3))))

    w.append('<p class="note">%s %s</p></main></body></html>' % (_esc(_('Raw data:')), _esc(os.path.join(folder, 'trace.jsonl'))))
    with open(os.path.join(folder, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(now, f)
    out = os.path.join(folder, 'report.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(w))
    return out


if __name__ == '__main__':
    print(write_html(sys.argv[1]))
