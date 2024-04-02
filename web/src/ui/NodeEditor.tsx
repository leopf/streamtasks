import Box from '@mui/material/Box';
import { useState, useRef, useEffect } from 'react';
import { NodeEditorRenderer } from '../lib/node-editor';
import { TaskNode } from '../lib/task-node';
import { observer, useLocalObservable } from "mobx-react-lite";
import { useGlobalState } from '../state';
import { TaskHostDragDataModel } from '../model/task-host';
import { observe } from 'mobx';
import { IconButton, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import { NodeOverlayTile } from './components/NodeOverlayTile';
import { Close as CloseIcon } from '@mui/icons-material';
import { Metadata } from '../types/task';
import { TaskIOLabel } from './components/TaskIOLabel';
import { TaskEditorWindow } from './components/TaskEditorWindow';

export const NodeEditor = observer(() => {
    const [nodeRenderer, _] = useState(() => new NodeEditorRenderer());
    const state = useGlobalState();
    const localState = useLocalObservable(() => ({
        deletingTaskId: undefined as string | undefined,
        selectedTaskId: undefined as string | undefined,
        get deletingTask() {
            return this.deletingTaskId ? state.deployment?.tasks.get(this.deletingTaskId) : undefined;
        },
        get selectedTask() {
            return this.selectedTaskId ? state.deployment?.tasks.get(this.selectedTaskId) : undefined;
        },
    }));
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        nodeRenderer.mount(containerRef.current!);
        const keypressHandler = (e: KeyboardEvent) => {
            if (e.code === "Delete") {
                localState.deletingTaskId = nodeRenderer.selectedNode?.id;
            }
            if (e.code === "Escape") {
                nodeRenderer.unselectNode();
            }
        };
        const selectTaskHandler = (id: string | undefined) => localState.selectedTaskId = id;
        window.addEventListener("keydown", keypressHandler)
        nodeRenderer.on("selected", selectTaskHandler)

        return () => {
            window.removeEventListener("keydown", keypressHandler);
            nodeRenderer.off("selected", selectTaskHandler);
            nodeRenderer.destroy();
        }
    }, [])

    useEffect(() => {
        nodeRenderer.clear();
        if (!state.deployment) return;
        return observe(state.deployment.tasks, (a) => {
            console.log(a);
            if (a.type === "delete" || a.type === "update") {
                nodeRenderer.deleteNode(a.oldValue.id);
            }
            if (a.type === "add" || a.type === "update") {
                nodeRenderer.addNode(new TaskNode(a.newValue));
            }
        })
    }, [state.deployment]);

    return (
        <Box width="100%" height="100%" maxHeight="100%" position="relative">
            <Box
                width="100%"
                height="100%"
                maxHeight="100%"
                position="absolute"
                onDragOver={e => e.preventDefault()}
                onDrop={async e => {
                    if (!state.deployment) return;
                    const taskHostData = TaskHostDragDataModel.parse(JSON.parse(e.dataTransfer.getData("task_host")));
                    const task = await state.taskManager.createManagedTaskInstance(taskHostData.id)
                    const containerOffset = containerRef.current!.getBoundingClientRect();
                    task.frontendConfig.position = nodeRenderer.getInternalPosition({ x: e.clientX - containerOffset.x - taskHostData.ox * nodeRenderer.zoom, y: e.clientY - containerOffset.y - taskHostData.oy * nodeRenderer.zoom });
                    await state.deployment.addTask(task);
                }}
                sx={{
                    "& canvas": {
                        "display": "block"
                    }
                }}
                ref={containerRef} />
            {localState.selectedTask && (<TaskEditorWindow task={localState.selectedTask} onClose={() => nodeRenderer.unselectNode()}/>)}
        </Box>
    );
});