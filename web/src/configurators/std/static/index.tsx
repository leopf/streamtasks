import { TaskConfigurator, TaskConfiguratorContext, Task, TaskOutput } from "../../../types/task";
import { getMetadataKeyDiffs } from "../../../lib/task";
import { ReactElementRenderer as ReactRenderer } from "../../../lib/conigurator";
import { StaticEditor } from "../../../StaticEditor";
import { applyConfigToIOMetadata, compareIgnoreMetadataKeys, connectMirrorIO, connectWithConfigOverwrite, createTaskFromContext, elementEmitUpdate, getCFGFieldEditorFields, getDisabledFields } from "./utils";

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
        const fields = getCFGFieldEditorFields(context);
        if (!fields) return;
        reactRenderer.render(element, <StaticEditor key={task.id} data={task.config} fields={fields} onUpdated={() => {
            applyConfigToIOMetadata(task, context);
            elementEmitUpdate(element, task);
        }} disabledFields={getDisabledFields(task, context)} />)
    }
};

export default configurator;