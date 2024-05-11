import { TaskConfiguratorContext, Task, Metadata, TaskPartialInput, TaskInput, TaskInstance, TaskInstanceStatus } from "../../types/task";
import { getMetadataKeyDiffs as getObjectDiffPaths } from "../../lib/task";
import { TaskCLSConfigurator, TaskCLSReactRendererMixin, createCLSConfigurator } from "../../lib/conigurator";
import { StaticEditor } from "../../StaticEditor";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { EditorField, EditorFieldsModel } from "../../StaticEditor/types";
import { GraphSetter, compareIgnoreMetadataKeys as compareIOIgnorePaths, extractObjectPathValues, parseMetadataField } from "../../lib/conigurator/helpers";
import { getFieldValidator } from "../../StaticEditor/util";
import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import { MetadataModel, TaskPartialInputModel } from "../../model/task";
import objectPath from "object-path";
import { Accordion, AccordionDetails, AccordionSummary, Box, Stack, Typography } from "@mui/material";
import { ExpandMore as ExpandMoreIcon } from "@mui/icons-material";
import urlJoin from "url-join";

const IOMirrorDataModel = z.array(z.tuple([z.string(), z.number().int()]));
type IOMirrorData = z.infer<typeof IOMirrorDataModel>;

function parseInputs(metadata: Metadata) {
    return parseMetadataField(metadata, "cfg:inputs", z.array(TaskPartialInputModel)) ?? [];
}

function parseOutputs(metadata: Metadata) {
    return parseMetadataField(metadata, "cfg:outputs", z.array(MetadataModel)) ?? [];
}

function TaskDisplay(props: { task: Task, taskInstance: TaskInstance, editorFields: EditorField[] }) {
    const [configExpanded, setConfigExpanded] = useState(false);

    const frontendUrl = useMemo(() => {
        const subPath = parseMetadataField(props.taskInstance.metadata, "cfg:frontendpath", z.string());
        if (!subPath) return;
        return urlJoin(location.href.split("#")[0], `./task/${props.taskInstance.id}/`, subPath ?? "frontend.html")
    }, [props.taskInstance]);

    useEffect(() => {
        if (!frontendUrl && props.taskInstance.status === TaskInstanceStatus.running) {
            setConfigExpanded(true);
        }
    }, [frontendUrl]);

    return (
        <Stack direction="column" spacing={3} height="100%" width="100%">
            <Accordion expanded={configExpanded} onChange={() => setConfigExpanded(pv => !pv)}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography>config</Typography>
                </AccordionSummary>
                <AccordionDetails>
                    <StaticEditor data={props.task.config} fields={props.editorFields} disableAll />
                </AccordionDetails>
            </Accordion>
            {frontendUrl && (
                <Box flex={1}>
                    <iframe src={frontendUrl} width="100%" height="100%" style={{ border: "none" }} />
                </Box>
            )}
        </Stack>
    )
}

export class StaticCLSConfigurator extends TaskCLSReactRendererMixin(TaskCLSConfigurator) {
    protected get editorFields() {
        return parseMetadataField(this.taskHost.metadata, "cfg:editorfields", EditorFieldsModel, false) ?? [];
    }

    constructor(context: TaskConfiguratorContext, task?: Task) {
        super(context, task ?? {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: parseMetadataField(context.taskHost.metadata, "cfg:label", z.string(), true),
            config: parseMetadataField(context.taskHost.metadata, "cfg:config", z.record(z.any())) ?? {},
            inputs: parseInputs(context.taskHost.metadata),
            outputs: parseOutputs(context.taskHost.metadata).map(o => ({ ...o, topic_id: context.idGenerator() })),
        });
        if (!task) {
            this.applyOutputIds();
            this.applyConfig(false);
        }
    }

    public rrenderDisplay(taskInstance: TaskInstance): ReactNode {
        return <TaskDisplay editorFields={this.editorFields} task={this.task} taskInstance={taskInstance} />
    }
    public rrenderEditor(onUpdate: () => void): ReactNode {
        const cs = this.getGraph();
        return <StaticEditor data={this.config} fields={this.editorFields} onUpdated={() => {
            this.applyConfig(true);
            onUpdate();
        }} disabledFields={cs.getDisabledFields("config", true)} />
    }
    public connect(key: string, output?: (Record<string, string | number | boolean | undefined> & { topic_id: number; }) | undefined): void | Promise<void> {
        const [input, inputIndex] = this.getInput(key, true);
        const dcSetter = this.getGraph();
        dcSetter.set(`inputs.${inputIndex}.topic_id`, undefined);
        this.setFields(dcSetter.validate());

        if (output) {
            const setter = this.getGraph();
            const diffs = getObjectDiffPaths(input, output, compareIOIgnorePaths);
            setter.set(`inputs.${inputIndex}.topic_id`, output.topic_id);
            for (const diff of diffs) {
                setter.set(`inputs.${inputIndex}.${diff}`, objectPath.get(output, diff));
            }
            try {
                this.setFields(setter.validate());
            }
            catch {
                if (input.topic_id === output.topic_id) {
                    setter.clearSetters();
                    setter.set(`inputs.${inputIndex}.topic_id`, undefined);
                    this.setFields(setter.validate());
                }
            }
        }
    }

    protected applyOutputIds() {
        const setter = this.getGraph();
        this.outputs.forEach((o, idx) => setter.set(`outputs.${idx}.topic_id`, o.topic_id));
        this.setFields(setter.validate())
    }

