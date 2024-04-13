import { z } from "zod";
import { Metadata, Task, TaskConfiguratorContext, TaskInput, TaskOutput } from "../../../types/task";
import { EditorField, EditorFieldModel } from "../../../StaticEditor/types";
import { LRUCache } from "lru-cache";
import { MetadataModel } from "../../../model/task";
import { getConfigModelByFields } from "../../../StaticEditor/util";
import { v4 as uuidv4 } from "uuid";

export const TaskPartialInputModel = MetadataModel.and(z.object({
    key: z.string()
}));
export type TaskPartialInput = z.infer<typeof TaskPartialInputModel>;

const metadataFieldsCache = new LRUCache<string, EditorField[]>({ max: 100 });
const InputMetadataMapModel = z.record(z.string(), z.record(z.string(), z.string()));
const OutputMetadataMapModel = z.array(z.record(z.string(), z.string()).optional());
const OutputKeysMapModel = z.array(z.string().optional());

export const compareIgnoreMetadataKeys = new Set(["key", "topic_id", "label"]);

export function getDefinedKeys<T extends string | number | symbol>(m: Record<T, any>) {
    return Object.entries(m).filter(([k, v]) => v !== undefined && v !== null).map(e => e[0])
}

export function getCFGFieldInputMetadata(context: TaskConfiguratorContext) {
    const inputMetadataRaw = context.taskHost.metadata["cfg:inputmetadata"];
    if (typeof inputMetadataRaw !== "string") return;
    return InputMetadataMapModel.parse(JSON.parse(inputMetadataRaw));
}

export function getCFGFieldInputs(context: TaskConfiguratorContext) {
    return z.array(TaskPartialInputModel).parse(JSON.parse(String(context.taskHost.metadata["cfg:inputs"])))
}

export function getCFGFieldOutputs(context: TaskConfiguratorContext) {
    return z.array(MetadataModel).parse(JSON.parse(String(context.taskHost.metadata["cfg:outputs"])))
}

export function getCFGFieldIOMirror(context: TaskConfiguratorContext) {
    const IOMirrorMetadataRaw = context.taskHost.metadata["cfg:iomirror"];
    if (typeof IOMirrorMetadataRaw !== "string") return;
    return z.array(z.tuple([z.string(), z.number()])).parse(JSON.parse(IOMirrorMetadataRaw));
}

export function getCFGFieldEditorFields(context: TaskConfiguratorContext, key: string = "cfg:editorfields"): EditorField[] | undefined {
    if (typeof context.taskHost.metadata[key] !== "string") return;
    const fieldsData = String(context.taskHost.metadata[key]);
    const fields = metadataFieldsCache.get(fieldsData) ?? z.array(EditorFieldModel).parse(JSON.parse(fieldsData))
    if (!metadataFieldsCache.has(fieldsData)) metadataFieldsCache.set(fieldsData, fields)
    return fields;
}

// maps output topic ids to config fiels with config = { [output key]: [output topic id] } + [old config]
export function applyOutputIdsToConfig(task: Task, context: TaskConfiguratorContext) {
    const outputKeysRaw = context.taskHost.metadata["cfg:outputkeys"];
    if (typeof outputKeysRaw !== "string") return;
    OutputKeysMapModel.parse(JSON.parse(outputKeysRaw)).forEach((key, idx) => {
        const topic_id = task.outputs.at(idx)?.topic_id;
        if (key && topic_id) {
            task.config[key] = topic_id;
        }
    });
}


// maps config values to output metadata values with map { [config key]: [output metadata key] }
export function applyConfigToOutputMetadata(task: Task, context: TaskConfiguratorContext) {
    const outputMetadataRaw = context.taskHost.metadata["cfg:outputmetadata"];
    if (typeof outputMetadataRaw !== "string") return;
    OutputMetadataMapModel.parse(JSON.parse(outputMetadataRaw)).forEach((map, idx) => {
        const output = task.outputs.at(idx);
        if (!output || !map) return;
        for (const [configKey, outputKey] of Object.entries(map)) {
            output[outputKey] = task.config[configKey];
        }
    });
}

// maps config values to input metadata values with map { [input key]: { [config key]: [input metadata key] } }
export function applyConfigToInputMetadata(task: Task, context: TaskConfiguratorContext) {
    for (const [inputKey, map] of Object.entries(getCFGFieldInputMetadata(context) ?? {})) {
        const foundInput = task.inputs.find(input => input.key === inputKey)
        if (foundInput) {
            for (const [configKey, inputMetadataKey] of Object.entries(map)) {
                foundInput[inputMetadataKey] = task.config[configKey];
            }
        }
    }
}

export function applyConfigToIOMetadata(task: Task, context: TaskConfiguratorContext) {
    applyConfigToOutputMetadata(task, context);
    applyConfigToInputMetadata(task, context);
}

export function getDisabledFields(task: Task, context: TaskConfiguratorContext, ignoreKey?: string) {
    const inputMetadataRaw = context.taskHost.metadata["cfg:inputmetadata"];
    if (typeof inputMetadataRaw !== "string") return new Set<string>();
    const disabledInputs = new Set<string>();
    for (const [inputKey, map] of Object.entries(InputMetadataMapModel.parse(JSON.parse(inputMetadataRaw)))) {
        if (inputKey !== ignoreKey && task.inputs.find(input => input.key === inputKey)?.topic_id) {
            Object.keys(map).forEach(k => disabledInputs.add(k))
        }
    }
    return disabledInputs;
}

