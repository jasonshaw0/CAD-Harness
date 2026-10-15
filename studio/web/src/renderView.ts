/** Lazy, private renderer: never reads or changes the interactive viewport. */
import * as THREE from 'three';
import type { SceneData } from './types';

export type CaptureRequest = {
  id: string; client_id: string; lease_token: string; scene_fingerprint: string;
  width: number; height: number; scene: SceneData;
  camera: { projection: string; position: number[]; target: number[]; up: number[];
    near: number; far: number; left: number; right: number; top: number; bottom: number };
};

let renderer: THREE.WebGLRenderer | null = null;
export function disposeRenderer() { renderer?.dispose(); renderer = null; }

export async function renderView(request: CaptureRequest): Promise<string> {
  if (!renderer) {
    renderer = new THREE.WebGLRenderer({ canvas: document.createElement('canvas'), antialias: true });
    renderer.setPixelRatio(1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
  }
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf4f6f7);
  scene.add(new THREE.HemisphereLight(0xf0f5ff, 0x667780, 2.3));
  const settings = request.camera;
  const camera = new THREE.OrthographicCamera(settings.left, settings.right, settings.top,
    settings.bottom, settings.near, settings.far);
  camera.position.fromArray(settings.position); camera.up.fromArray(settings.up);
  camera.lookAt(new THREE.Vector3().fromArray(settings.target));
  // Lights follow camera orientation so opposite views remain equally legible.
  const key = new THREE.DirectionalLight(0xffffff, 2.5);
  const target = new THREE.Vector3().fromArray(settings.target);
  key.position.copy(camera.position).add(new THREE.Vector3(0, 0, settings.far * .2));
  key.target.position.copy(target); scene.add(key, key.target);
  const fill = new THREE.DirectionalLight(0xb3c9e0, 1);
  fill.position.copy(target).multiplyScalar(2).sub(camera.position);
  fill.target.position.copy(target); scene.add(fill, fill.target);
  try {
    for (const component of request.scene.components) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(component.positions, 3));
      geometry.setIndex(component.indices); geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({ color: 0x93a8b5, roughness: .6,
        metalness: .12, side: THREE.DoubleSide });
      scene.add(new THREE.Mesh(geometry, material));
      scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 25),
        new THREE.LineBasicMaterial({ color: 0x222c31, transparent: true, opacity: .65 })));
    }
    renderer.setSize(request.width, request.height, false);
    if (renderer.getContext().isContextLost()) throw new Error('Studio capture WebGL context was lost');
    renderer.render(scene, camera);
    // Read immediately after render; no preserveDrawingBuffer or animation loop.
    const blob = await new Promise<Blob>((resolve, reject) => renderer!.domElement.toBlob(
      value => value ? resolve(value) : reject(new Error('Studio could not encode the PNG')), 'image/png'));
    return await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve((reader.result as string).split(',')[1]);
      reader.onerror = () => reject(new Error('Studio could not read the PNG'));
      reader.readAsDataURL(blob);
    });
  } finally {
    scene.traverse(object => {
      if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
        object.geometry.dispose();
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        materials.forEach(material => material.dispose());
      }
    });
  }
}
