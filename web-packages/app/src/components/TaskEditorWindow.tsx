import { Box, IconButton, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { Close as CloseIcon, Delete as DeleteIcon } from "@mui/icons-material";
import { TaskInfoDisplay } from "./TaskInfoDisplay";
import { useTaskUpdate } from "../lib/task";
import { TaskWindow } from "./TaskWindow";
import { ManagedTask, TaskModel } from "@streamtasks/core";

export function TaskLabel(props: { label: string, onClick?: () => void }) {
    return <Typography lineHeight={1} fontSize="0.85rem" onClick={props.onClick}>{props.label}</Typography>;
}

export function LabelEditor(props: { task: ManagedTask }) {
    const [isEditing, setEditing] = useState(false);
    const editorClickedRef = useRef(false);

    useEffect(() => {
        const clickOutside = () => {
            if (editorClickedRef.current) {
                editorClickedRef.current = false;
            }
            else {
                setEditing(false);
            }
        }
        window.addEventListener("click", clickOutside);
        return () => window.removeEventListener("click", clickOutside);
    }, []);

    if (!isEditing) {
        return <TaskLabel label={props.task.label} onClick={() => {
            editorClickedRef.current = true;
            setEditing(true);
        }} />;
    }
    else {
        return <TextField fullWidth inputProps={{ style: { fontSize: "0.85rem" } }} value={props.task.label} size="small"
            onInput={e => props.task.label = (e.target as HTMLInputElement).value}
            onClick={() => editorClickedRef.current = true}
            onKeyDown={e => e.key === "Enter" && setEditing(false)} variant="standard" />;
    }
}

export function TaskEditorWindow(props: { task: ManagedTask, onClose: () => void, onDelete: () => void }) {
    const customEditorRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!props.task.hasEditor || !customEditorRef.current) return;

        const taskUpdateHandler = (e: Event) => {
            const newData = TaskModel.parse((e as CustomEvent).detail);
            props.task.updateData(newData);
        };

        customEditorRef.current.addEventListener("task-instance-updated", taskUpdateHandler);
        try {
            props.task.renderEditor(customEditorRef.current);
        } catch (error) {
            console.error(error);
        }

        return () => {
            customEditorRef.current?.removeEventListener("task-instance-updated", taskUpdateHandler)
        }
    }, [props.task, customEditorRef.current]);


    const taskUpdateCounter = useTaskUpdate(props.task, () => {
        if (customEditorRef.current) {
            try {
                props.task.renderEditor(customEditorRef.current);
            } catch (error) {
                console.error(error);
            }
        }
    }, true)

    return (
        <TaskWindow>
            <NodeOverlayTile header={(
                <Stack direction="row" alignItems="center" spacing={1}>
                    <LabelEditor task={props.task} />
                    <Box flex={1} />
                    <IconButton aria-label="close" size="small" onClick={() => props.onDelete()}>
                        <DeleteIcon fontSize="inherit" />
                    </IconButton>
                    <IconButton aria-label="close" size="small" onClick={() => props.onClose()}>
                        <CloseIcon fontSize="inherit" />
                    </IconButton>
                </Stack>
            )}>
                <>
                    <TaskInfoDisplay task={props.task} updateCounter={taskUpdateCounter} />
                    {props.task.hasEditor && <Box padding={1} ref={customEditorRef} />}
                </>
            </NodeOverlayTile>
        </TaskWindow>
    )
}