    protected applyConfig(ignoreDisabled: boolean) {
        const setter = this.getGraph();
        const pathValues = extractObjectPathValues(this.config, "config.");
        if (ignoreDisabled) {
            Array.from(pathValues.keys()).forEach(k => {
                if (setter.isDisabled(k)) {
                    pathValues.delete(k);
                }
            })
        }

        for (const [k, v] of pathValues.entries()) {
            setter.set(k, v);
        }
        this.setFields(setter.validate())
    }

    protected getGraph() {
        const setter = new GraphSetter();
        for (const field of this.editorFields) {
            const validator = getFieldValidator(field);
            setter.constrainValidator(`config.${field.key}`, v => validator.safeParse(v).success)
        }

        const config2InputMap = parseMetadataField(this.taskHost.metadata, "cfg:config2inputmap", z.record(z.string(), z.record(z.string(), z.string()))) ?? {};
        for (const [inputKey, map] of Object.entries(config2InputMap)) {
            const inputIndex = this.inputs.findIndex(input => input.key === inputKey);
            if (inputIndex !== -1) {
                for (const [configKey, inputMetadataKey] of Object.entries(map)) {
                    setter.addEdge(`inputs.${inputIndex}.${inputMetadataKey}`, `config.${configKey}`);
                }
            }
        }
        const originalInputs = parseInputs(this.taskHost.metadata);
        const originalInputKeys = new Set(originalInputs.map(input => input.key));
        this.inputs.forEach((input, idx) => {
            if (originalInputKeys.has(input.key)) {
                setter.addEdge(`inputs.${idx}.topic_id`, `config.${input.key}`);
            }
            if (input.topic_id !== undefined) {
                setter.addDisableCheck(`inputs.${idx}`, (subPath) => !compareIOIgnorePaths.has(subPath));
            }
        });

        for (const oInput of originalInputs) {
            const mappedFields = Object.values(config2InputMap[oInput.key] ?? {});
            const disableFields = Object.keys(oInput).filter(k => !compareIOIgnorePaths.has(k) && !mappedFields.includes(k));
            const inputIndex = this.inputs.findIndex(input => input.key === oInput.key);
            if (inputIndex !== -1) {
                disableFields.forEach(field => setter.addDisableCheck(`inputs.${inputIndex}.${field}`, () => true));
            }
        }

        const originalOutputs = parseOutputs(this.taskHost.metadata);
        const config2OutputMap = parseMetadataField(this.taskHost.metadata, "cfg:config2outputmap", z.array(z.record(z.string(), z.string()).optional())) ?? [];
        config2OutputMap.forEach((map, outputIndex) => {
            if (map) {
                for (const [configKey, outputMetadataKey] of Object.entries(map)) {
                    setter.addEdge(`outputs.${outputIndex}.${outputMetadataKey}`, `config.${configKey}`);
                }
            }
            const mappedFields = Object.values(map ?? {});
            const oOutput = originalOutputs[outputIndex] ?? {};
            const disableFields = Object.keys(oOutput).filter(k => !compareIOIgnorePaths.has(k) && !mappedFields.includes(k));
            disableFields.forEach(field => setter.addDisableCheck(`outputs.${outputIndex}.${field}`, () => true));
        });

        const outputConfigKeys = parseMetadataField(this.taskHost.metadata, "cfg:outputkeys", z.array(z.string().optional())) ?? [];
        outputConfigKeys.forEach((configKey, outputIndex) => {
            if (this.outputs[outputIndex]) {
                setter.addEdge(`config.${configKey}`, `outputs.${outputIndex}.topic_id`);
            }
        });

        this.makeIOMirrorGraph(setter);

        return setter;
    }

    private makeIOMirrorGraph(setter: GraphSetter) {
        // if (String(this.taskHost.metadata["cfg:label"]).startsWith("timestamp")) debugger;
        const data = parseMetadataField(this.taskHost.metadata, "cfg:iomirror", IOMirrorDataModel) ?? [];

        const effectedInputs = new Set(data.map(e => e[0]));
        const effectedOutputs = new Set(data.map(e => e[1]));
        const baseInputs = parseInputs(this.taskHost.metadata).map(input => [this.getInput(input.key, true)[1], input] as [number, TaskPartialInput]).filter(([_, input]) => effectedInputs.has(input.key));
        const baseOutputs = parseOutputs(this.taskHost.metadata).map((output, idx) => [idx, output] as [number, Metadata]).filter(([idx, _]) => effectedOutputs.has(idx));

        this.inputs.map((input, idx) => [input, idx] as [TaskInput, number]).filter(([input, _]) => !effectedInputs.has(input.key))
            .forEach(([input, idx]) => setter.addDisableCheck(`inputs.${idx}`, subPath => !compareIOIgnorePaths.has(subPath) && !objectPath.has(input, subPath)))

        const inputKeyToIndexMap = Object.fromEntries(baseInputs.map(([idx, input]) => [input.key, idx]));
        [
            ...baseInputs.map(([idx, input]) => [`inputs.${idx}`, data.filter(([inputKey, _]) => inputKey === input.key).map(([_, outputIdx]) => `outputs.${outputIdx}`)] as [string, string[]]),
            ...baseOutputs.map(([idx, _]) => [`outputs.${idx}`, data.filter(([_, outputIdx]) => outputIdx === idx).map(([inputKey, _]) => `inputs.${inputKeyToIndexMap[inputKey]}`)] as [string, string[]]),
        ].forEach(([path, connectedPaths]) => {
            setter.addEdgeGenerator(path, (subPath) => {
                if (!subPath || subPath === "topic_id") return [];
                return connectedPaths.map(p => `${p}.${subPath}`);
            });
        })
    }
}

const configurator = createCLSConfigurator((context, task) => new StaticCLSConfigurator(context, task));
export default configurator;