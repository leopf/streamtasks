import { TableContainer, Table, TableBody, TableRow, TableCell, Box, Stack, Typography, Divider, IconButton, TextField, FormControl, Select, MenuItem, InputLabel, Menu } from "@mui/material";
import { observer } from "mobx-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Task, TaskInputStream, TaskOutputStream, TaskStream, TaskStreamBase, streamToString } from "../../lib/task";
import { DeploymentState } from "../../state/deployment";
import { TaskEditorField, TaskNode } from "../../lib/task/node";
import { Delete as DeleteIcon, Wysiwyg as WysiwygIcon } from "@mui/icons-material";
import { TopicDataModal } from "../stateless/TopicDataModal";

const TaskStreamDisplay = (props: { stream: TaskStreamBase, allowOpen: boolean, onOpen: () => void }) => {
    const valueToString = (value: any) => {
        if (typeof value === "boolean") {
            return value ? "yes" : "no";
        }
        return String(value);
    }

    return (
        <Stack direction="column" alignItems="flex-start" paddingY={1}>
            <Stack direction="row" spacing={1} alignItems="center" width="100%">
                <Typography variant="caption" lineHeight={1} flex={1}>{streamToString(props.stream)}</Typography>
                {props.allowOpen && (
                    <IconButton onClick={props.onOpen}>
                        <WysiwygIcon sx={{ width: "15px", height: "15px" }} />
                    </IconButton>
                )}
            </Stack>
            {Object.entries(props.stream.extra ?? {}).map(([key, value], index) => (
                <Typography marginTop={index === 0 ? 0.5 : 0} lineHeight={1} variant="caption" color="GrayText">{key}: {valueToString(value)}</Typography>
            ))}
        </Stack>
    )
};

class EditorValidationHandler {
    private updated: Record<string, number> = {};
    private scheduled: Record<string, number> = {};

    public get isOutdated() {
        return Object.values(this.updated).some(value => value > 0);
    }

    public updateField(field: string) {
        this.updated[field] = (this.updated[field] ?? 0) + 1;
    }
    public schedulePending() {
        const scheduling = { ...this.updated };
        for (const [key, value] of Object.entries(this.scheduled)) {
            scheduling[key] = (scheduling[key] ?? 0) - value;
        }
        this.scheduled = { ...this.updated };
        return scheduling;
    }
    public submitScheduled(scheduled: Record<string, number>) {
        for (const [key, value] of Object.entries(scheduled)) {
            this.updated[key] -= value;
            this.scheduled[key] -= value;
        }
    }
}

const TaskFieldEditor = (props: { taskNode: TaskNode }) => {
    const [fields, setFields] = useState<TaskEditorField[]>([]);
    const [updateCounter, setUpdateCounter] = useState(0);
    const validationHandlerRef = useRef(new EditorValidationHandler());

    useEffect(() => {
        let disposed = false;
        props.taskNode.getEditorFields().then(fields => {
            if (!disposed) {
                setFields(fields);
            }
        });
        return () => {
            disposed = true
        };
    }, [props.taskNode]);

    if (fields.length === 0) {
        return null;
    }

    const refetchFields = async () => {
        const scheduled = validationHandlerRef.current.schedulePending();
        const fields = await props.taskNode.getEditorFields();
        validationHandlerRef.current.submitScheduled(scheduled);
        setFields(fields);
    };

    const renderField = (field: TaskEditorField) => {
        if (field.type === "header") return <Typography variant="subtitle2" sx={{ fontWeight: "600" }}>{field.label}</Typography>;
        if (field.type === "text") {
            return (
                <TextField
                    key={field.config_path}
                    size="small"
                    label={field.label}
                    value={props.taskNode.getConfig(field.config_path, "")}
                    fullWidth
                    error={!field.valid || validationHandlerRef.current.isOutdated}
                    onInput={e => {
                        console.log("changed text");
                        props.taskNode.setConfig(field.config_path, (e.target as HTMLInputElement).value)
                        validationHandlerRef.current.updateField(field.config_path);
                        refetchFields();
                        setUpdateCounter(updateCounter + 1);
                    }} />
            )
        }
        if (field.type === "select") {
            return (
                <FormControl fullWidth key={field.config_path}>
                    <InputLabel id={field.config_path}>{field.label}</InputLabel>
                    <Select
                        size="small"
                        labelId={field.config_path}
                        label={field.label}
                        value={props.taskNode.getConfig(field.config_path, "")}
                        error={!field.valid || validationHandlerRef.current.isOutdated}
                        onChange={e => {
                            console.log("changed select");
                            props.taskNode.setConfig(field.config_path, e.target.value)
                            validationHandlerRef.current.updateField(field.config_path);
                            refetchFields();
                            setUpdateCounter(updateCounter + 1);
                        }}
                    >
                        <MenuItem sx={{ height: 30 }} value={""}></MenuItem>
                        {field.options.map(option => (<MenuItem value={option.value} key={option.value}>{option.label}</MenuItem>))}
                    </Select>
                </FormControl>
            );
        }
        return null;
    };
    return (
        <Stack direction="column" spacing={1.5}>
            {fields.map(renderField)}
        </Stack>
    );
};

