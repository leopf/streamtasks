import { Box, Stack, Typography } from "@mui/material";
import React, { useEffect, useRef, useState } from "react";
import { Point } from "../../types/basic";

export function MovableWindow(props: React.PropsWithChildren<{
    title: string,
    xAnchor: "left" | "right",
    yAnchor: "top" | "bottom",
}>) {
    const capturedRef = useRef<boolean>(false);
    const [position, setPosition] = useState<Point>({ x: 0, y: 0 });

    useEffect(() => {
        const mouseUpHandler = (e: MouseEvent) => capturedRef.current = false; 
        const mouseMoveHandler = (e: MouseEvent) => {
            if (!capturedRef.current) return;
            setPosition(pv => ({
                x: props.xAnchor === "left" ? pv.x + e.movementX : pv.x - e.movementX,
                y: props.yAnchor === "top" ? pv.y + e.movementY : pv.y - e.movementY,
            }));
        };
        
        window.addEventListener("mouseup", mouseUpHandler);
        window.addEventListener("mousemove", mouseMoveHandler);

        return () => {
            window.removeEventListener("mouseup", mouseUpHandler);
            window.removeEventListener("mousemove", mouseMoveHandler);
        };
    }, []);

    return (
        <Stack
            position="absolute"
            boxSizing="border-box"
            bgcolor="#fff"
            sx={{ cursor: "move" }}
            {...{ [props.xAnchor]: position.x, [props.yAnchor]: position.y }}
            boxShadow="0 0 10px rgba(0,0,0,0.1)"
            border="1px solid #cfcfcf"
            borderRadius={1}>
            <Box borderBottom="1px solid #cfcfcf" paddingX={1} paddingY={0.5} sx={{ cursor: "move", userSelect: "none" }} onMouseDown={() => capturedRef.current = true}>
                <Typography>{props.title}</Typography>
            </Box>
            <Box flex={1} sx={{ cursor: "default" }}>
                {props.children}
            </Box>
        </Stack>
    )
}