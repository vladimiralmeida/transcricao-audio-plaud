"""Teste de diarização (etapa 2). Uso: python teste_diarizacao.py <audio> [num_falantes]"""
import os
import sys
import time

import torch


def registrar_dlls_nvidia():
    base = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    if os.path.isdir(base):
        for sub in os.listdir(base):
            b = os.path.join(base, sub, "bin")
            if os.path.isdir(b):
                os.add_dll_directory(b)


registrar_dlls_nvidia()

from pyannote.audio import Pipeline  # noqa: E402

audio = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else None
token = os.environ.get("HF_TOKEN")  # só necessário no primeiro download

t0 = time.time()
pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
pipe.to(torch.device("cuda"))
t1 = time.time()
import wave  # noqa: E402

import numpy as np  # noqa: E402

with wave.open(audio, "rb") as w:  # WAV PCM16; evita depender do torchcodec
    sr, ch = w.getframerate(), w.getnchannels()
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
x = pcm.reshape(-1, ch).mean(axis=1).astype(np.float32) / 32768.0
entrada = {"waveform": torch.from_numpy(x).unsqueeze(0), "sample_rate": sr}
out = pipe(entrada, num_speakers=n) if n else pipe(entrada)
t2 = time.time()
print(f"carga={t1-t0:.1f}s diarizacao={t2-t1:.1f}s pico_vram={torch.cuda.max_memory_allocated()/2**20:.0f}MiB")
for turn, _, spk in out.speaker_diarization.itertracks(yield_label=True):
    print(f"[{turn.start:6.1f}-{turn.end:6.1f}] {spk}")
