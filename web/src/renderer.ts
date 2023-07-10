import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Connection, Node } from "./types";

const streamsTopOffset = 25;
const streamsBottomOffset = streamsTopOffset;
const streamHeight = 30;
const xOffset = streamHeight / 2;
const streamCircleRadius = 8;
const outlineColor = 0x333333;
const outlineWidth = 2;
const labelEdgeOffset = streamCircleRadius + 5;
const minLabelSpace = 20;

export class NodeRenderer {
    private group: PIXI.Container;
    private task: Node;
    private streamLabelTextStyle: PIXI.TextStyle;

    constructor(task: Node) {
        this.task = task;
        this.group = new PIXI.Container();
        this.streamLabelTextStyle = new PIXI.TextStyle({
            fontFamily: 'Arial',
            fontSize: 13,
            fill: '#000000',
            wordWrap: false
        });
    }

    public init(container: Viewport) {
        container.addChild(this.group);
        this.group.interactive = true;

        let pointerDown = false;
        const resumeDrag = () => {
            if (pointerDown) {
                container.plugins.resume('drag');
                pointerDown = false;
            }
        }
        this.group.on('pointerdown', (e) => {
            pointerDown = true;
            container.plugins.pause('drag');
        });
        this.group.on('pointerout', resumeDrag);
        this.group.on('pointerup', resumeDrag);
        
        // allow moving the task
        this.group.on('pointermove', (e) => {
            if (pointerDown) {
                const currentPosition = this.task.getPosition();
                const newPosition = {
                    x: currentPosition.x + e.movementX / container.scale.x,
                    y: currentPosition.y + e.movementY / container.scale.y
                };
                this.task.setPosition(newPosition.x, newPosition.y);
                this.group.position.set(newPosition.x, newPosition.y);
            }
        });
    }

    public render() {
        const pos = this.task.getPosition();
        this.group.position.set(pos.x, pos.y);

        const streamLabelTextStyle = new PIXI.TextStyle({
            fontFamily: 'Arial',
            fontSize: 12,
            fill: '#000000',
            // disable wrapping
            wordWrap: false
        });

        // rect width and height
        const streamGroups = this.task.getConnectionGroups();
        const ioHeight = streamGroups.map(sg => Math.max(sg.inputs.length, sg.outputs.length)).reduce((a, b) => a + b, 0);
        const rectHeight = ioHeight * streamHeight + streamsBottomOffset + streamsTopOffset;

        const inputLabelMaxSize = this.measureStreamLabelSizes(streamGroups.map(sg => sg.inputs).reduce((a, b) => a.concat(b), []));
        const outputLabelMaxSize = this.measureStreamLabelSizes(streamGroups.map(sg => sg.outputs).reduce((a, b) => a.concat(b), []));

        const rectWidth = inputLabelMaxSize.width + outputLabelMaxSize.width + minLabelSpace + labelEdgeOffset * 2;

        // gray rect with rounded corners
        const containerRect = new PIXI.Graphics();
        containerRect.lineStyle(outlineWidth, outlineColor);
        containerRect.beginFill(0xffffff);
        containerRect.drawRoundedRect(xOffset, 0, rectWidth, rectHeight, streamCircleRadius);
        containerRect.endFill();
        this.group.addChild(containerRect);

        // draw streams
        let heightIndex = 0;
        for (const streamGroup of streamGroups) {
            for (let i = 0; i < streamGroup.inputs.length; i++) {
                const stream = streamGroup.inputs[i];
                const yOffsetCenter = (heightIndex + i + 0.5) * streamHeight + streamsTopOffset;

                // draw a circle on the edge of the rect
                const circle = this.createStreamCircle(stream);
                circle.position.set(xOffset, yOffsetCenter);

                // draw the stream label
                const label = new PIXI.Text(stream.label, streamLabelTextStyle);
                label.position.set(xOffset + labelEdgeOffset, yOffsetCenter - label.height / 2);
                label.resolution = 2;

                this.group.addChild(circle);
                this.group.addChild(label);
            }
            for (let i = 0; i < streamGroup.outputs.length; i++) {
                const stream = streamGroup.outputs[i];
                const yOffsetCenter = (heightIndex + i + 0.5) * streamHeight + streamsTopOffset;

                const circle = this.createStreamCircle(stream);
                circle.position.set(xOffset + rectWidth, yOffsetCenter);

                // draw the stream label
                const label = new PIXI.Text(stream.label, streamLabelTextStyle);
                label.position.set(xOffset + rectWidth - labelEdgeOffset - label.width, yOffsetCenter - label.height / 2);
                label.resolution = 2;

                this.group.addChild(circle);
                this.group.addChild(label);
            }
            heightIndex += Math.max(streamGroup.inputs.length, streamGroup.outputs.length);
        }
    }

    private createStreamCircle(stream: Connection) {
        const circle = new PIXI.Graphics();
        circle.lineStyle(outlineWidth, outlineColor);
        circle.beginFill(this.getStreamColor(stream));
        circle.drawCircle(0, 0, streamCircleRadius);
        circle.endFill();
        return circle;
    }

    private measureStreamLabelSizes(streams: Connection[]) {
        let maxWidth = 0;
        let maxHeight = 0;
        for (const stream of streams) {
            const size = PIXI.TextMetrics.measureText(stream.label, this.streamLabelTextStyle);
            if (size.width > maxWidth) {
                maxWidth = size.width;
            }
            if (size.height > maxHeight) {
                maxHeight = size.height;
            }
        }
        return { width: maxWidth, height: maxHeight };
    }

    private getStreamColor(stream: Connection) {
        const hash = objectHash(["5", stream.config]);
        let r = parseInt(hash.substr(0, 2), 16) / 255;
        let g = parseInt(hash.substr(2, 2), 16) / 255;
        let b = parseInt(hash.substr(4, 2), 16) / 255;

        // brighten the color to be at least 0.5
        const brighten = 0.6 / ((r+g+b) / 3);
        r = Math.min(1, r * brighten);
        g = Math.min(1, g * brighten);
        b = Math.min(1, b * brighten);

        return (r * 255) << 16 ^ (g * 255) << 8 ^ (b * 255) << 0;
    }
}

export class NodeEditorRenderer {
    private viewport?: Viewport;
    private app?: PIXI.Application;

    public addTask(task: Node) {
        const taskRenderer = new NodeRenderer(task);
        taskRenderer.init(this.viewport!);
        taskRenderer.render();
    }

    public mount(container: HTMLElement) {
        this.app = new PIXI.Application({
            width: container.clientWidth,
            height: container.clientHeight,
            backgroundColor: 0xeeeeee,
            antialias: true,
            autoDensity: true,
        });
        
        this.viewport = new Viewport({
            worldWidth: 1000,
            worldHeight: 1000,
            events: this.app.renderer.events,
        });
        this.viewport
            .drag()
            .pinch()
            .wheel()
            .decelerate()

        this.app.stage.addChild(this.viewport);
        
        container.appendChild(this.app.view as HTMLCanvasElement);
        const hostResizeObserver = new ResizeObserver(() => {
            this.app?.renderer.resize(container.clientWidth, container.clientHeight);
            this.viewport?.resize(container.clientWidth, container.clientHeight, 1000, 1000);
        });
        hostResizeObserver.observe(container);
    }
}