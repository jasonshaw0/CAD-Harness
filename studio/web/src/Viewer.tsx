import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { ComponentMesh, SceneData } from './types';

export type ViewerControl = { fit: () => void; view: (view: string) => void };
type Props = { scene: SceneData | null; previous: SceneData | null; selected: string | null; hidden: Set<string>; isolated: string | null; overlay: boolean; ghost: boolean; onSelect: (id: string | null) => void; controls: React.RefObject<ViewerControl | null> };

export default function Viewer(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const runtime = useRef<{ scene: THREE.Scene; renderer: THREE.WebGLRenderer; camera: THREE.PerspectiveCamera; orbit: OrbitControls; model: THREE.Group; previous: THREE.Group; center: THREE.Vector3; radius: number; fit: () => void } | null>(null);
  const latest = useRef(props);
  latest.current = props;

  useEffect(() => {
    const host = container.current!;
    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x171b1d, 1);
    renderer.domElement.setAttribute('aria-label', 'Interactive 3D model');
    renderer.domElement.setAttribute('data-testid', 'cad-canvas');
    host.append(renderer.domElement);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100000);
    camera.up.set(0, 0, 1);
    camera.position.set(100, -140, 100);
    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true;
    orbit.dampingFactor = 0.12;
    scene.add(new THREE.HemisphereLight(0xe5f4ff, 0x44494b, 2.8));
    const light = new THREE.DirectionalLight(0xffffff, 3.2);
    light.position.set(70, -100, 160); scene.add(light);
    const fill = new THREE.DirectionalLight(0x83d5c2, 1); fill.position.set(-80, 20, 40); scene.add(fill);
    const grid = new THREE.GridHelper(400, 40, 0x3b4448, 0x252e32);
    grid.rotation.x = Math.PI / 2; grid.position.z = -0.15; scene.add(grid);
    const axes = new THREE.AxesHelper(15); axes.position.z = 0.05; scene.add(axes);
    const model = new THREE.Group(), previous = new THREE.Group(); scene.add(model, previous);
    const center = new THREE.Vector3();
    const fit = () => {
      const box = new THREE.Box3().setFromObject(model);
      if (box.isEmpty()) return;
      box.getCenter(center);
      const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1);
      if (runtime.current) runtime.current.radius = radius;
      orbit.target.copy(center);
      camera.position.copy(center).add(new THREE.Vector3(1, -1.5, 1.1).normalize().multiplyScalar(radius * 3.8));
      camera.near = Math.max(radius / 10000, 0.001); camera.far = radius * 1000; camera.updateProjectionMatrix();
      orbit.update();
    };
    runtime.current = { scene, renderer, camera, orbit, model, previous, center, radius: 50, fit };
    props.controls.current = { fit, view: (direction) => {
      const vectors: Record<string, THREE.Vector3> = { top: new THREE.Vector3(0, -0.001, 1), front: new THREE.Vector3(0, -1, 0), right: new THREE.Vector3(1, 0, 0), iso: new THREE.Vector3(1, -1.5, 1.1) };
      const r = runtime.current!;
      camera.position.copy(orbit.target).add(vectors[direction].clone().normalize().multiplyScalar(r.radius * 3.8));
      orbit.update();
    }};
    const resize = () => { const width = host.clientWidth, height = host.clientHeight; renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix(); };
    const observer = new ResizeObserver(resize); observer.observe(host); resize();
    const raycaster = new THREE.Raycaster();
    let down = [0, 0];
    const pointerDown = (event: PointerEvent) => { down = [event.clientX, event.clientY]; };
    const pick = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
      const meshes = model.children.filter(child => child.visible && child instanceof THREE.Mesh);
      const hit = raycaster.intersectObjects(meshes, false)[0];
      latest.current.onSelect(hit ? hit.object.userData.componentId : null);
    };
    renderer.domElement.addEventListener('pointerdown', pointerDown);
    renderer.domElement.addEventListener('pointerup', pick);
    let frame = 0;
    const render = () => { orbit.update(); renderer.render(scene, camera); frame = requestAnimationFrame(render); };
    render();
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); orbit.dispose();
      renderer.domElement.removeEventListener('pointerdown', pointerDown); renderer.domElement.removeEventListener('pointerup', pick);
      scene.traverse(object => { if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) { object.geometry.dispose(); const materials = Array.isArray(object.material) ? object.material : [object.material]; materials.forEach(material => material.dispose()); } });
      renderer.dispose(); host.removeChild(renderer.domElement); runtime.current = null;
    };
  }, []);

  useEffect(() => {
    const r = runtime.current; if (!r) return;
    const clear = (group: THREE.Group) => { for (const object of [...group.children]) { const item = object as THREE.Mesh; item.geometry?.dispose(); (item.material as THREE.Material)?.dispose(); group.remove(object); } };
    const add = (component: ComponentMesh, group: THREE.Group, old = false) => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(component.positions, 3)); geometry.setIndex(component.indices); geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({ color: old ? 0xe5aa6e : 0xa6b4bc, roughness: 0.48, metalness: 0.25, side: THREE.DoubleSide, transparent: old, opacity: old ? 0.23 : 1, depthWrite: !old });
      const mesh = new THREE.Mesh(geometry, material); mesh.userData = { componentId: component.id, role: component.role, old };
      group.add(mesh);
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 25), new THREE.LineBasicMaterial({ color: old ? 0xf2bb7b : 0x222c31, transparent: true, opacity: old ? 0.5 : 0.65 }));
      edges.userData = { componentId: component.id, role: component.role, edge: true }; group.add(edges);
    };
    const wasEmpty = r.model.children.length === 0;
    clear(r.model); clear(r.previous);
    props.scene?.components.forEach(component => add(component, r.model));
    props.previous?.components.forEach(component => {
      const current = props.scene?.components.find(item => item.id === component.id);
      if (!current || current.fingerprint !== component.fingerprint) add(component, r.previous, true);
    });
    if (wasEmpty && props.scene) r.fit();
  }, [props.scene, props.previous]);

  useEffect(() => {
    const r = runtime.current; if (!r) return;
    for (const object of r.model.children) {
      const { componentId, role, edge } = object.userData;
      object.visible = !props.hidden.has(componentId) && (!props.isolated || props.isolated === componentId);
      if (!edge) {
        const material = (object as THREE.Mesh).material as THREE.MeshStandardMaterial;
        const reference = role === 'reference-envelope';
        material.color.set(componentId === props.selected ? 0x82e9ce : reference ? 0x8ca9b8 : 0xaab7bd);
        material.transparent = reference && props.ghost;
        material.opacity = reference && props.ghost ? 0.16 : 1;
        material.depthWrite = !(reference && props.ghost);
      }
    }
    for (const object of r.previous.children) {
      const id = object.userData.componentId;
      object.visible = !props.hidden.has(id) && (!props.isolated || props.isolated === id);
    }
    r.previous.visible = props.overlay;
  }, [props.scene, props.previous, props.selected, props.hidden, props.isolated, props.overlay, props.ghost]);

  return <div className="viewer" ref={container} data-testid="viewer" />;
}
