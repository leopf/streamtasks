import { Box, IconButton, Stack, Typography } from "@mui/material";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { Close as CloseIcon } from "@mui/icons-material";
import { StatusBadge } from "./StatusBadge";
import { taskInstance2GeneralStatusMap, useTaskUpdate } from "../lib/task";
import { TaskWindow } from "./TaskWindow";
import { TaskInfoDisplay } from "./TaskInfoDisplay";
import { useEffect, useRef } from "react";
import { ManagedTask } from "@streamtasks/core";

export function TaskDisplayWindow(props: { task: ManagedTask, onClose: () => void }) {
    const customDisplayRef = useRef<HTMLDivElement>(null);
    const taskUpdateCounter = useTaskUpdate(props.task, () => {
        if (customDisplayRef.current) {
            props.task.renderDisplay(customDisplayRef.current, { context: "task" });
        }
    }, true);

    useEffect(() => {
        if (!props.task.hasDisplay || !customDisplayRef.current) return;
        customDisplayRef.current.innerHTML = "";
        props.task.renderDisplay(customDisplayRef.current, { context: "task" });
    }, [props.task, customDisplayRef.current]);

    return (
        <TaskWindow>
            <NodeOverlayTile header={(
                <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography lineHeight={1} fontSize="0.85rem">{props.task.label}</Typography>
                    <Box flex={1} />
                    <StatusBadge status={taskInstance2GeneralStatusMap[props.task.taskInstance?.status ?? "failed"]} text={props.task.taskInstance?.status ?? "unknown"} />
                    <IconButton aria-label="close" size="small" onClick={() => props.onClose()}>
                        <CloseIcon fontSize="inherit" />
                    </IconButton>
                </Stack>
            )}>
                <>
                    <TaskInfoDisplay task={props.task} updateCounter={taskUpdateCounter} />
                    {props.task.hasDisplay && <Box flex={1} padding={1} ref={customDisplayRef} />}
                </>
            </NodeOverlayTile>
        </TaskWindow>
    )
}