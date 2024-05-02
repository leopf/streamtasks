import { TaskConfiguratorContext, Task } from "../../types/task";
import { getMetadataKeyDiffs } from "../../lib/task";
import { TaskCLSConfigurator, TaskCLSReactRendererMixin, createCLSConfigurator } from "../../lib/conigurator";
import { StaticEditor } from "../../StaticEditor";
import { ReactNode } from "react";
import { EditorFieldsModel } from "../../StaticEditor/types";
import { GraphSetter, compareIgnoreMetadataKeys, extractObjectPathValues, parseMetadataField } from "../../lib/conigurator/helpers";
import { getFieldValidator } from "../../StaticEditor/util";
import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import { MetadataModel, TaskPartialInputModel } from "../../model/task";

export class StaticCLSConfigurator extends TaskCLSReactRendererMixin(TaskCLSConfigurator) {
    protected get editorFields() {
        return parseMetadataField(this.taskHost.metadata, "cfg:editorfields", EditorFieldsModel, false) ?? [];
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
        if (!task) {
            this.applyOutputIds();
            this.applyConfig(false);
        }
    }

    public rrenderEditor(onUpdate: () => void): ReactNode {
        const cs = this.getGraph();
        return <StaticEditor data={this.config} fields={this.editorFields} onUpdated={() => {
            this.applyConfig(true);
            onUpdate();
        }} disabledFields={cs.getDisabledFields("config", true)} />
    }
    public connect(key: string, output?: (Record<string, string | number | boolean | undefined> & { topic_id: number; }) | undefined): void | Promise<void> {
        const [input, inputIndex] = this.getInput(key, true);
        const setter = this.getGraph();
        setter.enable(`inputs.${inputIndex}`);
        
        if (!output) {
            setter.set(`inputs.${inputIndex}.topic_id`, undefined);
            this.setFields(setter.validate());
        }
        else {
            const diffs = getMetadataKeyDiffs(input, output, compareIgnoreMetadataKeys);
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
    
    protected applyConfig(ignoreDisabled: boolean) {
        const setter = this.getGraph();
        const pathValues = extractObjectPathValues(this.config, "config.");
        if (ignoreDisabled) {
            Array.from(pathValues.keys()).forEach(k => {
                if (setter.isDisabled(k)) {
                    pathValues.delete(k);
                }
            })
        }

        for (const [k, v] of pathValues.entries()) {
            setter.set(k, v);
        }
        this.setFields(setter.validate())
    }
    
    protected getGraph() {
        const setter = new GraphSetter();
        for (const field of this.editorFields) {
            const validator = getFieldValidator(field);
            setter.constrainValidator(`config.${field.key}`, v => validator.safeParse(v).success)
        }

        const config2InputMap = parseMetadataField(this.taskHost.metadata, "cfg:config2inputmap", z.record(z.string(), z.record(z.string(), z.string()))) ?? {};
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
        
        const config2OutputMap = parseMetadataField(this.taskHost.metadata, "cfg:config2outputmap", z.array(z.record(z.string(), z.string()).optional())) ?? [];
        config2OutputMap.forEach((map, outputIndex) => {
            if (map) {
                for (const [configKey, outputMetadataKey] of Object.entries(map)) {
                    setter.addEquals(`outputs.${outputIndex}.${outputMetadataKey}`, `config.${configKey}`);
                }
            }
        });

        const outputConfigKeys = parseMetadataField(this.taskHost.metadata, "cfg:outputkeys", z.array(z.string().optional())) ?? [];
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