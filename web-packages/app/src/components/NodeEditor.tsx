import Box from '@mui/material/Box';
import { useState, useRef, useEffect, useMemo } from 'react';
import { TaskNode } from '../lib/task-node';
import { observer, useLocalObservable } from "mobx-react-lite";
import { observe, reaction } from 'mobx';
import { TaskEditorWindow } from './TaskEditorWindow';
import { Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button, Snackbar } from '@mui/material';
import { TaskDisplayWindow } from './TaskDisplayWindow';
import { ConnectFailureInfo, NodeEditorRenderer } from '../lib/node-editor';
import { ManagedTask, TaskInput, TaskOutput, getObjectDiffPaths, TaskHostDragDataModel, compareIOIgnorePaths } from '@streamtasks/core';
import { ioFieldNameToLabel } from '../lib/task';
import { useDeployment } from '../state/deployment-manager';
import { useRootStore } from '../state/root-store';

type TaskConnectFailureInfo = {
    errorText?: string
    input: {
        task: ManagedTask,
        input: TaskInput
    },
    output?: {
        task: ManagedTask,
        output: TaskOutput
    },
};

export const NodeEditor = observer(() => {
    const [nodeRenderer, _] = useState(() => new NodeEditorRenderer());
    const [isDeleting, setDeleting] = useState(false);
    const [connectFailureInfo, setConnectFailureInfo] = useState<TaskConnectFailureInfo | undefined>(undefined);
    const deployment = useDeployment();
    const rootStore = useRootStore();

    const state = useLocalObservable(() => ({
        selectedTaskId: undefined as string | undefined,
        get selectedTask() {
            return this.selectedTaskId ? deployment.tasks.get(this.selectedTaskId) : undefined;
        },
    }));
    const containerRef = useRef<HTMLDivElement>(null);
    const connectFailureMismatchedFields = useMemo(() => {
        if (connectFailureInfo) {
            return getObjectDiffPaths(connectFailureInfo.input.input, connectFailureInfo.output?.output ?? {}, compareIOIgnorePaths);
        }
        return [];
    }, [connectFailureInfo]);

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
        const onSelectedTask = (id: string | undefined) => state.selectedTaskId = id;
        const onConnectFailure = (data: ConnectFailureInfo) => {
            const inputTask = deployment.tasks.get(data.input.nodeId);
            const outputTask = data.output?.nodeId ? deployment.tasks.get(data.output.nodeId) : undefined;
            if (inputTask) {
                setConnectFailureInfo({
                    errorText: data.errorText,
                    input: {
                        task: inputTask,
                        input: inputTask.inputs.find(input => input.key === data.input.key)!
                    },
                    output: outputTask && data.output && {
                        task: outputTask,
                        output: outputTask.outputs.find(output => output.topic_id === data.output!.id)!
                    }
                });
            }
        }

        window.addEventListener("keydown", keypressHandler)
        nodeRenderer.on("selected", onSelectedTask)
        nodeRenderer.on("connect-failure", onConnectFailure)

        return () => {
            window.removeEventListener("keydown", keypressHandler);
            nodeRenderer.off("selected", onSelectedTask);
            nodeRenderer.off("connect-failure", onConnectFailure);
            nodeRenderer.destroy();
        }
    }, [])

    useEffect(() => {
        nodeRenderer.clear();
        const centerTimeoutHdl = setTimeout(() => nodeRenderer.viewport.panToCenter(), 500);
        const disposers = [
            observe(deployment.tasks, (a) => {
                if (a.type === "delete" || a.type === "update") {
                    nodeRenderer.deleteNode(a.oldValue.id);
                }
                if (a.type === "add" || a.type === "update") {
                    nodeRenderer.addNode(new TaskNode(a.newValue));
                }
            }),
            reaction(() => deployment.running, () => nodeRenderer.readOnly = deployment.running, { fireImmediately: true }),
            () => clearTimeout(centerTimeoutHdl)
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
                            const task = await rootStore.taskManager.createManagedTask(taskHostData.id)
                            const containerOffset = containerRef.current!.getBoundingClientRect();
                            task.frontend_config.position = nodeRenderer.getLocalPosition({ x: e.clientX - containerOffset.x - taskHostData.ox * nodeRenderer.zoom, y: e.clientY - containerOffset.y - taskHostData.oy * nodeRenderer.zoom });
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
            <Snackbar
                open={!!connectFailureInfo}
                autoHideDuration={6000}
                onClose={() => setConnectFailureInfo(undefined)}
                message={`Failed to connect! Mismatch on the fields ${connectFailureMismatchedFields.map(k => `"${ioFieldNameToLabel(k)}"`).join(", ")}.${connectFailureInfo?.errorText ? ` Error: ${connectFailureInfo.errorText}` : ""}`}
                action={(<Button color="secondary" size="small" onClick={() => setConnectFailureInfo(undefined)}>close</Button>)}
                />
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