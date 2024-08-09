import { Box, Checkbox, FormControl, FormControlLabel, Grid, IconButton, InputLabel, MenuItem, Select, Slider, SliderValueLabelProps, Stack, TextField, Tooltip, Typography } from "@mui/material";
import { BooleanField, DynamicSelectField, EditorField, KVOptionsField, MultiselectField, NumberField, SelectField, SelectItem, SelectItemModel, SliderField, TextField as STextField } from "./types";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Add as AddIcon, Close as CloseIcon } from "@mui/icons-material";
import { z } from "zod";
import { useStaticEditorConfig } from "./config";

function TextFieldEditor(props: { config: STextField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [value, setValue] = useState(String(props.data[props.config.key]) ?? "")

    useEffect(() => {
        if (props.data[props.config.key] != value) {
            props.data[props.config.key] = value;
            props.onUpdated();
        }
    }, [value]);

    return (
        <TextField
            size="small"
            fullWidth
            variant="filled"
            multiline={props.config.multiline}
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
                variant="filled"
                value={value}
                onInput={e => setValue((e.target as HTMLInputElement).value)}
                label={props.config.label}
                helperText={error}
                error={!!error} />
            {!!props.config.unit && (
                <Typography position="absolute" color={theme => theme.palette.text.primary} display="block" right="1rem" top="50%" sx={{ transform: "translate(0, -50%)" }}>{props.config.unit}</Typography>
            )}
        </Box>
    )
}

function SliderFieldEditor(props: { config: SliderField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [value, setValue] = useState(Number(props.data[props.config.key]) ?? "")

    useEffect(() => {
        const numValue = Number(value);
        if (numValue !== props.data[props.config.key]) {
            props.data[props.config.key] = numValue;
            props.onUpdated();
        }
    }, [value]);

    const sliderMax = Math.pow(props.config.max, props.config.pow);
    const sliderMin = Math.pow(props.config.min, props.config.pow);
    const sliderStep = (sliderMax - sliderMin) / 1000;

    const _SliderFieldEditorVLD = (vldprops: SliderValueLabelProps) => {
        const { children, value } = vldprops;

        const displayValue = Math.round(Math.pow(value, props.config.pow) * 10000) / 10000;

        return (
            <Tooltip enterTouchDelay={0} placement="top" title={displayValue}>
                {children}
            </Tooltip>
        );
    }

    return (
        <Box>
            <Typography color={theme => theme.palette.text.primary} fontSize="0.8rem">{props.config.label} ({Math.round(value * 10000) / 10000})</Typography>
            <Slider
                disabled={props.disabled}
                valueLabelDisplay="auto"
                slots={{
                    valueLabel: _SliderFieldEditorVLD
                }}
                size="small"
                onChange={(_, v) => setValue(Math.pow(Number(v), props.config.pow))}
                value={Math.pow(value, 1 / props.config.pow)}
                step={sliderStep}
                min={sliderMin}
                max={sliderMax}
            />
        </Box>
    )
}

function SelectFieldEditor(props: { config: SelectField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    return (
        <FormControl fullWidth variant="filled">
            <InputLabel htmlFor={`select-field-${props.config.key}`}>{props.config.label}</InputLabel>
            <Select
                id={`select-field-${props.config.key}`}
                label={props.config.label}
                value={props.data[props.config.key] ?? undefined}
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

const dynamicSelectItemCache = new Map<string, SelectItem[]>();

function DynamicSelectFieldEditor(props: { config: DynamicSelectField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [items, setItems] = useState<SelectItem[]>([]);
    const editorConfig = useStaticEditorConfig();
    const url = String(new URL(props.config.path, editorConfig.baseUrl));

    const loadItems = async (controller: AbortController) => {
        const items = await fetch(url, { signal: controller.signal })
            .then(res => res.json())
            .then(res => z.array(SelectItemModel).parse(res));

        if (controller.signal.aborted) return;
        dynamicSelectItemCache.set(url, items);
        setItems(items);
    };

    useEffect(() => {
        const cachedItems = dynamicSelectItemCache.get(url);
        if (cachedItems) {
            setItems(cachedItems);
        }
        else {
            const controller = new AbortController();
            loadItems(controller);
            return () => controller.abort();
        }
    }, [url]);
    
    return (
        <FormControl fullWidth variant="filled">
            <InputLabel htmlFor={`select-field-${props.config.key}`}>{props.config.label}</InputLabel>
            <Select
                id={`select-field-${props.config.key}`}
                label={props.config.label}
                value={props.data[props.config.key] ?? undefined}
                size="small"
                disabled={props.disabled}
                onOpen={() => loadItems(new AbortController())}
                onChange={e => {
                    props.data[props.config.key] = e.target.value;
                    props.onUpdated();
                }}
            >
                {items.map(item => <MenuItem value={item.value} key={item.value}>{item.label}</MenuItem>)}
            </Select>
        </FormControl>
    );
}

function MultiselectFieldEditor(props: { config: MultiselectField, data: Record<string, any>, onUpdated: () => void, disabledFields?: Set<string>, disableAll: boolean }) {
    const keys = Object.keys(props.config.items[0]);

    const keyItems = useMemo(() => {
        return Object.fromEntries(keys.map(key => [key, Array.from(new Set(props.config.items.map(item => item[key])))]))
    }, [props.config]);

    const updateOthers = (key: string) => {
        const value = props.data[key];
        let remainingItems = props.config.items.filter(item => item[key] === value);
        const others = keys.map(okey => [okey, remainingItems.filter(item => item[okey] === props.data[okey]).length] as [string, number]).sort((a, b) => b[1] - a[1]).map(v => v[0]);
        for (const otherKey of others) {
            const nrem = remainingItems.filter(item => item[otherKey] === props.data[otherKey]);
            if (nrem.length === 0) {
                remainingItems = [remainingItems[0]];
                props.data[otherKey] = remainingItems[0][otherKey];
            }
            else {
                remainingItems = nrem;
            }
        }
    }

    return keys.map(key => (
        <FormControl key={key} fullWidth variant="filled">
            <InputLabel htmlFor={`select-field-${key}`} sx={{ textTransform: "capitalize" }}>{key}</InputLabel>
            <Select
                id={`select-field-${key}`}
                value={props.data[key] ?? undefined}
                size="small"
                onChange={e => {
                    props.data[key] = e.target.value;
                    updateOthers(key);
                    props.onUpdated();
                }}
            >
                {keyItems[key].map(item => <MenuItem value={item} key={String(item)} sx={{ textTransform: "uppercase" }}>{item}</MenuItem>)}
            </Select>
        </FormControl>
    ));
}

function KVOptionsFieldEditor(props: { config: KVOptionsField, data: Record<string, any>, onUpdated: () => void, disabled?: boolean }) {
    const [record, setRecord] = useState<Record<string, string>>(props.data[props.config.key] ?? {})
    const [newItemKey, setNewItemKey] = useState("");
    const [newItemValue, setNewItemValue] = useState("");

    const items = useMemo(() => Object.entries(record).sort((a, b) => a[0].localeCompare(b[0])), [record]);

    useEffect(() => {
        if (props.data[props.config.key] !== record) {
            props.data[props.config.key] = record;
            props.onUpdated();
        }
    }, [record])

    return (
        <Stack spacing={0.25} color={theme => theme.palette.text.primary}>
            <Typography>{props.config.label}</Typography>
            <Grid container rowSpacing={1} columns={props.disabled ? 11 : 12}>
                {items.map(item => (
                    <React.Fragment key={item[0]}>
                        <Grid item xs={5}>
                            <TextField variant="filled" fullWidth size="small" value={item[0]} label="key" disabled />
                        </Grid>
                        <Grid item xs={1}>
                            <Stack alignItems="center" justifyContent="center" height="100%">
                                <Typography fontSize="1.2rem">=</Typography>
                            </Stack>
                        </Grid>
                        <Grid item xs={5}>
                            <TextField variant="filled" fullWidth size="small" value={item[1]} label="key" disabled />
                        </Grid>
                        {!props.disabled && (
                            <Grid item xs={1} paddingX={1}>
                                <IconButton onClick={() => setRecord(pv => Object.fromEntries(Object.entries(pv).filter(e => e[0] !== item[0])))}>
                                    <CloseIcon />
                                </IconButton>
                            </Grid>
                        )}
                    </React.Fragment>
                ))}
                {(!props.disabled || items.length == 0) && (
                    <>
                        <Grid item xs={5}>
                            <TextField variant="filled" fullWidth size="small" value={newItemKey} label="key" onInput={e => setNewItemKey((e.target as HTMLInputElement).value)} disabled={props.disabled} />
                        </Grid>
                        <Grid item xs={1}>
                            <Stack alignItems="center" justifyContent="center" height="100%">
                                <Typography fontSize="1.2rem">=</Typography>
                            </Stack>
                        </Grid>
                        <Grid item xs={5}>
                            <TextField variant="filled" fullWidth size="small" value={newItemValue} label="value" onInput={e => setNewItemValue((e.target as HTMLInputElement).value)} disabled={props.disabled} />
                        </Grid>
                        {!props.disabled && (

                            <Grid item xs={1} paddingX={1}>
                                <IconButton onClick={() => {
                                    if (!props.disabled) {
                                        setRecord(pv => ({ ...pv, [newItemKey]: newItemValue }));
                                        setNewItemKey("");
                                        setNewItemValue("");
                                    }
                                }} disabled={props.disabled}>
                                    <AddIcon />
                                </IconButton>
                            </Grid>
                        )}
                    </>
                )}
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
        )} label={<Typography color={theme => theme.palette.text.primary}>{props.config.label}</Typography>} />
    );
}

export function StaticEditor(props: { data: Record<string, any>, fields: EditorField[], onUpdated?: () => void, disabledFields?: Set<string>, disableAll?: boolean }) {
    const disabledFields = props.disabledFields ?? new Set();
    const onUpdated = useCallback(() => props.onUpdated?.call(null), [props.fields, props.onUpdated]);

    return (
        <Stack spacing={2} paddingY={2}>
            {props.fields.map(field => {
                if (field.type === "number") {
                    return <NumberFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "slider") {
                    return <SliderFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "select") {
                    return <SelectFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "dynamicselect") {
                    return <DynamicSelectFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "multiselect") {
                    return <MultiselectFieldEditor disabledFields={disabledFields} key={Object.keys(field.items[0]).join(";")} data={props.data} config={field} onUpdated={onUpdated} disableAll={!!props.disableAll}/>
                }
                else if (field.type === "boolean") {
                    return <BooleanFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "text") {
                    return <TextFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
                else if (field.type === "kvoptions") {
                    return <KVOptionsFieldEditor disabled={disabledFields.has(field.key) || props.disableAll} key={field.key} data={props.data} config={field} onUpdated={onUpdated} />
                }
            })}
        </Stack>
    );
}