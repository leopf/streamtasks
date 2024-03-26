import { z } from "zod";
import { Metadata, TaskConfigurator, TaskConfiguratorContext, TaskInstance, TaskOutput } from "../../types/task";
import { v4 as uuidv4 } from 'uuid';
import { MetadataModel, TaskInputModel, TaskOutputModel } from "../../model/task";

export const TaskPartialInputModel = MetadataModel.and(z.object({
    key: z.string()
}));

const task: TaskConfigurator = {
    connect: (taskInstance: TaskInstance, key: string, output: TaskOutput, context: TaskConfiguratorContext) => {
        const targetInput = taskInstance.inputs.find(input => input.key === key);
        if (!targetInput) {
            throw new Error("Input stream not found!"); // should not happen during normal operation
        }
        const outputMetadata: Metadata = { ...output };
        delete outputMetadata.topic_id;

        const inputMetadata: Metadata = { ...targetInput };
        delete inputMetadata.key;

        if ("topic_id" in inputMetadata) delete inputMetadata.topic_id

        for (const metadataKey of new Set([...Object.keys(outputMetadata), ...Object.keys(inputMetadata)])) {
            if (outputMetadata[metadataKey] !== inputMetadata[metadataKey]) {
                throw new Error(`Metadata mismatch on field "${metadataKey}".`);
            }
        }

        targetInput.topic_id = output.topic_id;
        return taskInstance;
    },
    create: (context: TaskConfiguratorContext) => {
        const metadata = context.taskHost.metadata;
        const label = z.string().parse(metadata["cfg:label"]);
        const inputs = z.array(TaskPartialInputModel).parse(metadata["cfg:inputs"])
        const outputs = z.array(TaskOutputModel).parse(metadata["cfg:outputs"])

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