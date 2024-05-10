import { useMemo } from "react";
import { ManagedTask } from "../../lib/task";
import { TaskIO } from "../../types/task";
import { Box } from "@mui/material";
import { TaskIOTable } from "./TaskIOTable";
import { useRootStore } from "../../state/root-store";

export function TaskInfoDisplay(props: { task: ManagedTask, updateCounter: number }) {
    const taskIO: TaskIO = useMemo(() => ({ inputs: props.task.inputs, outputs: props.task.outputs }), [props.task, props.updateCounter])
    const rootStore = useRootStore();

    const allowOpen = !!props.task.taskInstance;

    return (
        <Box marginBottom={2}>
            <TaskIOTable
                taskIO={taskIO}
                onOpen={(tid) => rootStore.uiControl.selectedTopic = { topicId: tid, topicSpaceId: props.task.taskInstance?.topic_space_id ?? undefined }}
                allowOpen={allowOpen} />
        </Box>
    );
}