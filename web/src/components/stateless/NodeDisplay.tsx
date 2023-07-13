import React, { useEffect } from "react";
import { Box } from "@mui/material";
import { Node, NodeDisplayRenderer } from "../../lib/node-editor";

export function NodeDisplay(props: { node: Node, backgroundColor?: string, padding?: number, resizeHeight?: boolean }) {
    const containerRef = React.useRef<HTMLDivElement>(null);

    useEffect(() => {
        const display = new NodeDisplayRenderer(props.node, containerRef.current!, {
            backgroundColor: props.backgroundColor,
            padding: props.padding
        });
        display.onUpdated(() => {
            if (props.resizeHeight) {
                containerRef.current!.style.height = `${display.perfectHeight}px`;
            }
        });

        return () => display.destroy();
    }, [props.node, props.backgroundColor, props.padding, props.resizeHeight]);

    return <Box sx={{ width: "100%", height: "100%" }} ref={containerRef}/>
}