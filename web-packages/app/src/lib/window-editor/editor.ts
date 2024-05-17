import EventEmitter from "eventemitter3";
import { HTMLViewport } from "../html-viewport";
import cloneDeep from "clone-deep";
import { ManagedTask } from "@streamtasks/core";
import { DeploymentManager } from "../../state/deployment-manager";
import { DashboardWindow } from "../../types/dashboard";

const resizeElementSize = 3;
const windowHeaderHeight = 20;
const headerFontSize = windowHeaderHeight - 8;
const headerHSpacing = windowHeaderHeight / 4;

type PointerMoveActionResize = { type: "resize", x: number, y: number, w: number, h: number }
type PointerMoveAction = PointerMoveActionResize | { type: "move" }

export class WindowRenderer extends EventEmitter<{
    "updated": [DashboardWindow],
    "remove": [DashboardWindow],
}> {
    public element: HTMLDivElement;

    private _data: DashboardWindow;
    public get data() {
        return { ...this._data };
    }
    
    private viewport: HTMLViewport;
    private labelEl: HTMLElement;
    private contentEl: HTMLElement;
    private task: ManagedTask | undefined;
    private rerenderTaskDataHandler = () => this.rerenderTaskData();
    private windowPointerMoveHandler = (e: PointerEvent) => this.windowPointerMove(e);
    private windowPointerUpHandler = () => this.pointerMoveAction = undefined;

    private pointerMoveAction?: PointerMoveAction;

    constructor(data: DashboardWindow, task: ManagedTask | undefined, viewport: HTMLViewport) {
        super();
        this.viewport = viewport;
        this._data = data;
        this.task = task;
        this.element = document.createElement("div");
        this.element.style.position = "absolute";
        this.element.style.backgroundColor = task ? "#1976d2" : "red";
        this.element.style.zIndex = String(viewport.host.childElementCount + 10);

        this.contentEl = document.createElement("div");
        this.contentEl.style.position = "absolute";
        this.contentEl.style.top = (resizeElementSize + windowHeaderHeight) + "px";
        this.contentEl.style.bottom = resizeElementSize + "px";
        this.contentEl.style.left = resizeElementSize + "px";
        this.contentEl.style.right = resizeElementSize + "px";
        this.contentEl.style.backgroundColor = "#fff";
        this.contentEl.style.overflow = "hidden";
        this.contentEl.style.padding = "0.5rem";

        const headerEl = document.createElement("div");
        headerEl.style.position = "absolute";
        headerEl.style.top = resizeElementSize + "px";
        headerEl.style.left = resizeElementSize + "px";
        headerEl.style.right = resizeElementSize + "px";
        headerEl.style.height = windowHeaderHeight + "px";
        headerEl.style.paddingBottom = resizeElementSize + "px";
        headerEl.style.boxSizing = "border-box";
        headerEl.style.cursor = "move";
        headerEl.style.display = "flex";
        headerEl.style.flexDirection = "row";
        headerEl.style.alignItems = "center";
        headerEl.addEventListener("pointerdown", () => this.startPointerMoveAction({ type: "move" }));

        this.labelEl = document.createElement("div");
        this.labelEl.style.marginLeft = headerHSpacing + "px";
        this.labelEl.style.fontSize = headerFontSize + "px";
        this.labelEl.style.lineHeight = headerFontSize + "px";
        this.labelEl.style.fontWeight = "bold";
        this.labelEl.style.color = "white";
        headerEl.appendChild(this.labelEl);

        const headerSpacer = document.createElement("div");
        headerSpacer.style.flex = "1";

        headerEl.appendChild(headerSpacer);

        const closeElement = document.createElement("div");
        closeElement.style.color = "#fff";
        closeElement.style.marginRight = headerHSpacing + "px";
        closeElement.style.userSelect = "none";
        closeElement.style.cursor = "pointer";
        closeElement.style.height = headerFontSize + "px";
        closeElement.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="100%" height="100%" viewBox="0 0 30 30" fill="white" style="display:block;">
            <path d="M 7 4 C 6.744125 4 6.4879687 4.0974687 6.2929688 4.2929688 L 4.2929688 6.2929688 C 3.9019687 6.6839688 3.9019687 7.3170313 4.2929688 7.7070312 L 11.585938 15 L 4.2929688 22.292969 C 3.9019687 22.683969 3.9019687 23.317031 4.2929688 23.707031 L 6.2929688 25.707031 C 6.6839688 26.098031 7.3170313 26.098031 7.7070312 25.707031 L 15 18.414062 L 22.292969 25.707031 C 22.682969 26.098031 23.317031 26.098031 23.707031 25.707031 L 25.707031 23.707031 C 26.098031 23.316031 26.098031 22.682969 25.707031 22.292969 L 18.414062 15 L 25.707031 7.7070312 C 26.098031 7.3170312 26.098031 6.6829688 25.707031 6.2929688 L 23.707031 4.2929688 C 23.316031 3.9019687 22.682969 3.9019687 22.292969 4.2929688 L 15 11.585938 L 7.7070312 4.2929688 C 7.5115312 4.0974687 7.255875 4 7 4 z"></path>
        </svg>`;
        closeElement.addEventListener("click", () => this.emit("remove", this.data))

        headerEl.appendChild(closeElement);

        [
            headerEl, this.contentEl,
            this.createSideResizeElement({ type: "resize", w: 1, h: 0, x: 0, y: 0 }), // right
            this.createSideResizeElement({ type: "resize", x: 1, w: -1, h: 0, y: 0 }), // left
            this.createSideResizeElement({ type: "resize", h: 1, x: 0, y: 0, w: 0 }), // bottom
            this.createSideResizeElement({ type: "resize", y: 1, h: -1, w: 0, x: 0 }), // top
            this.createCornerResizeElement({ type: "resize", h: 1, w: 1, x: 0, y: 0 }), // bottom right
            this.createCornerResizeElement({ type: "resize", h: -1, w: -1, x: 1, y: 1 }), // top left
            this.createCornerResizeElement({ type: "resize", h: -1, w: 1, x: 0, y: 1 }), // top right
            this.createCornerResizeElement({ type: "resize", h: 1, w: -1, x: 1, y: 0 }), // bottom left
        ].forEach(el => this.element.appendChild(el));
        this.reposition();
        this.rerenderTaskData();
        this.task?.addListener("updated", this.rerenderTaskDataHandler);
        window.addEventListener("pointermove", this.windowPointerMoveHandler);
        window.addEventListener("pointerup", this.windowPointerUpHandler);
    }

    public destroy() {
        this.element.remove();
        this.removeAllListeners();
        this.task?.removeListener("updated", this.rerenderTaskDataHandler);
        window.removeEventListener("pointermove", this.windowPointerMoveHandler);
        window.removeEventListener("pointerup", this.windowPointerUpHandler);
    }

    private createCornerResizeElement(action: PointerMoveActionResize) {
        const el = document.createElement("div");
        el.style.position = "absolute";
        
        if (action.x !== 0) {
            el.style.left = "0";    
        }
        else {
            el.style.right = "0";    
        }

        if (action.y !== 0) {
            el.style.top = "0";    
        }
        else {
            el.style.bottom = "0";    
        }

        el.style.height = resizeElementSize + "px";
        el.style.width = resizeElementSize + "px";
        el.style.cursor = ((action.x !== 0) == (action.y !== 0)) ?  "nw-resize" : "ne-resize";
        el.addEventListener("pointerdown", () => this.startPointerMoveAction(action));
        return el
    }
    private createSideResizeElement(action: PointerMoveActionResize) {
        const el = document.createElement("div");
        el.style.position = "absolute";

        if (action.w !== 0) {
            el.style.bottom = resizeElementSize + "px";
            el.style.top = resizeElementSize + "px";
            el.style.width = resizeElementSize + "px";

            if (action.x !== 0) {
                el.style.left = "0";
            }
            else {
                el.style.right = "0";
            }
        }
        if (action.h !== 0) {
            el.style.left = resizeElementSize + "px";
            el.style.right = resizeElementSize + "px";
            el.style.height = resizeElementSize + "px";

            if (action.y !== 0) {
                el.style.top = "0";
            }
            else {
                el.style.bottom = "0";
            }
        }

        el.style.cursor = action.w !== 0 ?  "ew-resize" : "ns-resize";
        el.addEventListener("pointerdown", () => this.startPointerMoveAction(action));
        return el
    }
    private startPointerMoveAction(action: PointerMoveAction) {
        this.pointerMoveAction = action;
        this.viewport.disableDrag();
    }
    private windowPointerMove(e: PointerEvent) {
        if (!this.pointerMoveAction) return;
        const mx = e.movementX / this.viewport.zoom;
        const my = e.movementY / this.viewport.zoom;

        if (this.pointerMoveAction.type === "move") {
            this.updateData({
                ...this._data,
                x: this._data.x + mx,
                y: this._data.y + my,
            });
        }
        else if (this.pointerMoveAction.type === "resize") {
            this.updateData({
                ...this._data,
                x: this._data.x + mx * this.pointerMoveAction.x,
                y: this._data.y + my * this.pointerMoveAction.y,
                width: this._data.width + mx * this.pointerMoveAction.w,
                height: this._data.height + my * this.pointerMoveAction.h,
            });
        }
    }
    private rerenderTaskData() {
        if (this.task) {
            this.labelEl.innerText = this.task.label;
            if (this.task.taskInstance) {
                this.task.renderDisplay(this.contentEl, { context: "dashboard" });
            }
            else {
                this.contentEl.innerHTML = `<div style="display: flex; align-items: center; justify-content: center;width: 100%; height: 100%;">
                    <div style="font-size: 1.5rem; font-weight: bold; color: #888;">not running!</div>
                </div>`;
            }
        }
        else {
            this.labelEl.innerText = "task not found";
        }
    }

    private updateData(data: DashboardWindow) {
        this._data = data;
        this.reposition();
        this.emit("updated", { ...data });
    }

    private reposition() {
        this.element.style.left = this._data.x + "px";
        this.element.style.top = this._data.y + "px";
        this.element.style.width = Math.max(this._data.width, resizeElementSize * 2) + "px";
        this.element.style.height = Math.max(this._data.height, resizeElementSize * 2 + windowHeaderHeight) + "px";
    }
}

export class WindowEditorRenderer extends EventEmitter<{
    "updated": [DashboardWindow],
    "removed": [DashboardWindow]
}> {
    public viewport = new HTMLViewport();
    private deployment: DeploymentManager;
    private windows: WindowRenderer[] = [];

    constructor(deployment: DeploymentManager) {
        super();
        this.deployment = deployment;
    }

    public addWindow(window: DashboardWindow) {
        const renderer = new WindowRenderer(cloneDeep(window), this.deployment.tasks.get(window.task_id), this.viewport);
        renderer.addListener("updated", window => this.emit("updated", window));
        renderer.addListener("remove", window => this.removeWindow(window.task_id));
        this.windows.push(renderer);
        this.viewport.host.appendChild(renderer.element);
        this.emit("updated", window);
    }
    public removeWindow(taskId: string) {
        const windows = this.windows.filter(window => window.data.task_id === taskId);
        for (const window of windows) {   
            window.destroy();
            this.emit("removed", window.data);
        }
        this.windows = this.windows.filter(w => w.data.task_id !== taskId);
    }

    public mount(element: HTMLDivElement) {
        this.viewport.mount(element);
    }
    public destroy() {
        this.viewport.unmount();
        this.windows.forEach(w => w.destroy());
        this.windows = [];
    }
}