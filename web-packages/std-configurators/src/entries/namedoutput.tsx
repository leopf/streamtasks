import { TextField, ThemeProvider } from "@mui/material";
import { GraphSetter, Metadata, StaticEditor, Task, TaskCLSConfigurator, TaskCLSReactRendererMixin, TaskConfiguratorContext, TaskOutput, compareIOIgnorePaths, createCLSConfigurator, extractObjectPathValues, getObjectDiffPaths, parseMetadataField, theme } from "@streamtasks/core";
import objectPath from "object-path";
import { ReactNode, useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { z } from "zod";

export class NamedOutputConfigurator extends TaskCLSReactRendererMixin(TaskCLSConfigurator) {
    constructor(context: TaskConfiguratorContext, task?: Task) {
        super(context, task ?? {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: parseMetadataField(context.taskHost.metadata, "cfg:label", z.string(), true),
            config: { metadata: {}, name: "named topic" },
            inputs: [ { key: "in_topic" } ],
            outputs: []
        });
        if (task === undefined) {
            this.applyConfig();
        }
    }

    public connect(key: string, output?: TaskOutput) {
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
    }

    public rrenderEditor(onUpdate: () => void): ReactNode {
        return (
            <ThemeProvider theme={theme}>
                <StaticEditor data={this.config} fields={[ { type: "text", key: "name", label: "name" } ]} onUpdated={() => {
                    this.applyConfig();
                    onUpdate();
                }}/>
            </ThemeProvider>
        );
    }

    protected applyConfig() {
        this.config.name = this.config.name.trim();
        const setter = this.getGraph();
        const pathValues = extractObjectPathValues(this.config, "config.");
        for (const [k, v] of pathValues.entries()) {
            setter.set(k, v);
        }
        setter.apply();
    }

    private getGraph() {
        const setter = new GraphSetter(this.task);

        setter.addEdge("inputs.0.label", "config.name");
        setter.addEdge("inputs.0.topic_id", "config.in_topic");
        setter.addEdgeGenerator("inputs.0", (subPath) => {
            if (compareIOIgnorePaths.has(subPath)) return [];
            return [`config.metadata.${subPath}`];
        });

        return setter;
    }
}

const configurator = createCLSConfigurator((context, task) => new NamedOutputConfigurator(context, task));
export default configurator;