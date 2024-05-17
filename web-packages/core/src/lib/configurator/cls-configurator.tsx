import { RunningTask, Task, TaskConfigurator, TaskConfiguratorContext, TaskDisplayOptions, TaskInput, TaskInstance, TaskOutput } from "../../types/task";
import cloneDeep from "clone-deep";
import objectPath from "object-path";

export abstract class TaskCLSConfigurator {
    
    public taskInstance?: TaskInstance;

    private _task: Task;
    public get task() {
        return cloneDeep(this._task);
    }
    
    public get id() {
        return this._task.id;
    }
    
    public get config() {
        return this._task.config;
    }
    
    public get inputs() {
        return this._task.inputs;
    }
    public set inputs(v: TaskInput[]) {
        this._task.inputs = v;
    }
    public get outputs() {
        return this._task.outputs;
    }
    public set outputs(v: TaskOutput[]) {
        this._task.outputs = v;
    }
    
    public get taskHost() {
        return this.context.taskHost;
    }
    
    public get newId() {
        return this.context.idGenerator
    }

    private context: TaskConfiguratorContext;
    
    constructor(context: TaskConfiguratorContext, task: Task) {
        this._task = task;
        this.context = context; 
    }

    public abstract connect(key: string, output?: TaskOutput): void | Promise<void>;
    public renderEditor(element: HTMLElement): void {}
    public renderDisplay(element: HTMLElement, options: TaskDisplayOptions): void {}
    public update(task: Task, context: TaskConfiguratorContext) {
        if (this.id != task.id) throw new Error("Task ids do not match!");
        this._task = task;
        this.context = context;
    }

    public getOutput(topic_id: number, withIndex: true): [TaskOutput, number];
    public getOutput(topic_id: number, withIndex: false): TaskOutput;
    public getOutput(topic_id: number, withIndex?: boolean): TaskOutput | [TaskOutput, number] {
        const outputIndex = this._task.outputs.findIndex(i => i.topic_id === topic_id);
        if (outputIndex === -1) throw new Error("Output not found");
        const output = this._task.outputs[outputIndex]; // TS fix
        if (withIndex) {
            return [output, outputIndex];
        }
        else {
            return output;
        }
    }

    public getInput(key: string, withIndex: true): [TaskInput, number];
    public getInput(key: string, withIndex: false): TaskInput;
    public getInput(key: string, withIndex: boolean = false): TaskInput | [TaskInput, number] {
        const inputIndex = this._task.inputs.findIndex(i => i.key === key);
        if (inputIndex === -1) throw new Error("Input not found");
        const input = this._task.inputs[inputIndex]; // TS fix
        if (withIndex) {
            return [input, inputIndex];
        }
        else {
            return input;
        }
    } 

    protected setFields(fields: Record<string, any>) {
        for (const [k, v] of Object.entries(fields)) {
            objectPath.set(this._task, k, v);
        }
    }
}

export function createCLSConfigurator(factory: (context: TaskConfiguratorContext, task?: Task) => TaskCLSConfigurator): TaskConfigurator {
    const cfgs = new Map<string, TaskCLSConfigurator>(); // TODO cleanup
    const getOrCreateTask = (context: TaskConfiguratorContext, task?: Task) => {
        let clsTask = task && cfgs.get(task.id);
        if (!clsTask) {
            clsTask = factory(context, task);
            cfgs.set(task?.id ?? clsTask.id, clsTask);
        }
        else {
            clsTask.update(task!, context);
        }
        return clsTask;
    };

    return {
        create: (context: TaskConfiguratorContext) => {
            const clsTask = getOrCreateTask(context);
            return clsTask.task;
        },
        connect: async (task: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
            const clsTask = getOrCreateTask(context, task);
            clsTask.taskInstance = undefined;
            await clsTask.connect(key, output);
            return clsTask.task;
        },
        renderEditor: async (task: Task, element: HTMLElement, context: TaskConfiguratorContext) => {
            const clsTask = getOrCreateTask(context, task);
            clsTask.taskInstance = undefined;
            clsTask.renderEditor(element);
        },
        renderDisplay: async (task: RunningTask, element: HTMLElement, options: TaskDisplayOptions, context: TaskConfiguratorContext) => {
            const clsTask = getOrCreateTask(context, task);
            clsTask.taskInstance = task.taskInstance;
            clsTask.renderDisplay(element, options);
        }
    };
}