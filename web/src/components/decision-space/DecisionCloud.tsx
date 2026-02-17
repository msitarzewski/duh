import { useRef, useMemo } from 'react'
import * as THREE from 'three'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import type { SpaceDecision } from '@/api/types'
import { outcomeColor, categoryIndex, genusIndex } from '@/utils'
import { useDecisionSpaceStore } from '@/stores'

interface DecisionCloudProps {
  decisions: SpaceDecision[]
  categories: string[]
  genera: string[]
  timelinePosition: number
}

export function DecisionCloud({ decisions, categories, genera, timelinePosition }: DecisionCloudProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const smoothScales = useRef<Float32Array>(new Float32Array(0))
  const { hoveredId, selectedId, setHovered, setSelected } = useDecisionSpaceStore()

  const { positions, colors, scales, visibleDecisions } = useMemo(() => {
    if (decisions.length === 0) {
      return { positions: [] as [number, number, number][], colors: [] as [number, number, number][], scales: [] as number[], visibleDecisions: [] as SpaceDecision[] }
    }

    const dates = decisions.map((d) => new Date(d.created_at).getTime())
    const minDate = Math.min(...dates)
    const maxDate = Math.max(...dates)
    const dateRange = maxDate - minDate || 1

    const cutoffTime = minDate + dateRange * timelinePosition

    const visible = decisions.filter(
      (d) => new Date(d.created_at).getTime() <= cutoffTime,
    )

    const pos: [number, number, number][] = []
    const col: [number, number, number][] = []
    const scl: number[] = []

    for (const d of visible) {
      const t = (new Date(d.created_at).getTime() - minDate) / dateRange
      const x = (t - 0.5) * 16
      const y = categoryIndex(d.category, categories) * 2 - (categories.length * 2) / 2
      const z = genusIndex(d.genus, genera) * 2 - (genera.length * 2) / 2

      pos.push([x, y, z])

      const color = new THREE.Color(outcomeColor(d.outcome))
      col.push([color.r, color.g, color.b])

      scl.push(0.15 + d.confidence * 0.35)
    }

    return { positions: pos, colors: col, scales: scl, visibleDecisions: visible }
  }, [decisions, categories, genera, timelinePosition])

  useFrame(() => {
    if (!meshRef.current || positions.length === 0) return

    if (smoothScales.current.length !== positions.length) {
      smoothScales.current = new Float32Array(positions.length)
      for (let i = 0; i < positions.length; i++) {
        smoothScales.current[i] = scales[i]!
      }
    }

    const tempObject = new THREE.Object3D()
    const tempColor = new THREE.Color()
    const lerpFactor = 0.12

    for (let i = 0; i < positions.length; i++) {
      const pos = positions[i]!
      const scale = scales[i]!
      const col = colors[i]!
      const decision = visibleDecisions[i]!

      const isHovered = decision.id === hoveredId
      const isSelected = decision.id === selectedId
      const targetScale = isHovered || isSelected ? scale * 1.5 : scale

      const current = smoothScales.current[i] ?? targetScale
      smoothScales.current[i] = current + (targetScale - current) * lerpFactor

      tempObject.position.set(pos[0], pos[1], pos[2])
      tempObject.scale.setScalar(smoothScales.current[i]!)
      tempObject.updateMatrix()
      meshRef.current.setMatrixAt(i, tempObject.matrix)

      tempColor.setRGB(col[0], col[1], col[2])
      if (isHovered || isSelected) {
        tempColor.multiplyScalar(1.5)
      }
      meshRef.current.setColorAt(i, tempColor)
    }

    meshRef.current.count = positions.length
    meshRef.current.instanceMatrix.needsUpdate = true
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true
    }
  })

  const hoveredDecision = visibleDecisions.find((d) => d.id === hoveredId)

  const hoveredPosition = useMemo((): [number, number, number] | null => {
    if (!hoveredDecision || decisions.length === 0) return null

    const dates = decisions.map((d) => new Date(d.created_at).getTime())
    const minDate = Math.min(...dates)
    const maxDate = Math.max(...dates)
    const dateRange = maxDate - minDate || 1

    const t = (new Date(hoveredDecision.created_at).getTime() - minDate) / dateRange
    const x = (t - 0.5) * 16
    const y = categoryIndex(hoveredDecision.category, categories) * 2 - (categories.length * 2) / 2 + 1
    const z = genusIndex(hoveredDecision.genus, genera) * 2 - (genera.length * 2) / 2

    return [x, y, z]
  }, [hoveredDecision, decisions, categories, genera])

  return (
    <group>
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, Math.max(decisions.length, 1)]}
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation()
          const idx = e.instanceId
          if (idx !== undefined && visibleDecisions[idx]) {
            setHovered(visibleDecisions[idx]!.id)
          }
        }}
        onPointerOut={() => setHovered(null)}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation()
          const idx = e.instanceId
          if (idx !== undefined && visibleDecisions[idx]) {
            setSelected(visibleDecisions[idx]!.id)
          }
        }}
      >
        <sphereGeometry args={[1, 16, 16]} />
        <meshStandardMaterial
          transparent
          opacity={0.85}
          roughness={0.3}
          metalness={0.2}
        />
      </instancedMesh>

      {hoveredDecision && hoveredPosition && (
        <Html
          position={hoveredPosition}
          style={{ pointerEvents: 'none' }}
        >
          <div className="bg-[rgba(10,10,15,0.9)] border border-[rgba(0,212,255,0.3)] rounded-lg p-3 max-w-[200px] backdrop-blur-md">
            <p className="text-[11px] text-[#e4e4e7] line-clamp-2 mb-1">{hoveredDecision.question}</p>
            <div className="flex items-center gap-2 text-[10px] font-mono">
              <span className="text-[#00d4ff]">{(hoveredDecision.confidence * 100).toFixed(0)}%</span>
              {hoveredDecision.category && (
                <span className="text-[#a1a1aa]">{hoveredDecision.category}</span>
              )}
            </div>
          </div>
        </Html>
      )}
    </group>
  )
}
