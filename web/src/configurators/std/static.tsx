import { z } from "zod";
import { TaskConfigurator, TaskConfiguratorContext, Task, TaskOutput } from "../../types/task";
import { v4 as uuidv4 } from "uuid";
import { MetadataModel } from "../../model/task";
import { validateMetadataEquals } from "../../lib/task";
import { ReactEditorRenderer as ReactRenderer } from "../../lib/conigurator";
import { EditorField, EditorFieldModel } from "../../StaticEditor/types";
import { StaticEditor } from "../../StaticEditor";
import { LRUCache } from "lru-cache";

export const TaskPartialInputModel = MetadataModel.and(z.object({
    key: z.string()
}));
export type TaskPartialInput = z.infer<typeof TaskPartialInputModel>;

const InputMetadataMapModel = z.record(z.string(), z.record(z.string(), z.string()));
const OutputMetadataMapModel = z.array(z.record(z.string(), z.string()).optional());
const OutputKeysMapModel = z.array(z.string().optional());

const compareIgnoreMetadataKeys = new Set(["key", "topic_id", "label"]);

const reactRenderer = new ReactRenderer();
const metadataFieldsCache = new LRUCache<string, EditorField[]>({ max: 100 });

// maps output topic ids to config fiels with config = { [output key]: [output topic id] } + [old config]
function applyOutputIdsToConfig(task: Task, context: TaskConfiguratorContext) {
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
function applyConfigToOutputMetadata(task: Task, context: TaskConfiguratorContext) {
    const outputMetadataRaw = context.taskHost.metadata["cfg:outputmetadata"];
    if (typeof outputMetadataRaw !== "string") return;
    OutputMetadataMapModel.parse(JSON.parse(outputMetadataRaw)).forEach((map, idx) => {
        const output = task.outputs.at(idx);
        if (!output || !map) return;
        for (const [ configKey, outputKey ] of Object.entries(map)) {
            output[outputKey] = task.config[configKey];
        }
    });
}

// maps config values to input metadata values with map { [input key]: { [config key]: [input metadata key] } }
function applyConfigToInputMetadata(task: Task, context: TaskConfiguratorContext) {
    const inputMetadataRaw = context.taskHost.metadata["cfg:inputmetadata"];
    if (typeof inputMetadataRaw !== "string") return;
    for (const [ inputKey, map ] of Object.entries(InputMetadataMapModel.parse(JSON.parse(inputMetadataRaw)))) {
        const foundInput = task.inputs.find(input => input.key === inputKey)
        if (foundInput) {
            for (const [ configKey, inputMetadataKey ] of Object.entries(map)) {
                foundInput[inputMetadataKey] = task.config[configKey];
            }
        }
    }
}

function applyConfigToIOMetadata(task: Task, context: TaskConfiguratorContext) {
    applyConfigToOutputMetadata(task, context);
    applyConfigToInputMetadata(task, context);
}

function getDisabledFields(task: Task, context: TaskConfiguratorContext) {
    const inputMetadataRaw = context.taskHost.metadata["cfg:inputmetadata"];
    if (typeof inputMetadataRaw !== "string") return;
    const disabledInputs = new Set<string>();
    for (const [ inputKey, map ] of Object.entries(InputMetadataMapModel.parse(JSON.parse(inputMetadataRaw)))) {
        if (task.inputs.find(input => input.key === inputKey)?.topic_id) {
            Object.keys(map).forEach(k => disabledInputs.add(k))
        }
    }
    return disabledInputs;
}


const task: TaskConfigurator = {
    connect: (task: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
        const targetInput = task.inputs.find(input => input.key === key);
        if (!targetInput) {
            throw new Error("Input not found!"); // should not happen during normal operation
        }

        if (!output) {
            targetInput.topic_id = undefined;
        }
        else {
            validateMetadataEquals(output, targetInput, compareIgnoreMetadataKeys);
            targetInput.topic_id = output.topic_id;
        }
        task.config[targetInput.key] = targetInput.topic_id
        return task;
    },
    create: (context: TaskConfiguratorContext) => {
        const metadata = context.taskHost.metadata;
        const label = z.string().parse(metadata["cfg:label"]);
        const inputs = z.array(TaskPartialInputModel).parse(JSON.parse(String(metadata["cfg:inputs"])))
        const outputs = z.array(MetadataModel).parse(JSON.parse(String(metadata["cfg:outputs"])))
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
    },
    renderEditor: (task: Task, element: HTMLElement, context: TaskConfiguratorContext) => {
        if (typeof context.taskHost.metadata["cfg:editorfields"] !== "string") return;
        const fieldsData = String(context.taskHost.metadata["cfg:editorfields"]);
        const fields = metadataFieldsCache.get(fieldsData) ?? z.array(EditorFieldModel).parse(JSON.parse(fieldsData))
        if (!metadataFieldsCache.has(fieldsData)) metadataFieldsCache.set(fieldsData, fields)
        reactRenderer.render(element, <StaticEditor task={task} fields={fields} beforeUpdate={() => {
            applyConfigToIOMetadata(task, context);
        }} disabledFields={getDisabledFields(task, context)} />)
    }
};

export default task;