import { observer } from "mobx-react-lite";
import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { TaskHost } from "../../types/task";
import { useEffect, useMemo, useRef, useState } from "react";
import { taskHostDescriptionFields, taskHostLabelFields } from "../../lib/task";
import { TaskNode } from "../../lib/task-node";
import { TaskHostDragData } from "../../types/task-host";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { useRootStore } from "../../state/root-store";
import { renderNodeToElement } from "../lib/node-editor";

export const TaskTemplateItem = observer((props: { taskHost: TaskHost }) => {
    const containerRef = useRef<HTMLImageElement>(null);
    const rootStore = useRootStore()

    const label = useMemo(() => taskHostLabelFields.map(f => props.taskHost.metadata[f]).find(l => l), [props.taskHost]);
    const description = useMemo(() => taskHostDescriptionFields.map(f => props.taskHost.metadata[f]).find(l => l), [props.taskHost]);
    const nodeName = useMemo(() => props.taskHost.metadata["nodename"], [props.taskHost]);

    useEffect(() => {
        rootStore.taskManager.createManagedTask(props.taskHost)
            .then(task => {
                const element = renderNodeToElement(new TaskNode(task));
                containerRef.current?.appendChild(element);
            })
    }, []);

    return (
        <Box width="100%" draggable={true} onDragStart={(e) => {
            if (!containerRef.current) return;
            const nodeRect = containerRef.current.getBoundingClientRect()
            const dragData: TaskHostDragData = { id: props.taskHost.id, ox: e.clientX - nodeRect.x, oy: e.clientY - nodeRect.y };
            e.dataTransfer.setData("task_host", JSON.stringify(dragData));
        }}>
            <NodeOverlayTile header={<Typography lineHeight={1} fontSize="0.7rem">node: {nodeName}</Typography>}>
                <Box padding={3}>
                    <Box ref={containerRef} />
                </Box>
                {description && (
                    <Box padding={1}>
                        <Typography variant="caption">{description}</Typography>
                    </Box>
                )}
            </NodeOverlayTile>
        </Box>
    );
});