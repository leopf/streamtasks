import { NodeEditorRenderer } from './lib/node-editor';
import { GateTask, NumberGeneratorTask } from "./sample-nodes";

// Create a Pixi Application in #root element

const hostEl = document.getElementById('root');
if (!hostEl) {
    throw new Error('Root element not found');
}

// const display = new NodeDisplayRenderer(new GateTask({ x: 100, y: 100 }), hostEl)

const renderer = new NodeEditorRenderer()
renderer.mount(hostEl);

renderer.addNode(new GateTask({ x: 100, y: 100 }))
renderer.addNode(new GateTask({ x: 300, y: 300 }))
renderer.addNode(new GateTask({ x: 700, y: 700 }))
renderer.addNode(new NumberGeneratorTask({ x: 400, y: 400 }))

setTimeout(() => {
    renderer.addNode(new GateTask({ x: 0, y: 0 }), true)
}, 3000);