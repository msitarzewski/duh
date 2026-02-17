import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { GridFloor } from './GridFloor'
import { DecisionCloud } from './DecisionCloud'
import { useDecisionSpaceStore } from '@/stores'
import type { SpaceDecision } from '@/api/types'

interface Scene3DProps {
  decisions: SpaceDecision[]
  timelinePosition: number
}

export default function Scene3D({ decisions, timelinePosition }: Scene3DProps) {
  const { availableCategories, availableGenera } = useDecisionSpaceStore()

  return (
    <Canvas
      camera={{ position: [12, 8, 12], fov: 50 }}
      style={{ background: '#0a0a0f' }}
      gl={{ antialias: true }}
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={0.8} />
      <fog attach="fog" args={['#0a0a0f', 15, 35]} />

      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={5}
        maxDistance={30}
      />

      <GridFloor />

      <DecisionCloud
        decisions={decisions}
        categories={availableCategories}
        genera={availableGenera}
        timelinePosition={timelinePosition}
      />
    </Canvas>
  )
}
