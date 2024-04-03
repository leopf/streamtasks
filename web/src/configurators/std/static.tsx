import { z } from "zod";
import { TaskConfigurator, TaskConfiguratorContext, TaskInstance, TaskOutput } from "../../types/task";
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

const compareIgnoreMetadataKeys = new Set(["key", "topic_id", "label"]);

const reactRenderer = new ReactRenderer();
const metadataFieldsCache = new LRUCache<string, EditorField[]>({ max: 100 });

const task: TaskConfigurator = {
    connect: (taskInstance: TaskInstance, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
        const targetInput = taskInstance.inputs.find(input => input.key === key);
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
        return taskInstance;
    },
    create: (context: TaskConfiguratorContext) => {
        const metadata = context.taskHost.metadata;
        const label = z.string().parse(metadata["cfg:label"]);
        const inputs = z.array(TaskPartialInputModel).parse(JSON.parse(String(metadata["cfg:inputs"])))
        const outputs = z.array(MetadataModel).parse(JSON.parse(String(metadata["cfg:outputs"])))
        const config = "cfg:config" in metadata ? z.record(z.any()).parse(JSON.parse(String(metadata["cfg:config"]))) : {};

        return {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: label,
            config: config,
            inputs: inputs,
            outputs: outputs.map(output => ({ ...output, topic_id: context.idGenerator() }))
        };
    },
    toStartConfig: (taskInstance: TaskInstance, context: TaskConfiguratorContext) => {
        const outputKeys = "cfg:outputkeys" in context.taskHost.metadata ?
            z.array(z.string().optional()).parse(JSON.parse(String(context.taskHost.metadata["cfg:outputkeys"]))) : [];

        return {
            ...taskInstance.config,
            ...Object.fromEntries(taskInstance.inputs.map(i => [i.key, i.topic_id ?? null])),
            ...Object.fromEntries(outputKeys.map((key, idx) => [key, taskInstance.outputs.at(idx)?.topic_id]).filter(([k, v]) => k && v))
        };
    },
    renderEditor: (taskInstance: TaskInstance, element: HTMLElement, context: TaskConfiguratorContext) => {
        if (typeof context.taskHost.metadata["cfg:editorfields"] !== "string") return;
        const fieldsData = String(context.taskHost.metadata["cfg:editorfields"]);
        const fields = metadataFieldsCache.get(fieldsData) ?? z.array(EditorFieldModel).parse(JSON.parse(fieldsData))
        if (!metadataFieldsCache.has(fieldsData)) metadataFieldsCache.set(fieldsData, fields)
        reactRenderer.render(element, <StaticEditor task={taskInstance} fields={fields}/>)
    }
};

export default task;