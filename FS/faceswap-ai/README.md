# FaceSwap AI

Aplicación web profesional de intercambio de rostros en videos mediante inteligencia artificial.

## Descripción

FaceSwap AI permite subir un video, detectar automáticamente todos los rostros presentes, seleccionar cuáles reemplazar, cargar fotografías de los nuevos rostros y generar un nuevo video conservando movimientos, gestos, audio y duración del original.

## Tecnologías

### Frontend
- React 18 + TypeScript
- Tailwind CSS + shadcn/ui
- Zustand (estado global)
- TanStack Query (fetching / caché)
- React Dropzone
- Axios

### Backend
- Python 3.11 + FastAPI
- Celery + Redis (cola de trabajos)
- SQLAlchemy + SQLite
- FFmpeg

### Inteligencia Artificial
- InsightFace (buffalo_l) — detección y embeddings faciales
- SCRFD — detección rápida de rostros
- ArcFace — agrupación de identidades
- InSwapper (inswapper_128.onnx) — motor de face swap neural
- GFPGAN / CodeFormer — mejora de calidad post-swap
- ByteTrack — seguimiento de personas entre frames

## Requisitos de hardware

| Escenario | CPU | RAM | GPU | Tiempo (5 min video) |
|---|---|---|---|---|
| Mínimo (CPU only) | 8 cores | 16 GB | — | 45–90 min |
| Recomendado | 8 cores | 32 GB | NVIDIA 8 GB VRAM | 5–15 min |
| Óptimo | 16 cores | 64 GB | NVIDIA 24 GB VRAM | 2–5 min |

## Instalación

### Prerequisitos
- Node.js 18+
- Python 3.11+
- Redis (para Celery)
- FFmpeg instalado en el sistema
- CUDA 11.8+ (opcional, para GPU)

### Modelo InSwapper
Descargar `inswapper_128.onnx` desde el repositorio oficial de InsightFace y colocarlo en:
```
backend/models/inswapper_128.onnx
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Worker Celery
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

## Estructura del proyecto

```
faceswap-ai/
├── frontend/               # React + TypeScript
│   ├── src/
│   │   ├── components/     # Componentes reutilizables
│   │   ├── pages/          # Pantallas de la aplicación
│   │   ├── stores/         # Estado global (Zustand)
│   │   ├── services/       # Clientes API
│   │   └── types/          # Interfaces TypeScript
│   └── package.json
│
├── backend/                # FastAPI + Celery
│   ├── app/
│   │   ├── api/            # Endpoints REST
│   │   ├── core/           # Configuración y seguridad
│   │   ├── models/         # Modelos SQLAlchemy
│   │   ├── schemas/        # Schemas Pydantic
│   │   ├── services/       # Lógica de negocio + IA
│   │   └── workers/        # Tareas Celery
│   ├── models/             # Archivos de modelos IA (.onnx)
│   ├── uploads/            # Videos subidos (temporal)
│   ├── outputs/            # Videos generados (temporal)
│   ├── thumbnails/         # Miniaturas de rostros
│   ├── requirements.txt
│   └── main.py
│
├── docker-compose.yml
└── README.md
```

## Aviso legal

Esta aplicación es una herramienta de IA para uso creativo y educativo.
El usuario es responsable de obtener los permisos necesarios para el uso de imágenes y videos.
Queda prohibido su uso para suplantación de identidad, acoso o contenido no consentido.
