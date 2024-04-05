import { Box, IconButton, Stack, Typography } from "@mui/material";
import { ManagedTask } from "../../lib/task";
import { useEffect, useMemo, useRef, useState } from "react";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { Close as CloseIcon, Delete as DeleteIcon } from "@mui/icons-material";
import { TaskIOTable } from "./TaskIOTable";
import { TaskIO } from "../../types/task";
import { useUIControl } from "../../state/ui-control-store";

export function TaskDisplayWindow(props: { task: ManagedTask, onClose: () => void }) {
    const resizingRef = useRef(false);
    const [addSize, setAddSize] = useState(0);
    const [taskUpdateCounter, setTaskUpdateCounter] = useState(0);
    const uiControl = useUIControl();

    useEffect(() => {
        const updateHandler = () => setTaskUpdateCounter(pv => pv + 1);
        props.task.on("updated", updateHandler);
        return () => { props.task.off("updated", updateHandler); }
    }, [props.task]);

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

    const taskIO: TaskIO = useMemo(() => ({ inputs: props.task.inputs, outputs: props.task.outputs }), [props.task, taskUpdateCounter])

    return (
        <Box position="absolute" top="1rem" right="1rem" width="30%" height={`calc(100% - 2rem + ${addSize}px)`}>
            <NodeOverlayTile header={(
                <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography lineHeight={1} fontSize="0.85rem">{props.task.label}</Typography>
                    <Box flex={1} />
                    <IconButton aria-label="close" size="small" onClick={() => props.onClose()}>
                        <CloseIcon fontSize="inherit" />
                    </IconButton>
                </Stack>
            )}>
                <>
                    <Box marginBottom={2}>
                        <TaskIOTable taskIO={taskIO} onOpen={(tid) => uiControl.selectedTopic = { topicId: tid, topicSpaceId: props.task.taskInstance?.topic_space_id ?? undefined }} allowOpen/>
                    </Box>
                    <Box padding={1}>
                        {!!props.task.taskInstance?.error && <Typography variant="h6" color="red">Error: {props.task.taskInstance?.error}</Typography>}
                    </Box>
                </>
            </NodeOverlayTile>
            <Box position="absolute" bottom={0} left={0} width={"100%"} height="4px" sx={{ cursor: "ns-resize", userSelect: "none" }} onMouseDown={() => resizingRef.current = true} />
        </Box>
    )
}