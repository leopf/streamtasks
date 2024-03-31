import { observer } from "mobx-react-lite";
import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { TaskHost } from "../types/task";
import { useEffect, useMemo, useRef, useState } from "react";
import { taskHostDescriptionFields, taskHostLabelFields } from "../lib/task";
import { renderNodeToImage } from "../lib/node-editor";
import { useGlobalState } from "../state";
import { TaskNode } from "../lib/task-node";
import { TaskHostDragData } from "../types/task-host";
import memoize from "memoizee";

export const TaskTemplateItem = observer((props: { taskHost: TaskHost }) => {
    const [imageUrl, setImageUrl] = useState<string | undefined>(undefined);
    const imageRef = useRef<HTMLImageElement>(null);
    const state = useGlobalState()

    const label = useMemo(() => taskHostLabelFields.map(f => props.taskHost.metadata[f]).find(l => l), [props.taskHost]);
    const description = useMemo(() => taskHostDescriptionFields.map(f => props.taskHost.metadata[f]).find(l => l), [props.taskHost]);
    const nodeName = useMemo(() => props.taskHost.metadata["nodename"], [props.taskHost]);

    useEffect(() => {
        state.taskManager.createManagedTaskInstance(props.taskHost)
            .then(task => renderNodeToImage(new TaskNode(task), { width: 200, backgroundColor: "#0000" }))
            .then(imageUrl => setImageUrl(imageUrl));
    }, []);



    return (
        <Box
            width="100%"
            draggable={true}
            bgcolor="#fff"
            boxShadow="0 0 5px rgba(0,0,0,0.2)"
            border="1px solid #cfcfcf"
            onDragStart={(e) => {
                if (!imageRef.current) return;
                const imageRect = imageRef.current.getBoundingClientRect()
                const dragData: TaskHostDragData = { id: props.taskHost.id, ox: e.clientX - imageRect.x, oy: e.clientY - imageRect.y };
                e.dataTransfer.setData("task_host", JSON.stringify(dragData));
                e.dataTransfer.setDragImage(imageRef.current, dragData.ox, dragData.oy)
            }}>
            <Box borderBottom="1px solid #cfcfcf" paddingX={1} paddingY={0.5}>
                <Typography fontWeight="bold" fontSize="0.7rem">node name: {nodeName}</Typography>
            </Box>
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
            <Stack marginTop={1} spacing={1} padding={1}>
                <Typography variant="subtitle2">description: {description || "This is a task for testing purposes. This is a task for testing purposes."}</Typography>

            </Stack>

        </Box>
    );
});