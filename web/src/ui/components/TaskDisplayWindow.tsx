import { Box, IconButton, Stack, Typography } from "@mui/material";
import { ManagedTask, taskInstance2GeneralStatusMap } from "../../lib/task";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { Close as CloseIcon } from "@mui/icons-material";
import { StatusBadge } from "./StatusBadge";
import { generalStatusColors } from "../../lib/status";
import { useTaskUpdate } from "../lib/task";
import { TaskWindow } from "./TaskWindow";
import { TaskInfoDisplay } from "./TaskInfoDisplay";

export function TaskDisplayWindow(props: { task: ManagedTask, onClose: () => void }) {
    const taskUpdateCounter = useTaskUpdate(props.task, () => 0, true);

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
                    <Box marginBottom={2}>
                        <TaskInfoDisplay task={props.task} updateCounter={taskUpdateCounter} />
                    </Box>
                    <Box padding={1}>
                        {!!props.task.taskInstance?.error && <Typography variant="h6" color={generalStatusColors.error}>Error: {props.task.taskInstance?.error}</Typography>}
                    </Box>
                </>
            </NodeOverlayTile>
        </TaskWindow>
    )
}