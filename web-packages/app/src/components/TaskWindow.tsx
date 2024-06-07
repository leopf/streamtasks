import { useRef, useState, useEffect } from "react";
import { Box } from "@mui/material";

export function TaskWindow(props: React.PropsWithChildren<{}>) {
    const resizingRef = useRef(false);
    const [addSize, setAddSize] = useState(0);

    useEffect(() => {
        const mouseUpHandler = () => resizingRef.current = false;
        const mouseMoveHandler = (e: MouseEvent) => {
            if (!resizingRef.current) return;
            setAddSize(pv => Math.min(0, pv + e.movementY));
        };

        window.addEventListener("mouseup", mouseUpHandler);
        window.addEventListener("mousemove", mouseMoveHandler);

        return () => {
            window.removeEventListener("mouseup", mouseUpHandler);
            window.removeEventListener("mousemove", mouseMoveHandler);
        };
    }, []);

    return (
        <Box position="absolute" top="1rem" right="1rem" width="30%" height={`calc(100% - 2rem + ${addSize}px)`}>
            {props.children}
            <Box position="absolute" bottom={0} left={0} width={"100%"} height="4px" sx={{ cursor: "ns-resize", userSelect: "none" }} onMouseDown={() => resizingRef.current = true} />
        </Box>
    );
}