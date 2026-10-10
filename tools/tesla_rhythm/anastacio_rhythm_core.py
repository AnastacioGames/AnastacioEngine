"""Chart and deterministic scoring, independent of the engine."""
BPM = 112.0
BEAT = 60.0 / BPM
LEAD = 3.0
WINDOW = 0.140


def make_chart():
    phrases = [(0, 1, 2, 4, 3, 2, 1, 0), (2, 3, 4, 2, 1, 3, 2, 0),
               (0, 2, 4, 3, 2, 1, 3, 4), (4, 3, 2, 0, 1, 2, 1, 0)]
    notes = []
    for bar in range(16):
        phrase = phrases[bar % 4]
        for step, lane in enumerate(phrase):
            # Opening four bars teach the five lanes at quarter-note speed.
            if bar < 4 and step % 2:
                continue
            t = LEAD + (bar * 4 + step * 0.5) * BEAT
            notes.append((t, lane))
            if bar >= 12 and step == 0:
                notes.append((t, (lane + 2) % 5))
    return sorted(notes)


class Judge:
    def __init__(self, chart):
        self.chart = chart
        self.done = set()
        self.score = self.combo = self.best = self.hits = self.misses = 0
        self.quality = 0.0

    def expire(self, now):
        count = 0
        for index, (stamp, lane) in enumerate(self.chart):
            if index not in self.done and now - stamp > WINDOW:
                self.done.add(index)
                self.misses += 1
                self.combo = 0
                count += 1
        return count

    def press(self, lane, now):
        candidates = [(abs(now - stamp), index) for index, (stamp, track)
                      in enumerate(self.chart) if track == lane and index not in self.done
                      and abs(now - stamp) <= WINDOW]
        if not candidates:
            self.combo = 0
            return 'FORA DO TEMPO'
        error, index = min(candidates)
        self.done.add(index)
        label, points = ('PERFEITO', 100) if error <= 0.045 else (
            ('BOM', 70) if error <= 0.090 else ('OK', 40))
        self.hits += 1
        self.combo += 1
        self.best = max(self.best, self.combo)
        self.quality += points / 100.0
        self.score += points * min(4, 1 + (self.combo - 1) // 10)
        return label

    @property
    def accuracy(self):
        total = self.hits + self.misses
        return 100.0 * self.quality / total if total else 0.0
