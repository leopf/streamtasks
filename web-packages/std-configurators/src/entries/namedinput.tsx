import { ThemeProvider } from "@mui/material";
import { EditorField, GraphSetter, StaticEditor, Task, TaskCLSConfigurator, TaskCLSReactRendererMixin, TaskConfiguratorContext, compareIOIgnorePaths, createCLSConfigurator, extractObjectPathValues, parseMetadataField, theme } from "@streamtasks/core";
import { ReactNode } from "react";
import { v4 as uuidv4 } from "uuid";
import { z } from "zod";

const editorFields: EditorField[] = [
    {
        type: "text",
        key: "name",
        label: "topic name",
    },
    {
        type: "kvoptions",
        key: "metadata",
        label: "Metadata"
    }
];

export class NamedInputConfigurator extends TaskCLSReactRendererMixin(TaskCLSConfigurator) {
    constructor(context: TaskConfiguratorContext, task?: Task) {
        super(context, task ?? {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: parseMetadataField(context.taskHost.metadata, "cfg:label", z.string(), true),
            config: { name: "named topic", out_topic: context.idGenerator() },
            inputs: [],
            outputs: [{ key: "out_topic", topic_id: 0 }]
        });
        if (task === undefined) {
            this.applyConfig();
        }
    }

    public rrenderEditor(onUpdate: () => void): ReactNode {
        return (
            <ThemeProvider theme={theme}>
                <StaticEditor data={this.config} fields={editorFields} onUpdated={() => {
                    this.applyConfig();
                    onUpdate();
                }} />
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
        for (const key of Object.keys(this.outputs[0]).filter(k => !compareIOIgnorePaths.has(k) && !pathValues.has("config.metadata." + k))) {
            setter.set(`config.metadata.${key}`, this.config.metadata[key]);
        }

        setter.apply();
    }

    private getGraph() {
        const setter = new GraphSetter(this.task);

        setter.addEdge("outputs.0.label", "config.name");
        setter.addEdge("outputs.0.topic_id", "config.out_topic");
        setter.addEdgeGenerator("config.metadata", (subPath) => {
            if (compareIOIgnorePaths.has(subPath)) return [];
            return [`outputs.0.${subPath}`];
        });

        return setter;
    }
}

const configurator = createCLSConfigurator((context, task) => new NamedInputConfigurator(context, task));
export default configurator;