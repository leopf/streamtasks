import React, { useEffect } from "react";
import { Box } from "@mui/material";
import { Node, NodeDisplayRenderer } from "../../lib/node-editor";

export function NodeDisplay(props: { node: Node }) {
    const containerRef = React.useRef<HTMLDivElement>(null);

    useEffect(() => {
        const display = new NodeDisplayRenderer(props.node, containerRef.current!);
        return () => display.destroy();
    }, [props.node]);

    return <Box sx={{ width: "100%", height: "100%" }} ref={containerRef}/>
}