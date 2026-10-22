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
    play = [fr for f, fr in sorted(frames.items()) if f > LOAD_FRAMES]
    costs = [_cost(fr) for fr in play]
    median = _median(costs)
    limit = max(SPIKE_FACTOR * median, SPIKE_MIN_MS)

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

    spikes = []
    for fr in sorted(play, key=_cost, reverse=True):
        if _cost(fr) <= limit:
            break
        spikes.append(dict(f=fr['f'], t=fr['t'], ms=_cost(fr), cats=_top(fr['c']),
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
        if e['f'] <= LOAD_FRAMES:
            continue
        if e['ev'] == 'convert_object':
            late.append((_('On Demand object'), e['name'], e['ms'], e['f'], e['t']))
        elif e['ev'] == 'scene_load' and not e['scene'].startswith('..'):
            late.append((_('LibLoad') if e.get('libload') else _('Scene'), e['scene'], e['ms'], e['f'], e['t']))
    for e in images.values():
        if e['f'] > LOAD_FRAMES:
            late.append((_('Image upload'), e['name'], e['ms'], e['f'], e['t']))
    late.sort(key=lambda x: x[2], reverse=True)

    work = [e for e in events if e['ev'] == 'work' and e['f'] > LOAD_FRAMES]
    work_rows = []
    if work:
        for k in sorted({k for e in work for k in e if k not in ('t', 'f', 'ev')}):
            v = sorted(e.get(k, 0) for e in work)
            work_rows.append((k, _median(v), _percentile(v, 0.95), v[-1]))

    return dict(session=session, play=play, median=median, limit=limit, spikes=spikes, categories=categories,
                p95=_percentile(costs, 0.95), p99=_percentile(costs, 0.99), worst=max(costs) if costs else 0.0,
                scenes=[e for e in events if e['ev'] == 'scene_load'],
                scene_shaders={e['scene']: e for e in events if e['ev'] == 'load_shaders'},
                has_usage=has_usage, never=never, shadow_only=shadow_only, tris=tris,
                unused_meshes=unused_meshes, unused_mats=unused_mats, unused_imgs=unused_imgs, images=images,
                meshes=meshes, late=late, work=work_rows,
                duration=events[-1]['t'] if events else 0.0)


def read_shader_log(folder):
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
            if frame > LOAD_FRAMES and kind != 'prefetch' and ms >= 1.0:
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
        out.append('<tr>' + ''.join('<td%s>%s</td>' % (' class="n"' if i in numeric else (' class="barcell"' if isinstance(c, Markup) else ''),
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
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="chart">%s<polyline points="%s" class="line"/>%s</svg>'
            % (w, h, lines, pts, dots))


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
.bar{height:10px;background:var(--acc);border-radius:4px;min-width:2px}
.ok{color:var(--good)}
"""


def write_html(folder, title=None):
    events = read_events(os.path.join(folder, 'trace.jsonl'))
    a = analyze(events)
    shader_items = read_shader_log(folder)
    game = title or a['session'].get('file') or os.path.basename(folder)
    fps = 1000.0 / a['median'] if a['median'] > 0 else 0.0

    w = []
    w.append('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    w.append('<title>%s</title><style>%s</style></head><body><main>' % (_esc(_('Performance Report')), CSS))
    w.append('<h1>%s</h1><div class="mut">%s &middot; %.1f s &middot; %d %s</div>'
             % (_esc(_('Performance Report')), _esc(os.path.basename(game)), a['duration'], len(a['play']), _esc(_('frames'))))

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

    w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
             % (_esc(_('Frame time')), _chart(a),
                _esc(_('Lower is better. Red dots are spikes: frames much slower than the rest (hover for details).'))))

    if a['categories']:
        total = sum(v for _k, v in a['categories']) or 1.0
        rows = [(k, Markup('<div class="bar" style="width:%.0f%%"></div>' % (v / a['categories'][0][1] * 100)), '%.2f' % v)
                for k, v in a['categories'][:15]]
        w.append('<h2>%s</h2><div class="card">%s</div>' % (_esc(_('Where the frame time goes (average)')),
                                                            _table((_('Part'), '', 'ms'), rows, numeric=(2,))))

    w.append('<h2>%s</h2><div class="card">' % _esc(_('Spikes')))
    if a['spikes']:
        rows = [('%.1f s' % s['t'], s['f'], '%.0f' % s['ms'], ', '.join('%s %.0f' % c for c in s['cats']),
                 '; '.join(s['loads']) or '-') for s in a['spikes']]
        w.append(_table((_('Time'), _('Frame'), 'ms', _('Slowest parts'), _('Loading at that moment')), rows, numeric=(1, 2)))
    else:
        w.append('<p class="ok">%s</p>' % _esc(_('No spikes: the frame time stays even.')))
    w.append('</div>')

    w.append('<h2>%s</h2><div class="card">' % _esc(_('Loading during play')))
    if a['late']:
        w.append(_table((_('What'), _('Name'), 'ms', _('Frame'), _('Time')),
                        [(k, n, '%.0f' % ms, f, '%.1f s' % t) for k, n, ms, f, t in a['late']], numeric=(2, 3)))
        w.append('<p class="note">%s</p>' % _esc(_('Each of these stalls the game while it loads. Preload them or load them behind a loading screen.')))
    else:
        w.append('<p class="ok">%s</p>' % _esc(_('Nothing loaded during play.')))
    w.append('</div>')

    if shader_items:
        w.append('<h2>%s</h2><div class="card">%s<p class="note">%s</p></div>'
                 % (_esc(_('Shaders and images prepared during play')),
                    _table((_('Kind'), _('Name'), 'ms', _('Frame')), [(k, n, '%.1f' % ms, f) for k, n, ms, f in shader_items],
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

    if a['work']:
        w.append('<h2>%s</h2><div class="card">%s</div>'
                 % (_esc(_('Work per frame')), _table((_('Counter'), _('Typical'), '95%', _('Max')),
                                                      [(k, '%g' % m, '%g' % p, '%g' % mx) for k, m, p, mx in a['work']],
                                                      numeric=(1, 2, 3))))

    w.append('<p class="note">%s %s</p></main></body></html>' % (_esc(_('Raw data:')), _esc(os.path.join(folder, 'trace.jsonl'))))
    out = os.path.join(folder, 'report.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(w))
    return out


if __name__ == '__main__':
    print(write_html(sys.argv[1]))
