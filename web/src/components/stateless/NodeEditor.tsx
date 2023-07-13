import React, { useEffect } from "react";
import { NodeEditorRenderer } from "../../lib/node-editor";
import { Box } from "@mui/material";

export function NodeEditor(props: { editor: NodeEditorRenderer }) {
    const containerRef = React.useRef<HTMLDivElement>(null);

    useEffect(() => {
        props.editor.mount(containerRef.current!);
        return () => props.editor.unmount();
    }, [props.editor]);

    return <Box sx={{ width: "100%", height: "100%" }} ref={containerRef}/>
}