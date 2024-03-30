import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { NodeEditorRenderer } from './lib/node-editor';

window.React = React;

function App() {
    const containerRef = useRef<HTMLDivElement>(null);
    const [nodeRenderer,_] = useState(() => new NodeEditorRenderer())

    useEffect(() => {
        nodeRenderer.mount(containerRef.current!);
        // nodeRenderer.addNode()
    }, [])

    return <div style={{ width: "100vw", height: "100vh" }} ref={containerRef}></div>
}

const root = createRoot(document.getElementById("root")!);
root.render((<App/>))