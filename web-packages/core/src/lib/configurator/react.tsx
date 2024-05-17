import { Root, createRoot } from "react-dom/client";
import { Task, TaskDisplayOptions } from "../../types";
import React from "react";

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
            innerContainer.style.width = "100%";
            innerContainer.style.height = "100%";
            container.appendChild(innerContainer);
            root = createRoot(innerContainer);
            this.roots.set(innerContainer, root);
        }
        root.render(element);
    }
}

type Constructor<T> = abstract new (...args: any[]) => T;
type TaskCfgConstructor = Constructor<{ task: Task }>;

export function TaskCLSReactRendererMixin<TBase extends TaskCfgConstructor>(Base: TBase) {
    abstract class _TaskCLSReactRenderer extends Base {
        public editorRenderer = new ReactElementRenderer();
        public displayRenderer = new ReactElementRenderer();
        
        public rrenderDisplay(options: TaskDisplayOptions): React.ReactNode { return null; }
        public renderDisplay(element: HTMLElement, options: TaskDisplayOptions): void {
            this.displayRenderer.render(element, <React.Fragment key={this.task.id}>{this.rrenderDisplay(options)}</React.Fragment>);
        }

        public rrenderEditor(onUpdate: () => void): React.ReactNode { return null; }
        public renderEditor(element: HTMLElement): void {
            this.editorRenderer.render(element, <React.Fragment key={this.task.id}>{this.rrenderEditor(() => {
                element.dispatchEvent(new CustomEvent("task-instance-updated", { detail: this.task, bubbles: true }));
            })}</React.Fragment>);
        }
    }
    return _TaskCLSReactRenderer;
}
