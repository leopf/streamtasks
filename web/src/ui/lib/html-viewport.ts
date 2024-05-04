import { Point } from "./point";

export class HTMLViewport {
    private _translate: Point = { x: 0, y: 0 };
    public get translate(): Point {
        return this._translate;
    }
    public set translate(v: Point) {
        this._translate = { ...v };
        this.updateHost();
    }

    private _zoom: number = 1;
    public get zoom(): number {
        return this._zoom;
    }
    public set zoom(v: number) {
        this._zoom = v;
        this.updateHost();
    }

    public get localCenter() {
        return this.toLocal({ x: this._container.clientWidth / 2, y: this._container.clientHeight / 2 });
    }

    private _host: HTMLDivElement;
    public get host() {
        return this._host;
    }
    private _container: HTMLDivElement;
    public get container() {
        return this._container;
    }

    public disableDrag: boolean = false;

    constructor() {
        this._host = document.createElement("div");
        this._host.style.position = "absolute";
        this._host.style.top = "0";
        this._host.style.left = "0";
        this.updateHost();

        this._container = document.createElement("div");
        this._container.style.width = "100%";
        this._container.style.height = "100%";
        this._container.style.position = "relative";
        this._container.style.overflow = "hidden";
        this._container.style.userSelect = "none";
        this._container.style.touchAction = "none";
        this._container.appendChild(this._host);

        this.setupEvents();
    }

    public toLocal(p: Point) {
        return { x: (p.x - this.translate.x) / this.zoom, y: (p.y - this.translate.y) / this.zoom }
    }

    public mount(element: HTMLElement) {
        if (element.children.length !== 0) throw new Error("The container should not have any children");
        element.appendChild(this._container);
    }

    public unmount() {
        this._container.remove();
    }

    private updateHost() {
        if (!this._host) return;
        this._host.style.transform = `translate(${this._translate.x}px, ${this._translate.y}px) scale(${this._zoom})`;
    }

    private setupEvents() {
        const getTouchPosition = (t: Touch) => <Point>{ x: t.clientX - this._container!.clientLeft, y: t.clientY - this._container!.clientTop }
        const getPointDistance = (a: Point, b: Point) => Math.sqrt(Math.pow(a.x - b.x, 2) + Math.pow(a.y - b.y, 2))

        let allowMove = false;
        let lastGestureTouches: Touch[] | undefined = undefined;

        this._container.addEventListener("pointerdown", () => allowMove = true);
        this._container.addEventListener("pointerup", () => allowMove = false);
        this._container.addEventListener("wheel", e => {
            const containerRect = this._container.getBoundingClientRect();

            this.changeZoom(1 - Math.max(-0.9, e.deltaY * 0.001), { x: e.clientX - containerRect.x, y: e.clientY - containerRect.y })
        });
        this._container.addEventListener("touchstart", e => {
            if (e.touches.length == 2) allowMove = false;
        });
        this._container.addEventListener("touchend", () => {
            lastGestureTouches = undefined;
        });
        this._container.addEventListener("touchmove", e => {
            if (e.touches.length !== 2) return;
            if (lastGestureTouches !== undefined) {
                const touches = [e.touches.item(0)!, e.touches.item(1)!];
                const newPoints: [Point, Point] = [getTouchPosition(touches[0]), getTouchPosition(touches[1])];

                const centerPoint: Point = {
                    x: (newPoints[0].x + newPoints[1].x) / 2,
                    y: (newPoints[0].y + newPoints[1].y) / 2,
                };

                const oldTouches: [Touch, Touch] = [
                    lastGestureTouches.find(o => o.identifier === touches[0].identifier)!,
                    lastGestureTouches.find(o => o.identifier === touches[1].identifier)!
                ];

                if (oldTouches.some(t => !t)) return;

                const oldPoints: [Point, Point] = [getTouchPosition(oldTouches[0]), getTouchPosition(oldTouches[1])];

                const oldDistance = getPointDistance(...oldPoints);
                const newDistance = getPointDistance(...newPoints);

                const relZoom = newDistance / oldDistance;
                this.changeZoom(relZoom, centerPoint);
            }
            lastGestureTouches = Array.from(e.touches);
        });
        this._container.addEventListener("pointermove", (e) => {
            if (!allowMove || this.disableDrag) return;
            e.preventDefault();
            this._translate.x += e.movementX;
            this._translate.y += e.movementY;
            this.updateHost();
        });
    }

    private changeZoom(relZoom: number, pos: Point) {
        this._translate.x -= (relZoom - 1) * (pos.x - this.translate.x);
        this._translate.y -= (relZoom - 1) * (pos.y - this.translate.y);
        this._zoom *= relZoom;
        this.updateHost();

    }
}