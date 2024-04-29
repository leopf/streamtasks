import { Root, createRoot } from "react-dom/client";
import React from "react";
import { Task, TaskConfigurator, TaskConfiguratorContext, TaskInput, TaskOutput } from "../types/task";
import { z } from "zod";

export class ReactElementRenderer {
    private roots: WeakMap<Node, Root> = new WeakMap();
    public render(container: HTMLElement, element: React.ReactNode) {
        let innerContainer = container.firstChild;

        let root: Root;
        if (innerContainer !== null && this.roots.has(innerContainer)) {
            root = this.roots.get(innerContainer)!;
        }
        else {
            while (container.firstChild) {
                container.removeChild(container.firstChild);
            }
            const innerContainer = document.createElement("div");
            container.appendChild(innerContainer);
            root = createRoot(innerContainer);
            this.roots.set(innerContainer, root);
        }
        root.render(element);
    }
}

export abstract class TaskCLSConfigurator {
    private context: TaskConfiguratorContext;
    
    constructor(context: TaskConfiguratorContext, task: Task) {
        this._task = task;
        this.context = context; 
    }

    private _task: Task;
    public get task() {
        return this._task;
    }

    public get id() {
        return this._task.id;
    }

    public get config() {
        return this._task.config;
    }

    public get taskHost() {
        return this.context.taskHost;
    }

    public get newId() {
        return this.context.idGenerator
    }

    public abstract connect(key: string, output?: TaskOutput): void | Promise<void>;
    public abstract renderEditor(element: HTMLElement): void;
    public update(task: Task, context: TaskConfiguratorContext) {
        if (this.id != task.id) throw new Error("Task ids do not match!");
        this._task = task;
        this.context = context;
    }

    public parseMetadataField<O>(key: string, model: z.ZodType<O>, force: true): O;
    public parseMetadataField<O>(key: string, model: z.ZodType<O>, force: false): O | undefined;
    public parseMetadataField<O>(key: string, model: z.ZodType<O>): O | undefined;
    public parseMetadataField<O>(key: string, model: z.ZodType<O>, force?: boolean) {
        const rawData = this.taskHost.metadata[key]; 
        if (rawData === undefined) {
            if (force) {
                throw new Error(`Field "${key}" not defined!`);
            }
            return undefined;
        }
        if (force) {
            return model.parse(rawData)
        }
        else {
            const res = model.safeParse(rawData);
            if (res.success) {
                return res.data;
            }
            return undefined;
        }
    }
    public getInput(key: string): TaskInput {
        const input = this._task.inputs.find(i => i.key === key);
        if (input === undefined) throw new Error("Input not found");
        return input; // TS fix
    } 
}

type Constructor = abstract new (...args: any[]) => TaskCLSConfigurator;

export function TaskCLSReactRendererMixin<TBase extends Constructor>(Base: TBase) {
    abstract class _TaskCLSReactRenderer extends Base {
        private _editorRenderer = new ReactElementRenderer();
        
        public abstract rrenderEditor(onUpdate: () => void): React.ReactNode;
        public renderEditor(element: HTMLElement): void {
            this._editorRenderer.render(element, <React.Fragment key={this.id}>{this.rrenderEditor(() => {
                element.dispatchEvent(new CustomEvent("task-instance-updated", { detail: this.task, bubbles: true }));
            })}</React.Fragment>);
        }
    }
    return _TaskCLSReactRenderer;
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
            return clsTask.task; // trick ts
        },
        connect: async (task: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
            const clsTask = getOrCreateTask(context, task);
            await clsTask.connect(key, output);
            return clsTask.task;
        },
        renderEditor: async (task: Task, element: HTMLElement, context: TaskConfiguratorContext) => {
            const clsTask = getOrCreateTask(context, task);
            clsTask.renderEditor(element);
        }
    };
}