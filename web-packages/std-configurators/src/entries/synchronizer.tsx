import { GraphSetter, Task, TaskCLSConfigurator, TaskConfiguratorContext, TaskOutput, compareIOIgnorePaths, createCLSConfigurator, getObjectDiffPaths, parseMetadataField } from "@streamtasks/core";
import objectPath from "object-path";
import { v4 as uuidv4 } from "uuid";
import { z } from "zod";

export class SynchronizerConfigurator extends TaskCLSConfigurator {
    constructor(context: TaskConfiguratorContext, task?: Task) {
        super(context, task ?? {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: parseMetadataField(context.taskHost.metadata, "cfg:label", z.string(), true),
            config: { topics: [] },
            inputs: [],
            outputs: [],
        });
        this.fix();
    }

    public  connect(key: string, output?: TaskOutput) {
        const [input, inputIndex] = this.getInput(key, true);
        const dcSetter = this.getGraph();
        dcSetter.set(`inputs.${inputIndex}.topic_id`, undefined);
        dcSetter.apply();

        if (output) {
            const setter = this.getGraph();
            const diffs = getObjectDiffPaths(input, output, compareIOIgnorePaths);
            setter.set(`inputs.${inputIndex}.topic_id`, output.topic_id);
            for (const diff of diffs) {
                setter.set(`inputs.${inputIndex}.${diff}`, objectPath.get(output, diff));
            }
            try {
                setter.apply();
            }
            catch {
                if (input.topic_id === output.topic_id) {
                    setter.reset();
                    setter.set(`inputs.${inputIndex}.topic_id`, undefined);
                    setter.apply();
                }
            }
        }

        this.fix();
    }

    private fix() {
        if (this.task.inputs.length !== this.task.outputs.length) {
            throw new Error("Synchronizer must have equal number of IOs!");
        }

        if (this.task.inputs.length > 0) {
            const removeIndexes = new Set([...Array(this.task.inputs.length - 1).keys()].filter(idx => typeof this.task.inputs[idx].topic_id !== "number"));
            this.task.inputs = this.task.inputs.filter((_, idx) => !removeIndexes.has(idx));
            this.task.outputs = this.task.outputs.filter((_, idx) => !removeIndexes.has(idx));
        }

        if (this.task.inputs.length === 0 || typeof this.task.inputs.at(-1)?.topic_id === "number") {
            this.task.inputs.push({ key: uuidv4() })
            this.task.outputs.push({ topic_id: this.newId() })
        }

        this.task.inputs.forEach((input, idx) => input.label = `input ${idx + 1}`);
        this.task.outputs.forEach((output, idx) => output.label = `output ${idx + 1}`);
        this.task.inputs.at(-1)!.label = "new input";
        this.task.outputs.at(-1)!.label = "new output";

        this.config.topics = [...Array(this.task.inputs.length - 1).keys()].map(idx => [this.inputs[idx].topic_id, this.outputs[idx].topic_id]);
    }
    private getGraph() {
        const setter = new GraphSetter(this.task);

        this.inputs.forEach((input, idx) => {
            setter.addEdgeGenerator(`inputs.${idx}`, subPath => {
                if (!subPath || compareIOIgnorePaths.has(subPath)) return [];
                return [`outputs.${idx}.${subPath}`];
            });
        });

        return setter;
    }
}

const configurator = createCLSConfigurator((context, task) => new SynchronizerConfigurator(context, task));
export default configurator;