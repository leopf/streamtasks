import { Root, createRoot } from "react-dom/client";
import React from "react";
import { Task } from "../types/task";

export class ReactEditorRenderer {
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