import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ConnectResult, InputConnection, NodeEditorRenderer, OutputConnection } from './lib/node-editor';
import { Node } from "./lib/node-editor";

window.React = React;

class DemoNode implements Node {
    public id: string = String(Math.random());
    public label: string = "Test";
    public position: { x: number; y: number; } = { x: 200 + 100 * Math.random(), y: 200 + 100 * Math.random() };
    public outputs: OutputConnection[] = [Math.floor(Math.random() * 1000000), Math.floor(Math.random() * 1000000)].map((id, idx) => ({ id, streamId: id, label: `out ${idx + 1}` }));
    public inputs: InputConnection[] = [String(Math.random() * 1000000), String(Math.random() * 1000000)].map((id, idx) => ({ id, key: id, label: `in ${idx + 1}` }));

    public async connect(key: string, output?: OutputConnection | undefined): Promise<ConnectResult> {
        const input = this.inputs.find(i => i.key == key);
        if (!input) return "Input not found!";
        input.streamId = output?.streamId;
        return true;
    }
    onUpdated?: ((cb: () => void) => void) | undefined;
}

function App() {
    const containerRef = useRef<HTMLDivElement>(null);
    const [nodeRenderer,_] = useState(() => new NodeEditorRenderer())

    useEffect(() => {
        nodeRenderer.mount(containerRef.current!);
        nodeRenderer.addNode(new DemoNode())
        nodeRenderer.addNode(new DemoNode())
    }, [])

    return <div style={{ width: "100vw", height: "100vh" }} ref={containerRef}></div>
}

const root = createRoot(document.getElementById("root")!);
root.render((<App/>))