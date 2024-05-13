import { observer } from "mobx-react-lite";
import { Box, Stack, Typography } from "@mui/material";
import { useEffect, useRef } from "react";
import { TaskNode } from "../lib/task-node";
import { ParsedTaskHost, TaskHostDragData } from "../../types/task-host";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { useRootStore } from "../../state/root-store";
import { renderNodeToElement } from "../lib/node-editor";

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
            <NodeOverlayTile header={<Typography lineHeight={1} fontSize="0.7rem">node: {props.taskHost.nodeName ?? "-"}</Typography>}>
                <Stack padding={3} direction="column" alignItems="center">
                    <Box ref={containerRef} />
                </Stack>
                {props.taskHost.description && (
                    <Box padding={1}>
                        <Typography variant="caption">{props.taskHost.description}</Typography>
                    </Box>
                )}
            </NodeOverlayTile>
        </Box>
    );
});