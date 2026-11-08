"""
Diagnóstico: prueba detección InsightFace en todas las fotos de reemplazo subidas.
"""
import sys
import os
sys.path.insert(0, '.')

import cv2
import numpy as np
from pathlib import Path
from insightface.app import FaceAnalysis

# Inicializar con CPU, det_size=640
app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1, det_size=(640, 640))

# Buscar fotos de reemplazo (no son frames ni thumbs)
thumb_dir = Path('thumbnails')
photos = sorted(
    [p for p in thumb_dir.rglob('*.jpg')
     if 'frame_' not in p.name and '_thumb' not in p.name],
    key=lambda p: p.stat().st_mtime,
    reverse=True
)

print(f"Fotos de reemplazo encontradas: {len(photos)}")
print()

for photo in photos[:20]:
    img = cv2.imread(str(photo))
    if img is None:
        print(f"  ERROR leyendo: {photo.name}")
        continue

    h, w = img.shape[:2]

    # Test 1: imagen original
    faces = app.get(img)
    scores = [round(f.det_score, 3) for f in faces]

    # Test 2: upscale 2x
    img_up = cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_LINEAR)
    faces_up = app.get(img_up)
    scores_up = [round(f.det_score, 3) for f in faces_up]

    # Test 3: solo si es pequeña, escalar a mínimo 512px
    if min(h, w) < 512:
        scale = 512 / min(h, w)
        img_512 = cv2.resize(img, (int(w*scale), int(h*scale)))
        faces_512 = app.get(img_512)
        scores_512 = [round(f.det_score, 3) for f in faces_512]
    else:
        scores_512 = ['n/a']

    detected = bool(scores and max(scores) >= 0.3)
    status = "DETECTADA" if detected else "NO DETECTADA"

    print(f"{photo.name[:50]}")
    print(f"  Tamaño: {w}x{h} | {photo.stat().st_size} bytes")
    print(f"  Original:  {scores}")
    print(f"  Upscale2x: {scores_up}")
    print(f"  Min512px:  {scores_512}")
    print(f"  Estado: {status}")
    print()
