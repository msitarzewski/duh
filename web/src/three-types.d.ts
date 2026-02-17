import '@react-three/fiber'

declare module '@react-three/fiber' {
  interface ThreeElements {
    group: JSX.IntrinsicElements['group']
    mesh: JSX.IntrinsicElements['mesh']
    instancedMesh: JSX.IntrinsicElements['instancedMesh']
    sphereGeometry: JSX.IntrinsicElements['sphereGeometry']
    meshStandardMaterial: JSX.IntrinsicElements['meshStandardMaterial']
    gridHelper: JSX.IntrinsicElements['gridHelper']
    ambientLight: JSX.IntrinsicElements['ambientLight']
    pointLight: JSX.IntrinsicElements['pointLight']
    fog: JSX.IntrinsicElements['fog']
  }
}
