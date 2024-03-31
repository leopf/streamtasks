import { z } from "zod";
import { Metadata, TaskConfigurator, TaskConfiguratorContext, TaskInstance, TaskOutput } from "../../types/task";
import { v4 as uuidv4 } from "uuid";
import { MetadataModel, TaskInputModel, TaskOutputModel } from "../../model/task";
import { validateMetadataEquals } from "../../lib/task";

export const TaskPartialInputModel = MetadataModel.and(z.object({
    key: z.string()
}));

export type TaskPartialInput = z.infer<typeof TaskPartialInputModel>;

const compareIgnoreMetadataKeys = new Set([ "key", "topic_id", "label" ]);

const task: TaskConfigurator = {
    connect: (taskInstance: TaskInstance, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
        const targetInput = taskInstance.inputs.find(input => input.key === key);
        if (!targetInput) {
            throw new Error("Input stream not found!"); // should not happen during normal operation
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
        const outputs = z.array(TaskOutputModel).parse(JSON.parse(String(metadata["cfg:outputs"])))

        return (<TaskInstance>{
            id: uuidv4(),
            label: label,
            config: {},
            inputs: inputs,
            outputs: outputs
        });
    },
    toStartConfig: (taskInstance: TaskInstance, context: TaskConfiguratorContext) => {
        return {
            ...taskInstance.config,
            ...Object.fromEntries(taskInstance.inputs.map(i => [i.key, i.topic_id ?? null])),
            outputs: taskInstance.outputs.map(o => o.topic_id)
        };
    }
};

export default task;