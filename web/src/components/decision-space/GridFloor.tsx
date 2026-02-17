export function GridFloor() {
  return (
    <group>
      <gridHelper
        args={[20, 20, '#00d4ff', '#00d4ff']}
        position={[0, -5, 0]}
        material-opacity={0.06}
        material-transparent={true}
      />
      <gridHelper
        args={[20, 4, '#00d4ff', '#00d4ff']}
        position={[0, -5, 0]}
        material-opacity={0.12}
        material-transparent={true}
      />
    </group>
  )
}
