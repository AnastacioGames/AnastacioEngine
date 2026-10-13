# Preenche com audio os 14 slots do modulo Effects que a demo Destruction.range ja tem
# (Explosion/Destruction por tamanho, Rain, Thunder x3), todos sem arquivo. Nao cria
# slot novo, nao mexe em mais nada da cena.
import math
import os
import struct
import wave

import bpy


def write_boom(path, seconds, base_freq, intensity):
    import random
    rate = 22050
    rnd = random.Random(int(base_freq))
    frames = bytearray()
    n = int(rate * seconds)
    low = 0.0
    for i in range(n):
        t = i / rate
        decay = math.exp(-t * (6.0 - intensity * 1.5))
        low += 0.3 * (rnd.uniform(-1.0, 1.0) - low)
        thump = math.sin(2.0 * math.pi * base_freq * t) * math.exp(-t * (12.0 - intensity * 3.0))
        frames += struct.pack('<h', int(32767 * intensity * max(-1.0, min(1.0, decay * low * 0.8 + thump * 0.6))))
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(bytes(frames))
    w.close()


def write_crack(path, seed, seconds, intensity):
    import random
    rate = 22050
    rnd = random.Random(seed)
    frames = bytearray()
    n = int(rate * seconds)
    low = 0.0
    for i in range(n):
        t = i / rate
        low += 0.5 * (rnd.uniform(-1.0, 1.0) - low)
        gain = math.exp(-t * (10.0 - intensity * 2.0))
        frames += struct.pack('<h', int(32767 * intensity * max(-1.0, min(1.0, gain * low))))
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(bytes(frames))
    w.close()


def write_thunder(path, seed, seconds=1.4):
    import random
    rate = 22050
    rnd = random.Random(seed)
    frames = bytearray()
    n = int(rate * seconds)
    low = 0.0
    crack_end = 0.08
    for i in range(n):
        t = i / rate
        low += 0.08 * (rnd.uniform(-1.0, 1.0) - low)
        gain = 1.0 if t < crack_end else math.exp(-(t - crack_end) * 1.8)
        frames += struct.pack('<h', int(32767 * max(-1.0, min(1.0, gain * low))))
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(bytes(frames))
    w.close()


def write_rain(path, seconds=3.0):
    import random
    rate = 22050
    rnd = random.Random(3)
    frames = bytearray()
    n = int(rate * seconds)
    low = 0.0
    for i in range(n):
        low += 0.4 * (rnd.uniform(-1.0, 1.0) - low)
        frames += struct.pack('<h', int(32767 * 0.5 * low))
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(bytes(frames))
    w.close()


demo_dir = os.path.dirname(bpy.data.filepath)
audio_dir = os.path.join(demo_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)

# tamanho -> (duracao, frequencia do baque, intensidade)
sizes = {
    "Tiny": (0.35, 90, 0.35),
    "Small": (0.5, 75, 0.5),
    "Medium": (0.7, 60, 0.7),
    "Large": (0.9, 50, 0.85),
    "Huge": (1.2, 40, 1.0),
}
for size, (seconds, freq, intensity) in sizes.items():
    write_boom(os.path.join(audio_dir, "explosao_%s.wav" % size.lower()), seconds, freq, intensity)
    write_crack(os.path.join(audio_dir, "quebra_%s.wav" % size.lower()), hash(size) & 0xFFFF, seconds * 0.7, intensity)

write_rain(os.path.join(audio_dir, "chuva.wav"))
write_thunder(os.path.join(audio_dir, "trovao1.wav"), 10)
write_thunder(os.path.join(audio_dir, "trovao2.wav"), 11)
write_thunder(os.path.join(audio_dir, "trovao3.wav"), 12)

world = bpy.context.scene.world
effects = world.sound_modules["Effects"]

mapping = {
    "Explosion Tiny": "audio/explosao_tiny.wav",
    "Explosion Small": "audio/explosao_small.wav",
    "Explosion Medium": "audio/explosao_medium.wav",
    "Explosion Large": "audio/explosao_large.wav",
    "Explosion Huge": "audio/explosao_huge.wav",
    "Destruction Tiny": "audio/quebra_tiny.wav",
    "Destruction Small": "audio/quebra_small.wav",
    "Destruction Medium": "audio/quebra_medium.wav",
    "Destruction Large": "audio/quebra_large.wav",
    "Destruction Huge": "audio/quebra_huge.wav",
    "Rain": "audio/chuva.wav",
    "Thunder 1": "audio/trovao1.wav",
    "Thunder 2": "audio/trovao2.wav",
    "Thunder 3": "audio/trovao3.wav",
}
missing = []
for sound in effects.sounds:
    rel = mapping.get(sound.name)
    if rel is None:
        missing.append(sound.name)
        continue
    sound.filepath = "//" + rel

bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print("SALVO", bpy.data.filepath)
print("sem mapeamento:", missing)
print("conferencia:", [(s.name, s.filepath) for s in effects.sounds])