export const TaskEditor = observer((props: { taskNode: TaskNode, deployment: DeploymentState, onUnselect: () => void, onDelete: () => void }) => {
    const [openStream, setOpenStream] = useState<TaskStream | undefined>(undefined);
    const [updateCounter, setUpdateCounter] = useState(0);

    const mappedStreams = useMemo(() => {
        const streams: [(TaskInputStream | undefined), (TaskOutputStream | undefined)][] = [];

        for (let i = 0; i < props.taskNode.task.stream_groups.length; i++) {
            const group = props.taskNode.task.stream_groups[i];

            for (let j = 0; j < Math.max(group.inputs.length, group.outputs.length); j++) {
                streams.push([group.inputs.at(j), group.outputs.at(j)]);
            }

            if (i + 1 !== props.taskNode.task.stream_groups.length) {
                streams.push([undefined, undefined]);
            }
        }

        return streams;
    }, [props.taskNode, updateCounter]);

    useEffect(() => {
        const updateCallback = () => setUpdateCounter(updateCounter + 1);
        props.taskNode.onUpdated(updateCallback);
        return () => props.taskNode.offUpdated(updateCallback);
    }, [props.taskNode]);

    return (
        <>
            <TopicDataModal taskName={props.taskNode.getName()} stream={openStream} onClose={() => setOpenStream(undefined)} />
            <Stack direction="column" padding={2}>
                <Stack direction="row" alignItems="center" paddingBottom={1}>
                    <Typography variant="subtitle1" gutterBottom>{props.taskNode.getName()}</Typography>
                    <Box flex={1} />
                    {!props.deployment.readOnly && (
                        <Box>
                            <IconButton onClick={props.onDelete}>
                                <DeleteIcon sx={{ width: "15px", height: "15px" }} />
                            </IconButton>
                        </Box>
                    )}
                </Stack>
                <Divider sx={{ width: "100%" }} />
                <TableContainer>
                    <Table size="small">
                        <TableBody>
                            {mappedStreams.map(([input, output], i) => (
                                <TableRow key={(input?.ref_id ?? "") + (output?.topic_id ?? "")}>
                                    <TableCell padding="none" align="left">{
                                        input ?
                                            <TaskStreamDisplay allowOpen={props.deployment.isStarted} stream={input} onOpen={() => setOpenStream(input)} /> :
                                            <Box height={1} />
                                    }</TableCell>
                                    <TableCell padding="none" align="left">{
                                        output ?
                                            <TaskStreamDisplay allowOpen={props.deployment.isStarted} stream={output} onOpen={() => setOpenStream(output)} /> :
                                            <Box height={1} />
                                    }</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
                <Box height={25} />
                <TaskFieldEditor taskNode={props.taskNode} />
            </Stack>
        </>
    );
});