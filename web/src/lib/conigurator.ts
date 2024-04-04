import { Root, createRoot } from "react-dom/client";
import React from "react";
import { Task } from "../types/task";

export class ReactEditorRenderer {
    private roots: WeakMap<HTMLElement, Root> = new WeakMap();
    public render(container: HTMLElement, element: React.ReactNode) {
        let root: Root;
        if (this.roots.has(container)) {
            root = this.roots.get(container)!;
        }
        else {
            root = createRoot(container);
            this.roots.set(container, root);
        }
        root.render(element);
    }
}