import { Box, Checkbox, FormControl, FormControlLabel, Grid, IconButton, InputLabel, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";
import { BooleanField, EditorField, KVOptionsField, NumberField, SelectField, TextField as STextField } from "./types";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Add as AddIcon, Close as CloseIcon } from "@mui/icons-material";

function TextFieldEditor(props: { config: STextField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [value, setValue] = useState(String(props.data[props.config.key]) ?? "")

    useEffect(() => {
        props.data[props.config.key] = value;
        props.onUpdated();
    }, [value]);

    return (
        <TextField
            size="small"
            fullWidth
            disabled={props.disabled}
            value={value}
            onInput={e => setValue((e.target as HTMLInputElement).value)}
            label={props.config.label} />
    )
}

function NumberFieldEditor(props: { config: NumberField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [value, setValue] = useState(String(props.data[props.config.key]) ?? "")

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
        if (!error && numValue !== props.data[props.config.key]) {
            props.data[props.config.key] = numValue;
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

function SelectFieldEditor(props: { config: SelectField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    return (
        <FormControl fullWidth>
            <InputLabel htmlFor={`select-field-${props.config.key}`}>{props.config.label}</InputLabel>
            <Select
                id={`select-field-${props.config.key}`}
                label={props.config.label}
                value={props.data[props.config.key] || undefined}
                size="small"
                disabled={props.disabled}
                onChange={e => {
                    props.data[props.config.key] = e.target.value;
                    props.onUpdated();
                }}
            >
                {props.config.items.map(item => <MenuItem value={item.value} key={item.value}>{item.label}</MenuItem>)}
            </Select>
        </FormControl>
    );
}

function KVOptionsFieldEditor(props: { config: KVOptionsField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [record, setRecord] = useState<Record<string, string>>(props.data[props.config.key] ?? {})
    const [newItemKey, setNewItemKey] = useState("");
    const [newItemValue, setNewItemValue] = useState("");

    const items = useMemo(() => Object.entries(record).sort((a, b) => a[0].localeCompare(b[0])), [record]);

    useEffect(() => {
        props.data[props.config.key] = record;
        props.onUpdated();
    }, [record])

    return (
        <Stack spacing={0.25}>
            <Typography color="GrayText">{props.config.label}</Typography>
            <Grid container rowSpacing={1}>
                {items.map(item => (
                    <React.Fragment key={item[0]}>
                        <Grid item xs={5}>
                            <TextField fullWidth size="small" value={item[0]} label="key" disabled />
                        </Grid>
                        <Grid item xs={1}>
                            <Stack alignItems="center" justifyContent="center" height="100%">
                                <Typography fontSize="1.2rem">=</Typography>
                            </Stack>
                        </Grid>
                        <Grid item xs={5}>
                            <TextField fullWidth size="small" value={item[1]} label="key" disabled />
                        </Grid>
                        <Grid item xs={1} paddingX={1}>
                            <IconButton onClick={() => setRecord(pv => Object.fromEntries(Object.entries(pv).filter(e => e[0] !== item[0])))}>
                                <CloseIcon />
                            </IconButton>
                        </Grid>
                    </React.Fragment>
                ))}
                <Grid item xs={5}>
                    <TextField fullWidth size="small" value={newItemKey} label="key" onInput={e => setNewItemKey((e.target as HTMLInputElement).value)} />
                </Grid>
                <Grid item xs={1}>
                    <Stack alignItems="center" justifyContent="center" height="100%">
                        <Typography fontSize="1.2rem">=</Typography>
                    </Stack>
                </Grid>
                <Grid item xs={5}>
                    <TextField fullWidth size="small" value={newItemValue} label="key" onInput={e => setNewItemValue((e.target as HTMLInputElement).value)} />
                </Grid>
                <Grid item xs={1} paddingX={1}>
                    <IconButton onClick={() => {
                        setRecord(pv => ({ ...pv, [newItemKey]: newItemValue }));
                        setNewItemKey("");
                        setNewItemValue("");
                    }}>
                        <AddIcon />
                    </IconButton>
                </Grid>
            </Grid>
        </Stack>
    );
}

function BooleanFieldEditor(props: { config: BooleanField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    return (
        <FormControlLabel control={(
            <Checkbox
                size="small"
                disabled={props.disabled}
                checked={!!props.data[props.config.key]}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    props.data[props.config.key] = e.target.checked;
                    props.onUpdated();
                }} />
        )} label={props.config.label} />
    );
}

export function StaticEditor(props: { data: Record<string, any>, fields: EditorField[], onUpdated: () => void, disabledFields?: Set<string> }) {
    const disabledFields = props.disabledFields ?? new Set();
    const onUpdated = useCallback(() => props.onUpdated(), [props.fields, props.onUpdated]);

    return (
        <Stack spacing={2} paddingY={2}>
            {props.fields.map(field => {
                if (field.type === "number") {
                    return <NumberFieldEditor disabled={disabledFields.has(field.key)} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "select") {
                    return <SelectFieldEditor disabled={disabledFields.has(field.key)} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "boolean") {
                    return <BooleanFieldEditor disabled={disabledFields.has(field.key)} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "text") {
                    return <TextFieldEditor disabled={disabledFields.has(field.key)} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "kvoptions") {
                    return <KVOptionsFieldEditor disabled={disabledFields.has(field.key)} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
            })}
        </Stack>
    );
}