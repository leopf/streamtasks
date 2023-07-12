import React, { useEffect } from "react";
import { Node, NodeDisplayRenderer } from "../lib/node-editor";

export function NodeDisplay(props: { node: Node }) {
    const containerRef = React.useRef<HTMLDivElement>(null);

    useEffect(() => {
        const display = new NodeDisplayRenderer(props.node, containerRef.current!);
        return () => display.destroy();
    }, [props.node]);

    return <div style={{ width: "100%", height: "100%" }} ref={containerRef}></div>
}