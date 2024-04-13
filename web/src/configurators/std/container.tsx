import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import { StaticEditor } from "../../StaticEditor";
import { getMetadataKeyDiffs } from "../../lib/task";
import { TaskConfigurator, Task, TaskOutput, TaskConfiguratorContext } from "../../types/task";
import { ReactEditorRenderer } from "../../lib/conigurator";
import { compareIgnoreMetadataKeys, connectWithConfigOverwrite, connectMirrorIO, getCFGFieldInputs, getCFGFieldOutputs, applyOutputIdsToConfig, applyConfigToIOMetadata, getCFGFieldEditorFields, getDisabledFields, createTaskFromContext } from "./static/utils";

const reactRenderer = new ReactEditorRenderer();
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
        const fields = getCFGFieldEditorFields(context);
        if (!fields) return;
        reactRenderer.render(element, <StaticEditor task={task} fields={fields} beforeUpdate={() => {
            applyConfigToIOMetadata(task, context);
        }} disabledFields={getDisabledFields(task, context)} />)
    }
};

export default configurator;