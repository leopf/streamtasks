import { Box, Checkbox, FormControl, FormControlLabel, InputLabel, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";
import { TaskInstance } from "../types/task";
import { BooleanField, EditorField, NumberField, SelectField } from "./types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function NumberFieldEditor(props: { config: NumberField, task: TaskInstance, onUpdated: () => void }) {
    const [value, setValue] = useState(String(props.task.config[props.config.key]) ?? "")

    const error = useMemo(() => {
        const numValue = Number(value || "z");
        if (Number.isNaN(numValue)) {
            return "You must enter a valid number"
        }

        if (props.config.integer && Math.floor(numValue) !== numValue) {
            return "The entered number must be an integer"
        }

        if (props.config.min && numValue < props.config.min) {
            return `The entered value is below the minimum of ${props.config.min}`;
        }

        if (props.config.max && numValue > props.config.max) {
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

function SelectFieldEditor(props: { config: SelectField, task: TaskInstance, onUpdated: () => void }) {
    return (
        <FormControl fullWidth>
            <InputLabel htmlFor={`select-field-${props.config.key}`}>{props.config.label}</InputLabel>
            <Select
                id={`select-field-${props.config.key}`}
                label={props.config.label}
                value={props.task.config[props.config.key] || undefined}
                size="small"
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

function BooleanFieldEditor(props: { config: BooleanField, task: TaskInstance, onUpdated: () => void }) {
    return (
        <FormControlLabel control={(
            <Checkbox
                size="small"
                checked={!!props.task.config[props.config.key]}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    props.task.config[props.config.key] = e.target.checked;
                    props.onUpdated();
                }} />
        )} label={props.config.label} />
    );
}

export function StaticEditor(props: { task: TaskInstance, fields: EditorField[] }) {
    const rootRef = useRef<HTMLDivElement>(null);

    const onUpdated = useCallback(() => {
        rootRef.current?.dispatchEvent(new CustomEvent("task-instance-updated", { detail: props.task, bubbles: true }))
    }, [props.task, props.fields])

    return (
        <Stack spacing={2} ref={rootRef} paddingY={2}>
            {props.fields.map(field => {
                if (field.type === "number") {
                    return <NumberFieldEditor key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "select") {
                    return <SelectFieldEditor key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "boolean") {
                    return <BooleanFieldEditor key={field.key + props.task.id} task={props.task} config={field} onUpdated={onUpdated} />
                }
            })}
        </Stack>
    );
}