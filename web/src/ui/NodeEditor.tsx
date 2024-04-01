import Box from '@mui/material/Box';
import { useState, useRef, useEffect } from 'react';
import { NodeEditorRenderer } from '../lib/node-editor';
import { TaskNode } from '../lib/task-node';
import { observer } from "mobx-react-lite";
import { useGlobalState } from '../state';
import { TaskHostDragDataModel } from '../model/task-host';
import { observe } from 'mobx';
import { MovableWindow } from './components/MovableWindow';
import { Typography } from '@mui/material';

export const NodeEditor = observer(() => {
    const [nodeRenderer, _] = useState(() => new NodeEditorRenderer());
    const [ deletingTaskId, setDeletingTaskId ] = useState<string | undefined>(undefined);
    const [ selectedTaskId, setSelectedTaskId ] = useState<string | undefined>(undefined);
    const containerRef = useRef<HTMLDivElement>(null);
    const state = useGlobalState();

    useEffect(() => {
        nodeRenderer.mount(containerRef.current!);
        const keypressHandler = (e: KeyboardEvent) => {
            if (e.code === "Delete") {
                setDeletingTaskId(nodeRenderer.selectedNode?.id);
            }
            if (e.code === "Escape") {
                nodeRenderer.unselectNode();
            }
        };
        const selectTaskHandler = (id: string | undefined) => setSelectedTaskId(id);
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
        <Box width="100%" height="100%" position="relative">
            <Box
                width="100%"
                height="100%"
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
            <MovableWindow xAnchor="right" yAnchor="top" title="Task">
                <Typography variant='h1'>Hello</Typography>
            </MovableWindow>
        </Box>
    );
});