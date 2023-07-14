import React, { useEffect } from "react";
import { Box } from "@mui/material";
import { Node, NodeDisplayRenderer, NodeImageRenderer, renderNodeToImage } from "../../lib/node-editor";

const renderer = new NodeImageRenderer({
    backgroundColor: "#fff0",
    padding: 0,
    width: 750,
})

export function NodeDisplay(props: { node: Node }) {
    const [ imageDataUrl, setImageDataUrl ] = React.useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        renderer.render(props.node).then((dataUrl) => {
            if (!cancelled) {
                setImageDataUrl(dataUrl);
            }
        });
        return () => {
            cancelled = true;
        }
    }, [props.node]);

    if (imageDataUrl === null) {
        return null;
    }
    else {
        return (<img src={imageDataUrl} style={{
            width: "100%",
            display: "block",
        }}/>)
    }
}