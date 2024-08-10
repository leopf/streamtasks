import { observer } from "mobx-react-lite";
import { Box, Stack, Typography } from "@mui/material";
import { useEffect, useRef } from "react";
import { TaskNode } from "../lib/task-node";
import { renderNodeToElement } from "../lib/node-editor";
import { ParsedTaskHost, TaskHostDragData } from "@streamtasks/core";
import { useRootStore } from "../state/root-store";

export const TaskTemplateItem = observer((props: { taskHost: ParsedTaskHost }) => {
    const containerRef = useRef<HTMLImageElement>(null);
    const rootStore = useRootStore()

    useEffect(() => {
        rootStore.taskManager.createManagedTask(props.taskHost.id).then(task => {
            const element = renderNodeToElement(new TaskNode(task));
            containerRef.current?.appendChild(element);
        });
    }, []);

    return (
        <Box width="100%" draggable={true} onDragStart={(e) => {
            if (!containerRef.current) return;
            const nodeRect = containerRef.current.getBoundingClientRect()
            const dragData: TaskHostDragData = { id: props.taskHost.id, ox: e.clientX - nodeRect.x, oy: e.clientY - nodeRect.y };
            e.dataTransfer.setData("task_host", JSON.stringify(dragData));
            e.dataTransfer.setDragImage(containerRef.current, dragData.ox, dragData.oy);
        }}>
            <Stack paddingX={3} direction="column" alignItems="center">
                <Box ref={containerRef} />
            </Stack>
        </Box>
    );
});