export function connectWithConfigOverwrite(task: Task, input: TaskInput, output: TaskOutput, diffs: string[], context: TaskConfiguratorContext) {
    try {
        if (diffs.some(d => output[d] === undefined || output[d] === null || input[d] === undefined || input[d] === null)) {
            throw new Error();
        }
        const disabledConfigFields = getDisabledFields(task, context, input.key);
        const inputMetadata = getCFGFieldInputMetadata(context)?.[input.key] ?? {};
        const allowSetInputMetadataConfig = Object.fromEntries(Object.entries(inputMetadata).filter(([k, v]) => !disabledConfigFields?.has(k)).map(([k, v]) => [v, k]));
        const allowSetInputMetadata = new Set(Object.keys(allowSetInputMetadataConfig));

        if (diffs.some(d => !allowSetInputMetadata.has(d))) {
            throw new Error();
        }

        const newConfig: Record<string, any> = {};
        for (const diff of diffs) {
            newConfig[allowSetInputMetadataConfig[diff]] = output[diff];
        }
        const fields = getCFGFieldEditorFields(context);
        const configModel = getConfigModelByFields(fields || []).partial().passthrough();
        Object.assign(task.config, configModel.parse(newConfig));
        applyConfigToIOMetadata(task, context);
        input.topic_id = output.topic_id;
        return true;
    } catch {
        return false;
    }
}

export function connectMirrorIO(task: Task, input: TaskInput, output: TaskOutput, diffs: string[], context: TaskConfiguratorContext) {
    try {
        const rawInputsMapped = Object.fromEntries(getCFGFieldInputs(context).map(i => [i.key, i]));
        const inputsMapped = Object.fromEntries(task.inputs.map(i => [i.key, i]));
        const rawOutputs = getCFGFieldInputs(context);
        const ioMirror = getCFGFieldIOMirror(context) ?? [];
        const effectedInputKeys = new Set([input.key]);
        const effectedOutputIdxs = new Set<number>();
        let lastEOL = 0;
        let lastEIL = 0;
        while (lastEOL !== effectedOutputIdxs.size || lastEIL !== effectedInputKeys.size) {
            lastEOL = effectedOutputIdxs.size;
            lastEIL = effectedInputKeys.size;
            for (const m of ioMirror.filter(m => effectedInputKeys.has(m[0]))) {
                effectedOutputIdxs.add(m[1]);
            }
            for (const m of ioMirror.filter(m => effectedOutputIdxs.has(m[1]))) {
                effectedInputKeys.add(m[0]);
            }
        }
        if (Array.from(effectedInputKeys).some(ik => !rawInputsMapped[ik] || !inputsMapped[ik])) {
            throw new Error("Input not found!");
        }
        const baseMetadata: Metadata[] = [rawInputsMapped[input.key]]; // this is the data that must not be changed
        effectedInputKeys.delete(input.key);
        for (const ik of effectedInputKeys) {
            baseMetadata.push(inputsMapped[ik].topic_id ? inputsMapped[ik] : rawInputsMapped[ik]);
        }
        for (const outIdx of effectedOutputIdxs) {
            const rawOutput = rawOutputs.at(outIdx);
            if (rawOutput) baseMetadata.push(rawOutput);
        }

        const newMetdata = { ...output };
        for (const ignoreKey of compareIgnoreMetadataKeys) {
            delete newMetdata[ignoreKey];
        }
        for (const k of Object.keys(newMetdata)) {
            if (newMetdata[k] === undefined || newMetdata[k] === null) {
                delete newMetdata[k];
            }
        }

        const diffSet = new Set(diffs);
        for (const m of baseMetadata) {
            for (const key of getDefinedKeys(m).filter(k => diffSet.has(k))) {
                if (newMetdata[key] !== undefined && m[key] !== newMetdata[key]) {
                    throw new Error("Found overwritten key, that can not be overwritten.");
                }
            }
        }

        task.inputs = task.inputs.map(i => effectedInputKeys.has(i.key) ? (i.topic_id ? { ...i, ...newMetdata } : { ...rawInputsMapped[i.key], ...newMetdata }) : i)
        task.outputs = task.outputs.map((o, idx) => effectedOutputIdxs.has(idx) ? { ...rawOutputs[idx], ...newMetdata, topic_id: o.topic_id } : o)
        Object.assign(input, newMetdata);
        input.topic_id = output.topic_id;
        return true;
    } catch {
        return false;
    }
}

export function createTaskFromContext(context: TaskConfiguratorContext) {
    const metadata = context.taskHost.metadata;
    const label = z.string().parse(metadata["cfg:label"]);
    const inputs = getCFGFieldInputs(context)
    const outputs = getCFGFieldOutputs(context)
    const config = "cfg:config" in metadata ? z.record(z.any()).parse(JSON.parse(String(metadata["cfg:config"]))) : {};

    const task: Task = {
        id: uuidv4(),
        task_host_id: context.taskHost.id,
        label: label,
        config: config,
        inputs: inputs,
        outputs: outputs.map(output => ({ ...output, topic_id: context.idGenerator() }))
    };

    applyOutputIdsToConfig(task, context);
    applyConfigToIOMetadata(task, context);

    return task;
}