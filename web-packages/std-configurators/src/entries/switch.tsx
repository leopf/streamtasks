import { GraphSetter, Task, TaskCLSConfigurator, TaskConfiguratorContext, TaskOutput, compareIOIgnorePaths, createCLSConfigurator, extractObjectPathValues, getObjectDiffPaths, parseMetadataField } from "@streamtasks/core";
import objectPath from "object-path";
import { v4 as uuidv4 } from "uuid";
import { z } from "zod";

export class SwitchConfigurator extends TaskCLSConfigurator {
    constructor(context: TaskConfiguratorContext, task?: Task) {
        super(context, task ?? {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: parseMetadataField(context.taskHost.metadata, "cfg:label", z.string(), true),
            config: { topics: [] },
            inputs: [],
            outputs: [{ topic_id: context.idGenerator(), label: "output" }],
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
        if (this.task.outputs.length !== 1) throw new Error("Switch must have one output!");
        if (this.task.inputs.length % 2 !== 0) {
            throw new Error("Switch must have an event amount of inputs!");
        }

        if (this.task.inputs.length > 2) {
            const removeInputIndexes = new Set<number>();
            [...Array(Math.floor(this.task.inputs.length / 2) - 1).keys()].forEach(idx => {
                if (typeof this.task.inputs[idx*2].topic_id !== "number" && typeof this.task.inputs[idx*2 + 1].topic_id !== "number") {
                    removeInputIndexes.add(idx*2);
                    removeInputIndexes.add(idx*2+1);
                }
            });

            this.task.inputs = this.task.inputs.filter((_, idx) => !removeInputIndexes.has(idx));
        }

        if (this.task.inputs.length < 2 || typeof this.task.inputs.at(-1)?.topic_id === "number" ||  typeof this.task.inputs.at(-2)?.topic_id === "number") {
            this.task.inputs.push({ key: uuidv4() });
            this.task.inputs.push({ key: uuidv4(), "content": "number", "type": "ts" });
        }


        [...Array(Math.floor(this.task.inputs.length / 2) - 1).keys()].forEach(idx => {
            this.task.inputs[idx * 2].label = `input ${idx + 1}`;
            this.task.inputs[idx * 2 + 1].label = `control ${idx + 1}`;
        });

        this.task.inputs.at(-2)!.label = "new input";
        this.task.inputs.at(-1)!.label = "new control";

        this.config.pairs = [...Array(Math.floor(this.task.inputs.length / 2) - 1).keys()].map(idx => ({ 
            input: this.inputs[idx*2].topic_id,
            control: this.inputs[idx*2 + 1].topic_id,
        }));
        this.config.output = this.task.outputs[0].topic_id;

        const graph = this.getGraph();
        for (const [k, v] of extractObjectPathValues(this.task.outputs[0]).entries()) {
            if (!compareIOIgnorePaths.has(k)) {
                graph.set(`outputs.0.${k}`, v);
            }
        }
        graph.apply();
    }
    private getGraph() {
        const setter = new GraphSetter(this.task);

        [...Array(Math.floor(this.task.inputs.length / 2)).keys()].forEach((idx) => {
            setter.addEdgeGenerator(`inputs.${idx*2}`, subPath => {
                if (!subPath || compareIOIgnorePaths.has(subPath)) return [];
                return [`outputs.0.${subPath}`];
            });
        });
        setter.addEdgeGenerator("outputs.0", subPath => {
            return [...Array(Math.floor(this.task.inputs.length / 2)).keys()].map(idx => `inputs.${idx * 2}.${subPath}`)
        });
        this.task.inputs.forEach((input, idx) => {
            if (typeof input.topic_id === "number") {
                setter.addValidator(`inputs.${idx}`, (_, subPath) => compareIOIgnorePaths.has(subPath));
            }
        })

        return setter;
    }
}

const configurator = createCLSConfigurator((context, task) => new SwitchConfigurator(context, task));
export default configurator;