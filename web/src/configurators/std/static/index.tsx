import { z } from "zod";
import { TaskConfigurator, TaskConfiguratorContext, Task, TaskOutput } from "../../../types/task";
import { v4 as uuidv4 } from "uuid";
import { getMetadataKeyDiffs } from "../../../lib/task";
import { ReactEditorRenderer as ReactRenderer } from "../../../lib/conigurator";
import { StaticEditor } from "../../../StaticEditor";
import { applyConfigToIOMetadata, applyOutputIdsToConfig, compareIgnoreMetadataKeys, connectMirrorIO, connectWithConfigOverwrite, createTaskFromContext, getCFGFieldEditorFields, getCFGFieldInputs, getCFGFieldOutputs, getDisabledFields } from "./utils";

const reactRenderer = new ReactRenderer();
const configurator: TaskConfigurator = {
    connect: (task: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
        const targetInput = task.inputs.find(input => input.key === key);
        if (!targetInput) {
            throw new Error("Input not found!"); // should not happen during normal operation
        }

        if (!output) {
            targetInput.topic_id = undefined;
        }
        else {
            const diffs = getMetadataKeyDiffs(output, targetInput, compareIgnoreMetadataKeys);
            if (diffs.length == 0) {
                targetInput.topic_id = output.topic_id;
            }
            else {
                if (!connectWithConfigOverwrite(task, targetInput, output, diffs, context)) {
                    if (!connectMirrorIO(task, targetInput, output, diffs, context)) {
                        if (targetInput.topic_id === output.topic_id) {
                            targetInput.topic_id = undefined;
                        }
                    }
                }
            }
        }
        task.config[targetInput.key] = targetInput.topic_id
        return task;
    },
    create: createTaskFromContext,
    renderEditor: (task: Task, element: HTMLElement, context: TaskConfiguratorContext) => {
        const mainFields = getCFGFieldEditorFields(context) ?? [];
        const videoFields = getCFGFieldEditorFields(context, "cfg:videoeditorfields") ?? [];
        const audioFields = getCFGFieldEditorFields(context, "cfg:audioeditorfields") ?? [];
        reactRenderer.render(element, <StaticEditor task={task} fields={mainFields} />)
    }
};

export default configurator;