import Box from '@mui/material/Box';
import { useState, useRef, useEffect } from 'react';
import { NodeEditorRenderer } from '../lib/node-editor';
import { TaskNode } from '../lib/task-node';
import { observer, useLocalObservable } from "mobx-react-lite";
import { TaskHostDragDataModel } from '../model/task-host';
import { observe, reaction } from 'mobx';
import { TaskEditorWindow } from './components/TaskEditorWindow';
import { useDeployment } from '../state/deployment';
import { useTaskManager } from '../state/task-manager';
import { Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button } from '@mui/material';
import { TaskDisplayWindow } from './components/TaskDisplayWindow';

export const NodeEditor = observer(() => {
    const [nodeRenderer, _] = useState(() => new NodeEditorRenderer());
    const [isDeleting, setDeleting] = useState(false);
    const deployment = useDeployment();
    const taskManager = useTaskManager();

    const state = useLocalObservable(() => ({
        selectedTaskId: undefined as string | undefined,
        get selectedTask() {
            return this.selectedTaskId ? deployment.tasks.get(this.selectedTaskId) : undefined;
        },
    }));
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        nodeRenderer.mount(containerRef.current!);
        const keypressHandler = (e: KeyboardEvent) => {
            if (e.code === "Delete") {
                setDeleting(true);
            }
            if (e.code === "Escape") {
                nodeRenderer.unselectNode();
            }
        };
        const selectTaskHandler = (id: string | undefined) => state.selectedTaskId = id;
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
        const disposers = [
            observe(deployment.tasks, (a) => {
                console.log(a);
                if (a.type === "delete" || a.type === "update") {
                    nodeRenderer.deleteNode(a.oldValue.id);
                }
                if (a.type === "add" || a.type === "update") {
                    nodeRenderer.addNode(new TaskNode(a.newValue));
                }
            }),
            reaction(() => deployment.running, () => nodeRenderer.readOnly = deployment.running, { fireImmediately: true })
        ];
        return () => disposers.forEach(d => d());
    }, [deployment]);

    return (
        <>
            <Box width="100%" height="100%" maxHeight="100%" position="relative">
                <Box
                    width="100%"
                    height="100%"
                    maxHeight="100%"
                    position="absolute"
                    onDragOver={e => e.preventDefault()}
                    onDrop={async e => {
                        try {
                            const taskHostData = TaskHostDragDataModel.parse(JSON.parse(e.dataTransfer.getData("task_host")));
                            const task = await taskManager.createManagedTask(taskHostData.id)
                            const containerOffset = containerRef.current!.getBoundingClientRect();
                            task.frontend_config.position = nodeRenderer.getInternalPosition({ x: e.clientX - containerOffset.x - taskHostData.ox * nodeRenderer.zoom, y: e.clientY - containerOffset.y - taskHostData.oy * nodeRenderer.zoom });
                            await deployment.addTask(task);
                        } catch {}
                    }}
                    sx={{
                        userSelect: "none",
                        "& canvas": {
                            "display": "block"
                        }
                    }}
                    ref={containerRef} />
                {state.selectedTask && (deployment.running ?
                    (<TaskDisplayWindow task={state.selectedTask} onClose={() => nodeRenderer.unselectNode()} />) :
                    (<TaskEditorWindow task={state.selectedTask} onClose={() => nodeRenderer.unselectNode()} onDelete={() => setDeleting(true)} />)
                )}
            </Box>
            <Dialog open={isDeleting && !deployment.running} onClose={() => setDeleting(false)}>
                <DialogTitle>delete task</DialogTitle>
                <DialogContent>
                    <DialogContentText>Do you wish to delete this task?</DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleting(false)} autoFocus>no</Button>
                    <Button onClick={async () => {
                        if (state.selectedTask) {
                            await deployment.deleteTask(state.selectedTask);
                        }
                        setDeleting(false);
                    }}>yes</Button>
                </DialogActions>
            </Dialog>
        </>
    );
});