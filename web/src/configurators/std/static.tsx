import { TaskConfiguratorContext, Task } from "../../types/task";
import { getMetadataKeyDiffs } from "../../lib/task";
import { TaskCLSConfigurator, TaskCLSReactRendererMixin, createCLSConfigurator } from "../../lib/conigurator";
import { StaticEditor } from "../../StaticEditor";
import { ReactNode } from "react";
import { EditorFieldsModel } from "../../StaticEditor/types";
import { GraphSetter, compareIgnoreMetadataKeys, parseMetadataField } from "../../lib/conigurator/helpers";
import { getFieldValidator } from "../../StaticEditor/util";
import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import { MetadataModel, TaskPartialInputModel } from "../../model/task";

export class StaticCLSConfigurator extends TaskCLSReactRendererMixin(TaskCLSConfigurator) {
    protected get editorFields() {
        return this.parseMetadataField("cfg:editorfields", EditorFieldsModel, false) ?? [];
    }

    constructor(context: TaskConfiguratorContext, task?: Task) {
        super(context, task ?? {
            id: uuidv4(),
            task_host_id: context.taskHost.id,
            label: parseMetadataField(context.taskHost.metadata, "cfg:label", z.string(), true),
            config: parseMetadataField(context.taskHost.metadata, "cfg:config", z.record(z.any())) ?? {},
            inputs: parseMetadataField(context.taskHost.metadata, "cfg:inputs", z.array(TaskPartialInputModel)) ?? [],
            outputs: (parseMetadataField(context.taskHost.metadata, "cfg:outputs", z.array(MetadataModel)) ?? [])
                .map(o => ({...o, topic_id: context.idGenerator()})),
        });
        this.applyOutputIds();
        this.applyConfig();
    }

    public rrenderEditor(onUpdate: () => void): ReactNode {
        const cs = this.getGraph();
        return <StaticEditor data={this.config} fields={this.editorFields} onUpdated={() => {
            this.applyConfig();
            onUpdate();
        }} disabledFields={cs.getDisabledFields("config", true)} />
    }
    public connect(key: string, output?: (Record<string, string | number | boolean | undefined> & { topic_id: number; }) | undefined): void | Promise<void> {
        const [input, inputIndex] = this.getInput(key, true);
        if (!output) {
            input.topic_id = undefined;
        }
        else {
            const diffs = getMetadataKeyDiffs(input, output, compareIgnoreMetadataKeys);
            const setter = this.getGraph();
            setter.enable(`inputs.${inputIndex}`);
            setter.set(`inputs.${inputIndex}.topic_id`, output.topic_id);
            for (const diff of diffs) {
                setter.set(`inputs.${inputIndex}.${diff}`, output[diff]);
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
    
    protected applyConfig() {
        const setter = this.getGraph();
        Object.entries(this.config).forEach(([ k, v ]) => setter.set(`config.${k}`, v))
        this.setFields(setter.validate())
    }
    
    protected getGraph() {
        const setter = new GraphSetter();
        for (const field of this.editorFields) {
            const validator = getFieldValidator(field);
            setter.constrainValidator(`config.${field.key}`, v => validator.safeParse(v).success)
        }

        const config2InputMap = this.parseMetadataField("cfg:config2inputmap", z.record(z.string(), z.record(z.string(), z.string()))) ?? {};
        for (const [inputKey, map] of Object.entries(config2InputMap)) {
            const inputIndex = this.inputs.findIndex(input => input.key === inputKey);
            if (inputIndex !== -1) {
                for (const [configKey, inputMetadataKey] of Object.entries(map)) {
                    setter.addEquals(`inputs.${inputIndex}.${inputMetadataKey}`, `config.${configKey}`);
                }
            }
        }

        this.inputs.forEach((input, idx) => {
            setter.addEquals(`inputs.${idx}.topic_id`, `config.${input.key}`);
            if (input.topic_id !== undefined) {
                setter.disable(`inputs.${idx}`);
            }
        })
        
        const config2OutputMap = this.parseMetadataField("cfg:config2outputmap", z.array(z.record(z.string(), z.string()).optional())) ?? [];
        config2OutputMap.forEach((map, outputIndex) => {
            if (map) {
                for (const [configKey, outputMetadataKey] of Object.entries(map)) {
                    setter.addEquals(`outputs.${outputIndex}.${outputMetadataKey}`, `config.${configKey}`);
                }
            }
        });

        const outputConfigKeys = this.parseMetadataField("cfg:outputkeys", z.array(z.string().optional())) ?? [];
        outputConfigKeys.forEach((configKey, outputIndex) => {
            if (this.outputs[outputIndex]) {
                setter.addEquals(`config.${configKey}`, `outputs.${outputIndex}.topic_id`);
            }
        });

        return setter;
    }
}

const configurator = createCLSConfigurator((context, task) => new StaticCLSConfigurator(context, task));
export default configurator;