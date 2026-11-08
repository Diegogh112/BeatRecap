/**
 * CompareSlider — comparador de video original vs generado.
 * Divide la vista horizontalmente con un handle arrastrable.
 * El video izquierdo (original) y el derecho (resultado) se reproducen sincronizados.
 */

import { useRef, useState, useEffect, useCallback } from 'react'
import { cn } from '@/utils/cn'
import { Play, Pause, Volume2, VolumeX } from 'lucide-react'

interface CompareSliderProps {
  originalSrc: string
  resultSrc: string
  className?: string
}

export function CompareSlider({ originalSrc, resultSrc, className }: CompareSliderProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const originalRef = useRef<HTMLVideoElement>(null)
  const resultRef = useRef<HTMLVideoElement>(null)
  const [sliderX, setSliderX] = useState(50)   // porcentaje 0–100
  const [isDragging, setIsDragging] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // ── Sincronización de videos ────────────────────────────────────────────────

  const syncVideos = useCallback((time: number) => {
    if (originalRef.current) originalRef.current.currentTime = time
    if (resultRef.current) resultRef.current.currentTime = time
  }, [])

  const togglePlay = useCallback(() => {
    const orig = originalRef.current
    const res = resultRef.current
    if (!orig || !res) return
    if (isPlaying) {
      orig.pause(); res.pause()
    } else {
      orig.currentTime = res.currentTime  // sync antes de play
      orig.play().catch(() => {})
      res.play().catch(() => {})
    }
    setIsPlaying(!isPlaying)
  }, [isPlaying])

  const toggleMute = useCallback(() => {
    const orig = originalRef.current
    const res = resultRef.current
    if (!orig || !res) return
    orig.muted = !isMuted
    res.muted = !isMuted
    setIsMuted(!isMuted)
  }, [isMuted])

  // Time update solo desde el video original
  useEffect(() => {
    const orig = originalRef.current
    if (!orig) return
    const onTimeUpdate = () => setCurrentTime(orig.currentTime)
    const onLoaded = () => setDuration(orig.duration)
    const onEnded = () => setIsPlaying(false)
    orig.addEventListener('timeupdate', onTimeUpdate)
    orig.addEventListener('loadedmetadata', onLoaded)
    orig.addEventListener('ended', onEnded)
    return () => {
      orig.removeEventListener('timeupdate', onTimeUpdate)
      orig.removeEventListener('loadedmetadata', onLoaded)
      orig.removeEventListener('ended', onEnded)
    }
  }, [])

  // ── Drag del slider ─────────────────────────────────────────────────────────

  const getPercent = useCallback((clientX: number) => {
    const container = containerRef.current
    if (!container) return 50
    const { left, width } = container.getBoundingClientRect()
    return Math.min(100, Math.max(0, ((clientX - left) / width) * 100))
  }, [])

  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  useEffect(() => {
    if (!isDragging) return
    const onMove = (e: MouseEvent) => setSliderX(getPercent(e.clientX))
    const onTouchMove = (e: TouchEvent) => setSliderX(getPercent(e.touches[0].clientX))
    const onUp = () => setIsDragging(false)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    window.addEventListener('touchmove', onTouchMove)
    window.addEventListener('touchend', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      window.removeEventListener('touchmove', onTouchMove)
      window.removeEventListener('touchend', onUp)
    }
  }, [isDragging, getPercent])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className={cn('relative select-none rounded-xl overflow-hidden bg-black', className)}>
      {/* Video original — ocupa todo */}
      <video
        ref={originalRef}
        src={originalSrc}
        className="w-full h-full object-contain"
        muted={isMuted}
        playsInline
        preload="metadata"
      />

      {/* Video resultado — clip por la derecha del slider */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ clipPath: `inset(0 0 0 ${sliderX}%)` }}
      >
        <video
          ref={resultRef}
          src={resultSrc}
          className="w-full h-full object-contain"
          muted={isMuted}
          playsInline
          preload="metadata"
        />
      </div>

      {/* Línea divisoria */}
      <div
        ref={containerRef}
        className="absolute inset-0 cursor-col-resize"
        onMouseDown={onMouseDown}
        onTouchStart={(e) => { setIsDragging(true); setSliderX(getPercent(e.touches[0].clientX)) }}
      >
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white/80 shadow-lg"
          style={{ left: `${sliderX}%` }}
        >
          {/* Handle */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-xl border border-white/20">
            <div className="flex gap-0.5">
              <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
              <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
            </div>
          </div>
        </div>
      </div>

      {/* Labels */}
      <div className="absolute top-3 left-3 pointer-events-none">
        <span className="text-xs font-semibold text-white bg-black/50 rounded px-2 py-0.5 backdrop-blur-sm">
          Original
        </span>
      </div>
      <div className="absolute top-3 right-3 pointer-events-none">
        <span className="text-xs font-semibold text-primary bg-black/50 rounded px-2 py-0.5 backdrop-blur-sm">
          Resultado
        </span>
      </div>

      {/* Controles inferiores */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3">
        {/* Seek bar */}
        <input
          type="range"
          min={0}
          max={duration || 100}
          step={0.1}
          value={currentTime}
          onChange={(e) => syncVideos(Number(e.target.value))}
          className="w-full h-1 accent-primary cursor-pointer mb-2"
        />
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors text-white"
            aria-label={isPlaying ? 'Pausar' : 'Reproducir'}
          >
            {isPlaying
              ? <Pause className="h-4 w-4" />
              : <Play className="h-4 w-4" />}
          </button>
          <button
            onClick={toggleMute}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors text-white"
            aria-label={isMuted ? 'Activar sonido' : 'Silenciar'}
          >
            {isMuted
              ? <VolumeX className="h-4 w-4" />
              : <Volume2 className="h-4 w-4" />}
          </button>
          <span className="text-xs text-white/70 font-mono">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          <span className="ml-auto text-xs text-white/50">
            ← arrastra para comparar →
          </span>
        </div>
      </div>
    </div>
  )
}
