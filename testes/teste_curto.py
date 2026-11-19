"""Teste de transcrição com áudio curto (etapa 1). Uso: python teste_curto.py <audio>"""
import os
import sys
import time


def registrar_dlls_nvidia():
    """Torna visíveis as DLLs cuBLAS/cuDNN instaladas via pip (Windows)."""
    base = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    if not os.path.isdir(base):
        return
    for sub in os.listdir(base):
        bin_dir = os.path.join(base, sub, "bin")
        if os.path.isdir(bin_dir):
            os.add_dll_directory(bin_dir)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]


registrar_dlls_nvidia()

from faster_whisper import WhisperModel  # noqa: E402

audio = sys.argv[1]
t0 = time.time()
model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
t1 = time.time()
segs, info = model.transcribe(audio, language="pt", vad_filter=True)
texto = [(s.start, s.end, s.text.strip()) for s in segs]
t2 = time.time()
print(f"duracao={info.duration:.1f}s carga_modelo={t1-t0:.1f}s transcricao={t2-t1:.1f}s")
for a, b, t in texto:
    print(f"[{a:6.1f}-{b:6.1f}] {t}")
