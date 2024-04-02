import { observer } from "mobx-react-lite";
import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { TaskHost } from "../../types/task";
import { useEffect, useMemo, useRef, useState } from "react";
import { taskHostDescriptionFields, taskHostLabelFields } from "../../lib/task";
import { renderNodeToImage } from "../../lib/node-editor";
import { useGlobalState } from "../../state";
import { TaskNode } from "../../lib/task-node";
import { TaskHostDragData } from "../../types/task-host";
import { LRUCache } from "lru-cache";
import { NodeOverlayTile } from "./NodeOverlayTile";

const taskHostImageCache = new LRUCache<string, string>({
    maxSize: 1e7,
    sizeCalculation: (a, b) => b.length
});

export const TaskTemplateItem = observer((props: { taskHost: TaskHost }) => {
    const [imageUrl, setImageUrl] = useState<string | undefined>(undefined);
    const imageRef = useRef<HTMLImageElement>(null);
    const state = useGlobalState()

    const label = useMemo(() => taskHostLabelFields.map(f => props.taskHost.metadata[f]).find(l => l), [props.taskHost]);
    const description = useMemo(() => taskHostDescriptionFields.map(f => props.taskHost.metadata[f]).find(l => l), [props.taskHost]);
    const nodeName = useMemo(() => props.taskHost.metadata["nodename"], [props.taskHost]);

    useEffect(() => {
        if (taskHostImageCache.has(props.taskHost.id)) {
            setImageUrl(taskHostImageCache.get(props.taskHost.id));
        }
        else {
            state.taskManager.createManagedTaskInstance(props.taskHost)
                .then(task => renderNodeToImage(new TaskNode(task), { width: 200, backgroundColor: "#0000" }))
                .then(imageUrl => {
                    taskHostImageCache.set(props.taskHost.id, imageUrl)
                    setImageUrl(imageUrl);
                });
        }
    }, []);

    return (
        <Box width="100%" draggable={true} onDragStart={(e) => {
            if (!imageRef.current) return;
            const imageRect = imageRef.current.getBoundingClientRect()
            const dragData: TaskHostDragData = { id: props.taskHost.id, ox: e.clientX - imageRect.x, oy: e.clientY - imageRect.y };
            e.dataTransfer.setData("task_host", JSON.stringify(dragData));
            e.dataTransfer.setDragImage(imageRef.current, dragData.ox, dragData.oy)
        }}>
            <NodeOverlayTile header={<Typography lineHeight={1} fontSize="0.7rem">node: {nodeName}</Typography>}>
                {imageUrl ? (
                    <Box padding={3}>
                        <img ref={imageRef} style={{ width: "100%", display: "block" }} src={imageUrl} />
                    </Box>
                ) : (
                    <Stack alignItems="center" spacing={2}>
                        <CircularProgress />
                        <Typography>{label}</Typography>
                    </Stack>
                )}
                {description && (
                    <Box padding={1}>
                        <Typography variant="caption">{description}</Typography>
                    </Box>
                )}
            </NodeOverlayTile>
        </Box>
    );
});