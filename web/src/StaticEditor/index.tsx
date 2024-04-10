import { Box, Checkbox, FormControl, FormControlLabel, InputLabel, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";
import { Task } from "../types/task";
import { BooleanField, EditorField, NumberField, SelectField, TextField as STextField } from "./types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function TextFieldEditor(props: { config: STextField, task: Task, onUpdated: () => void, disabled?: boolean }) {
    const [value, setValue] = useState(String(props.task.config[props.config.key]) ?? "")

    useEffect(() => {
        props.task.config[props.config.key] = value;
        props.onUpdated();
    }, [value]);

    return (
        <TextField
            size="small"
            fullWidth
            disabled={props.disabled}
            value={value}
            onInput={e => setValue((e.target as HTMLInputElement).value)}
            label={props.config.label}/>
    )
}

function NumberFieldEditor(props: { config: NumberField, task: Task, onUpdated: () => void, disabled?: boolean }) {
    const [value, setValue] = useState(String(props.task.config[props.config.key]) ?? "")

    const error = useMemo(() => {
        const numValue = Number(value || "z");
        if (Number.isNaN(numValue)) {
            return "You must enter a valid number"
        }

        if (props.config.integer && Math.floor(numValue) !== numValue) {
            return "The entered number must be an integer"
        }

        if (props.config.min !== undefined && numValue < props.config.min) {
            return `The entered value is below the minimum of ${props.config.min}`;
        }

        if (props.config.max !== undefined && numValue > props.config.max) {
            return `The entered value is above the maximum of ${props.config.max}`;
        }
    }, [value]);

    useEffect(() => {
        const numValue = Number(value);
        if (!error && numValue !== props.task.config[props.config.key]) {
            props.task.config[props.config.key] = numValue;
            props.onUpdated();
        }
    }, [value, !!error]);

    return (
        <Box position="relative">
            <TextField
                size="small"
                fullWidth
                disabled={props.disabled}
                value={value}
                onInput={e => setValue((e.target as HTMLInputElement).value)}
                label={props.config.label}
                helperText={error}
                error={!!error} />
            {!!props.config.unit && (
                <Typography position="absolute" display="block" right="1rem" top="50%" sx={{ transform: "translate(0, -50%)" }}>{props.config.unit}</Typography>
            )}
        </Box>
    )
}

function SelectFieldEditor(props: { config: SelectField, task: Task, onUpdated: () => void, disabled?: boolean }) {
    return (
        <FormControl fullWidth>
            <InputLabel htmlFor={`select-field-${props.config.key}`}>{props.config.label}</InputLabel>
            <Select
                id={`select-field-${props.config.key}`}
                label={props.config.label}
                value={props.task.config[props.config.key] || undefined}
                size="small"
                disabled={props.disabled}
                onChange={e => {
                    props.task.config[props.config.key] = e.target.value;
                    props.onUpdated();
                }}
            >
                {props.config.items.map(item => <MenuItem value={item.value} key={item.value}>{item.label}</MenuItem>)}
            </Select>
        </FormControl>
    );
}

function BooleanFieldEditor(props: { config: BooleanField, task: Task, onUpdated: () => void, disabled?: boolean }) {
    return (
        <FormControlLabel control={(
            <Checkbox
                size="small"
                disabled={props.disabled}
                checked={!!props.task.config[props.config.key]}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    props.task.config[props.config.key] = e.target.checked;
                    props.onUpdated();
                }} />
        )} label={props.config.label} />
    );
}

export function StaticEditor(props: { task: Task, fields: EditorField[], beforeUpdate?: () => void, disabledFields?: Set<string> }) {
    const disabledFields = props.disabledFields ?? new Set();
    const rootRef = useRef<HTMLDivElement>(null);

    const onUpdated = useCallback(() => {
        props.beforeUpdate?.call(null);
        rootRef.current?.dispatchEvent(new CustomEvent("task-instance-updated", { detail: props.task, bubbles: true }))
    }, [props.task, props.fields, props.beforeUpdate])

    return (
        <Stack spacing={2} ref={rootRef} paddingY={2}>
            {props.fields.map(field => {
                if (field.type === "number") {
                    return <NumberFieldEditor disabled={disabledFields.has(field.key)} key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "select") {
                    return <SelectFieldEditor disabled={disabledFields.has(field.key)} key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "boolean") {
                    return <BooleanFieldEditor disabled={disabledFields.has(field.key)} key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "text") {
                    return <TextFieldEditor disabled={disabledFields.has(field.key)} key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
            })}
        </Stack>
    );
}