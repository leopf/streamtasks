import { useMemo } from "react";
import { ManagedTask } from "../../lib/task";
import { TaskIO } from "../../types/task";
import { Box, Typography } from "@mui/material";
import { TaskIOTable } from "./TaskIOTable";
import { useRootStore } from "../../state/root-store";
import { generalStatusColors } from "../../lib/status";

export function TaskInfoDisplay(props: { task: ManagedTask, updateCounter: number }) {
    const taskIO: TaskIO = useMemo(() => ({ inputs: props.task.inputs, outputs: props.task.outputs }), [props.task, props.updateCounter])
    const rootStore = useRootStore();

    const allowOpen = !!props.task.taskInstance;

    return (
        <>
            <Box marginBottom={2}>
                <TaskIOTable
                    taskIO={taskIO}
                    onOpen={(tid) => rootStore.uiControl.selectedTopic = { topicId: tid, topicSpaceId: props.task.taskInstance?.topic_space_id ?? undefined }}
                    allowOpen={allowOpen} />
            </Box>
            <Box padding={1}>
                {!!props.task.taskInstance?.error && <Typography variant="h6" color={generalStatusColors.error}>Error: {props.task.taskInstance?.error}</Typography>}
            </Box>
        </>
    );
}