import { Box, IconButton, Stack, Typography } from "@mui/material";
import { ManagedTask } from "../../lib/task";
import { useEffect, useMemo, useRef, useState } from "react";
import { TaskModel } from "../../model/task";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { Close as CloseIcon, Delete as DeleteIcon } from "@mui/icons-material";
import { TaskIOTable } from "./TaskIOTable";
import { TaskIO } from "../../types/task";

export function TaskEditorWindow(props: { task: ManagedTask, onClose: () => void, onDelete: () => void }) {
    const resizingRef = useRef(false);
    const customEditorRef = useRef<HTMLDivElement>(null);
    const [addSize, setAddSize] = useState(0);
    const [taskUpdateCounter, setTaskUpdateCounter] = useState(0);

    useEffect(() => {
        if (!props.task.hasEditor || !customEditorRef.current) return;

        const taskUpdateHandler = (e: Event) => {
            const newData = TaskModel.parse((e as CustomEvent).detail);
            props.task.updateData(newData);
        };

        customEditorRef.current.addEventListener("task-instance-updated", taskUpdateHandler);
        try {
            props.task.renderEditor(customEditorRef.current);
        } catch (error) {
            console.error(error);
        }

        return () => {
            customEditorRef.current?.removeEventListener("task-instance-updated", taskUpdateHandler)
        }
    }, [props.task, customEditorRef.current]);

    useEffect(() => {
        const updateHandler = () => {
            setTaskUpdateCounter(pv => pv + 1);
            if (customEditorRef.current) {
                try {
                    props.task.renderEditor(customEditorRef.current);
                } catch (error) {
                    console.error(error);
                }
            }
        }
        props.task.on("updated", updateHandler);
        return () => {
            props.task.off("updated", updateHandler);
        }
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
                    <IconButton aria-label="close" size="small" onClick={() => props.onDelete()}>
                        <DeleteIcon fontSize="inherit" />
                    </IconButton>
                    <IconButton aria-label="close" size="small" onClick={() => props.onClose()}>
                        <CloseIcon fontSize="inherit" />
                    </IconButton>
                </Stack>
            )}>
                <>
                    <Box marginBottom={2}><TaskIOTable taskIO={taskIO}/></Box>
                    {props.task.hasEditor && <Box padding={1} ref={customEditorRef} />}
                </>
            </NodeOverlayTile>
            <Box position="absolute" bottom={0} left={0} width={"100%"} height="4px" sx={{ cursor: "ns-resize", userSelect: "none" }} onMouseDown={() => resizingRef.current = true} />
        </Box>
    )
}