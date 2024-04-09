import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport';
import { Connection, Node, ConnectResult, InputConnection, NodeDisplayOptions, NodeRenderOptions, OutputConnection } from "./types";
import { Point } from '../../types/basic';
import EventEmitter from 'eventemitter3';

const appBackgroundColor = 0xeeeeee;
const paddingVertical = 10;
const nodeLabelHPadding = 20;
const streamsBottomOffset = paddingVertical;
const streamHeight = 30;
const streamCircleRadius = 8;
const outlineColor = 0x333333;
const outlineWidth = 2;
const xOffset = streamCircleRadius + outlineWidth / 2;
const labelEdgeOffset = streamCircleRadius + 5;
const minLabelSpace = 20;
const selectedNodeFillColor = 0xf0f6ff;

const connectionColorSamples = [
    0x6528F7,
    0xA076F9,
    0xFFE300,
    0xFF7800,
    0x0CCA98,
    0x00FFCC,
    0xF9A828,
    0xEEB76B,
    0xADE498,
    0xEDE682,
    0x91CA62,
    0xF1EBBB,
    0xF8B500,
    0xAA14F0,
    0xBC8CF2,
    0x6D67E4,
    0xFFC5A1,
    0xEF3F61,
    0xDF8931,
    0x85EF47,
    0xF9FD50
]

const ignoreFieldsForContentComparison = new Set([ "streamId", "label", "key", "id" ]);

export function getStreamColor(connection: Record<string, number | string | boolean>, ignoreFields: Set<string> = ignoreFieldsForContentComparison) {

    const newConnection = {...Object.fromEntries(Object.entries(connection).filter(([k, _]) => !ignoreFields.has(k)))};

    return connectionColorSamples[parseInt(objectHash([1, newConnection]).slice(0, 6), 16) % connectionColorSamples.length];
}

export class NodeRenderer {
    private group: PIXI.Container;
    private node: Node;
    private editor?: NodeEditorRenderer;

    private _relConnectorPositions = new Map<string | number, Point>();
    private _absuluteConnectorPositions = new Map<string | number, Point>();
    private connectorPositionsOutdated = true;

    private connectionLabelTextStyle = new PIXI.TextStyle({
        fontFamily: 'Arial',
        fontSize: 16,
        fill: '#000000',
        wordWrap: false
    });
    private nodeLabelTextStyle = new PIXI.TextStyle({
        fontFamily: 'Arial',
        fontSize: 18,
        fill: '#000000',
        wordWrap: false
    });

    public get id() {
        return this.node.id;
    }
    public get container() {
        return this.group;
    }
    private get isSelected() {
        return this.editor?.selectedNode === this;
    }
    private get fillColor() {
        return this.isSelected ? selectedNodeFillColor : 0xffffff;
    }

    public get connectorPositions() {
        if (this.connectorPositionsOutdated) {
            this._absuluteConnectorPositions.clear();
            for (const [refId, relPos] of this._relConnectorPositions) {
                this._absuluteConnectorPositions.set(refId, {
                    x: relPos.x + this.group.position.x,
                    y: relPos.y + this.group.position.y
                });
            }
            this.connectorPositionsOutdated = false;
        }
        return this._absuluteConnectorPositions;
    }

    public get inputs() {
        return this.node.inputs;
    }
    public get outputs() {
        return this.node.outputs;
    }

    public get position() {
        return this.node.position;
    }

    constructor(node: Node, editor?: NodeEditorRenderer) {
        this.node = node;
        this.node.on?.call(this.node, "updated", async () => await this.editor?.updateNode(this.id));
        this.editor = editor;

        this.group = new PIXI.Container();
        this.group.interactive = true;

        this.group.on('pointerdown', () => this.editor?.onPressNode(this.id));

        this.editor?.viewport.addChild(this.group);
    }

    public async connect(key: string, output?: OutputConnection) {
        return await this.node.connect(key, output);
    }

    public updatePosition(pos: Point) {
        this.node.position = { x: pos.x, y: pos.y };
        this.group.position.set(pos.x, pos.y);
        this.connectorPositionsOutdated = true;
    }

    public move(x: number, y: number) {
        const currentPosition = this.position;
        this.updatePosition({ x: currentPosition.x + x, y: currentPosition.y + y });
    }

    public destroy() {
        this.group.removeFromParent();
        this.group.destroy();
        this.node.destroy?.call(this.node);
    }

    public render() {
        this.group.removeChildren();
        this._relConnectorPositions.clear();
        this.updatePosition(this.position);

        const nodeLabel = new PIXI.Text(this.node.label, this.nodeLabelTextStyle);
        nodeLabel.resolution = 2;
        const streamsTopOffset = paddingVertical * 2 + nodeLabel.height;


        // rect width and height
        const ioHeight = Math.max(this.node.inputs.length, this.node.outputs.length)
        const rectHeight = ioHeight * streamHeight + streamsBottomOffset + streamsTopOffset;

        const inputLabelMaxSize = this.measureStreamLabelSizes(this.node.inputs);
        const outputLabelMaxSize = this.measureStreamLabelSizes(this.node.outputs);

        const rectWidth = Math.max(
            inputLabelMaxSize.width + outputLabelMaxSize.width + minLabelSpace + labelEdgeOffset * 2,
            nodeLabel.width + nodeLabelHPadding * 2
        );

        // set label position
        nodeLabel.position.set(xOffset + (rectWidth - nodeLabel.width) / 2, paddingVertical);

        // gray rect with rounded corners
        const containerRect = new PIXI.Graphics();
        containerRect.lineStyle(outlineWidth, this.node.outlineColor ?? outlineColor);
        containerRect.beginFill(this.fillColor);
        containerRect.drawRoundedRect(xOffset, 0, rectWidth, rectHeight, streamCircleRadius);
        containerRect.endFill();
        this.group.addChild(containerRect);
        this.group.addChild(nodeLabel);


        for (let i = 0; i < this.node.inputs.length; i++) {
            const connection = this.node.inputs[i];
            const yOffsetCenter = (i + 0.5) * streamHeight + streamsTopOffset;

            // draw a circle on the edge of the rect
            const circle = this.createConnectionCircle(connection);
            circle.position.set(xOffset, yOffsetCenter);
            this._relConnectorPositions.set(connection.id, circle.position);

            // draw the stream label
            const label = new PIXI.Text(connection.label, this.connectionLabelTextStyle);
            label.position.set(xOffset + labelEdgeOffset, yOffsetCenter - label.height / 2);
            label.resolution = 2;

            this.group.addChild(circle);
            this.group.addChild(label);
        }

        for (let i = 0; i < this.node.outputs.length; i++) {
            const connection = this.node.outputs[i];
            const yOffsetCenter = (i + 0.5) * streamHeight + streamsTopOffset;

            const circle = this.createConnectionCircle(connection);
            circle.position.set(xOffset + rectWidth, yOffsetCenter);
            this._relConnectorPositions.set(connection.id, circle.position);

            // draw the stream label
            const label = new PIXI.Text(connection.label, this.connectionLabelTextStyle);
            label.position.set(xOffset + rectWidth - labelEdgeOffset - label.width, yOffsetCenter - label.height / 2);
            label.resolution = 2;

            this.group.addChild(circle);
            this.group.addChild(label);
        }
    }

    private createConnectionCircle(connection: Connection) {
        const circle = new PIXI.Graphics();
        circle.lineStyle(outlineWidth, outlineColor);
        circle.beginFill(getStreamColor(connection));
        circle.drawCircle(0, 0, streamCircleRadius);
        circle.endFill();
        circle.interactive = true;

        circle.on('pointerdown', async () => await this.editor?.onSelectStartConnection(connection.id));
        circle.on('pointerup', async () => await this.editor?.onSelectEndConnection(this.id, connection.id));

        return circle;
    }

    private measureStreamLabelSizes(streams: { label?: string }[]) {
        let maxWidth = 0;
        let maxHeight = 0;
        for (const stream of streams) {
            const size = PIXI.TextMetrics.measureText(stream.label || "", this.connectionLabelTextStyle);
            if (size.width > maxWidth) {
                maxWidth = size.width;
            }
            if (size.height > maxHeight) {
                maxHeight = size.height;
            }
        }
        return { width: maxWidth, height: maxHeight };
    }


}

type ConnectionLink = {
    inputKey: string;
    inputNodeId: string;
    outputId: number;
    outputNodeId: string;
    rendered?: PIXI.Container
};

class ConnectionLinkCollection {
    private map = new Map<string, ConnectionLink>();

    public get values() {
        return Array.from(this.map.values());
    }

    public add(link: ConnectionLink) {
        this.map.set(this.getKey(link), link);
    }
    public remove(link: ConnectionLink) {
        this.map.delete(this.getKey(link));
    }
    public has(link: ConnectionLink) {
        return this.map.has(this.getKey(link));
    }

    private getKey(link: ConnectionLink) {
        return objectHash([link.inputKey, link.inputNodeId, link.outputId])
    }
}

export class NodeDisplayRenderer {
    private app: PIXI.Application;
    private nodeRenderer: NodeRenderer;
    private resizeObserver: ResizeObserver;
    private _perfectWidth: number = 0;
    private _perfectHeight: number = 0;
    private updateHandlers: (() => void)[] = [];
    private hostEl: HTMLElement;

    public padding: number = 20;

    public get perfectWidth() {
        return this._perfectWidth;
    }
    public get perfectHeight() {
        return this._perfectHeight;
    }

    constructor(node: Node, hostEl: HTMLElement, options: NodeDisplayOptions = {}) {
        this.hostEl = hostEl;
        this.nodeRenderer = new NodeRenderer(node);
        this.padding = options.padding !== undefined ? options.padding : this.padding;
        this.app = new PIXI.Application({
            width: this.hostEl.clientWidth,
            height: this.hostEl.clientHeight,
            backgroundColor: options.backgroundColor ?? appBackgroundColor,
            antialias: true,
            autoDensity: true,
            autoStart: false,
        });
        this.app.stage.addChild(this.nodeRenderer.container);
        this.hostEl.appendChild(this.app.view as HTMLCanvasElement);

        this.resizeObserver = new ResizeObserver(() => {
            this.resize();
            this.update();
        });
        if (!options.disableAutoResize) {
            this.resizeObserver.observe(this.hostEl);
        }
    }

    public resize() {
        this.app.renderer.resize(this.hostEl.clientWidth, this.hostEl.clientHeight);
    }
    public toDataUrl() {
        return this.app.renderer.extract.base64(this.app.stage);
    }

    public update() {
        this.nodeRenderer.render();

        const containerWidth = this.nodeRenderer.container.width / this.nodeRenderer.container.scale.x;
        const containerHeight = this.nodeRenderer.container.height / this.nodeRenderer.container.scale.y;

        const widthScale = (this.hostEl.clientWidth - this.padding * 2) / containerWidth;
        const heightScale = (this.hostEl.clientHeight - this.padding * 2) / containerHeight;
        const scale = Math.min(widthScale, heightScale);

        if (scale > 0) {
            const newWidth = containerWidth * scale;
            const newHeight = containerHeight * scale;

            this.nodeRenderer.container.transform.scale.set(scale, scale);
            this.nodeRenderer.container.position.set(
                (this.app.renderer.width - newWidth) / 2,
                (this.app.renderer.height - newHeight) / 2
            );
        }

        this._perfectWidth = heightScale * containerWidth + this.padding * 2;
        this._perfectHeight = widthScale * containerHeight + this.padding * 2;

        this.app.render();

        this.updateHandlers.forEach(h => h());
    }

    public destroy() {
        this.nodeRenderer.destroy();
        this.app.destroy();
        this.resizeObserver.disconnect();
        this.updateHandlers = [];
    }
}

export async function renderNodeToImage(node: Node, options: NodeRenderOptions) {
    const hostEl = document.createElement('div');
    if (options.width) {
        hostEl.style.width = options.width + 'px';
    }
    else if (options.height) {
        hostEl.style.height = options.height + 'px';
    }
    hostEl.style.visibility = 'hidden';
    document.body.appendChild(hostEl);

    const renderer = new NodeDisplayRenderer(node, hostEl, { ...options, disableAutoResize: true });
    renderer.update();
    if (options.width) {
        hostEl.style.height = renderer.perfectHeight + 'px';
    }
    else if (options.height) {
        hostEl.style.width = renderer.perfectWidth + 'px';
    }
    renderer.resize();
    renderer.update();
    const dataUrl = await renderer.toDataUrl();
    renderer.destroy();
    hostEl.remove();

    return dataUrl;
}

export class NodeEditorRenderer extends EventEmitter<{
"connectError": [ string ],
"updated": [ string ],
"selected": [ string | undefined ],
}> {
    public viewport: Viewport;
    private app?: PIXI.Application;
    private connectionLayer = new PIXI.Container();
    private nodeRenderers = new Map<string, NodeRenderer>();
    private links = new ConnectionLinkCollection();

    private pressActive = false;
    private selectedNodeId?: string;

    private selectedConnectionId?: string | number;
    private keepEditingLinkLine = false;
    private editingLinkLine?: PIXI.Graphics;

    private container?: HTMLElement;
    private containerResizeObserver?: ResizeObserver;

    private onPointerUpHandler = () => this.onReleaseNode();

    private _readOnly: boolean = false;
    public get readOnly() {
        return this._readOnly;
    }
    public set readOnly(value: boolean) {
        this._readOnly = value;
        this.editingLinkLine?.removeFromParent();
    }

    public get selectedNode(): NodeRenderer | undefined {
        if (!this.selectedNodeId) {
            return undefined;
        }
        return this.nodeRenderers.get(this.selectedNodeId);
    }
    public get zoom() {
        return this.viewport.scaled;
    }
    private get selectedInputConnection() {
        if (!this.selectedConnectionId) {
            return undefined;
        }
        return this.selectedNode?.inputs.find(c => c.key === this.selectedConnectionId);
    }
    private get selectedConnectionPosition() {
        if (!this.selectedConnectionId) {
            return undefined;
        }
        return this.selectedNode?.connectorPositions.get(this.selectedConnectionId);
    }

    constructor() {
        super();
        this.app = new PIXI.Application({
            width: 1,
            height: 1,
            backgroundColor: appBackgroundColor,
            antialias: true,
            autoDensity: true,
            autoStart: false,
        });

        this.app.ticker.maxFPS = 60;
        this.viewport = new Viewport({
            worldWidth: 1000,
            worldHeight: 1000,
            events: this.app.renderer.events,
        });
        this.app.stage.addChild(this.viewport);
        this.viewport.addChild(this.connectionLayer);
        this.viewport.on("pointermove", (e) => {
            if (!this.pressActive || !this.selectedNodeId || this._readOnly) return;
            const selectedConnectionPosition = this.selectedConnectionPosition;
            if (!selectedConnectionPosition) {
                this.selectedNode?.move(e.movementX / this.viewport.scale.x, e.movementY / this.viewport.scale.y);
                this.renderNodeLinks(this.selectedNodeId);
            }
            else {
                this.renderEditingLink(e.getLocalPosition(this.viewport))
            }
        })
        window.addEventListener("pointerup", this.onPointerUpHandler);
        this.viewport
            .drag()
            .pinch()
            .wheel()
    }

    public getInternalPosition(p: Point): Point {
        const r = this.viewport.toLocal(p);
        return { x: r.x, y: r.y }
    }

    public async addNode(node: Node, center: boolean = false) {
        if (this.nodeRenderers.has(node.id)) throw new Error(`Node with id ${node.id} already exists`);

        const nodeRenderer = new NodeRenderer(node, this);

        this.nodeRenderers.set(node.id, nodeRenderer);
        const links = [
            ...this.createLinksFromInputConnections(nodeRenderer.id, nodeRenderer.inputs),
            ...this.createLinksFromOutputConnections(nodeRenderer.id, nodeRenderer.outputs)
        ];
        for (const link of links) {
            if (await this.connectLinkToInput(link)) {
                this.links.add(link)
            }
        }

        this.renderNode(node.id);

        if (center) {
            const xOffset = nodeRenderer.container.width / 2;
            const yOffset = nodeRenderer.container.height / 2;
            nodeRenderer.updatePosition({
                x: this.viewport.center.x - xOffset,
                y: this.viewport.center.y - yOffset
            });
            this.renderNode(node.id);
        }
    }
    public deleteNode(id: string) {
        this.nodeRenderers.get(id)?.destroy();
        this.nodeRenderers.delete(id);
        this.removeLinks(this.links.values.filter(c => c.inputNodeId === id || c.outputNodeId === id));
    }
    public async updateNode(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        node.render();
        await this.reconnectNodeOutputs(nodeId);
        this.renderNodeLinks(nodeId);
        this.emit("updated", nodeId);
    }
    public clear() {
        this.nodeRenderers.forEach(node => node.destroy());
        this.nodeRenderers.clear();
        this.links.values.forEach(link => link.rendered?.removeFromParent());
        this.links = new ConnectionLinkCollection();
    }

    public async onSelectStartConnection(connectionId: string | number) {
        this.selectedConnectionId = connectionId;
        if (this._readOnly) return;

        const selectedInputConnection = this.selectedInputConnection;
        if (selectedInputConnection) {
            if (await this.connectConnectionToInput(this.selectedNodeId!, selectedInputConnection.key)) {
                this.removeLinks(this.links.values.filter(c => c.inputNodeId === this.selectedNodeId && c.inputKey === connectionId));
                this.emit("updated", this.selectedNodeId!);
            }
        }
    }
    public async onSelectEndConnection(nodeId: string, connectionId: string | number) {
        if (this._readOnly) return;

        const connection: ConnectionLink | undefined = this.createConnectionLink(this.selectedNodeId, this.selectedConnectionId, nodeId, connectionId);
        if (!connection) return;
        if (this.links.has(connection)) return;
        this.keepEditingLinkLine = true;
        try {
            if (await this.connectLinkToInput(connection)) {
                this.links.add(connection);
                this.renderLink(connection);
                this.renderUpdateInputLinks(connection.inputNodeId, connection.inputKey);

                this.emit("updated", connection.inputNodeId);
                this.emit("updated", connection.outputNodeId);
            }
        }
        finally {
            this.editingLinkLine?.removeFromParent();
            this.keepEditingLinkLine = false;
        }
    }
    
    public unmount() {
        if (!this.container) return;
        this.app?.stop();
        this.containerResizeObserver?.disconnect();
        this.containerResizeObserver = undefined;
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }
    }
    public mount(container: HTMLElement) {
        this.unmount();
        if (!this.app) return;
        this.container = container;
        container.appendChild(this.app.view as HTMLCanvasElement);
        this.app.start();

        this.resize()
        this.containerResizeObserver = new ResizeObserver(this.resize.bind(this));
        this.containerResizeObserver.observe(container);
    }
    public destroy() {
        this.unmount();
        this.app?.destroy();
        this.app = undefined;
        window.removeEventListener("pointerup", this.onPointerUpHandler);
    }

    public unselectNode() {
        if (this.selectedNodeId === undefined) return;
        this.emit("selected", undefined);
        const nodeId = this.selectedNodeId;
        this.selectedNodeId = undefined;
        this.renderNode(nodeId);
    }

    public onPressNode(id: string) {
        const oldNodeId = this.selectedNodeId;

        this.selectedNodeId = id;
        if (oldNodeId !== undefined && oldNodeId !== id) {
            this.renderNode(oldNodeId)
        }
        this.emit("selected", id);
        this.pressActive = true;
        this.viewport.plugins.pause('drag');

        this.renderNode(id);
        this.selectedNode?.render();
        this.renderNodeLinks(id);
    }
    private onReleaseNode() {
        if (this.pressActive) {
            this.pressActive = false;
            this.selectedConnectionId = undefined;
            if (!this.keepEditingLinkLine) {
                this.editingLinkLine?.removeFromParent();
            }
            this.viewport.plugins.resume('drag');
        }
    }

    private resize() {
        if (!this.container) return;
        this.app?.renderer.resize(this.container.clientWidth, this.container.clientHeight);
        this.viewport.resize(this.container.clientWidth, this.container.clientHeight, 1000, 1000);
    }
    private createLinksFromOutputConnections(nodeId: string, outputConnections: OutputConnection[]) {
        const outputConnectionIdsSet = new Set(outputConnections.map(c => c.streamId));

        const newLinks: ConnectionLink[] = [];
        for (const nodeRenderer of this.nodeRenderers.values()) {
            for (const input of nodeRenderer.inputs) {
                if (input.streamId && outputConnectionIdsSet.has(input.streamId)) {
                    newLinks.push({
                        inputKey: input.key,
                        inputNodeId: nodeRenderer.id,
                        outputId: input.streamId,
                        outputNodeId: nodeId
                    })
                }
            }
        }

        return newLinks;
    }
    private createLinksFromInputConnections(nodeId: string, inputConnections: InputConnection[]) {
        const inputConnectionIdMap = new Map<number, string>();
        for (const input of inputConnections) {
            if (input.streamId) {
                inputConnectionIdMap.set(input.streamId, input.key);
            }
        }

        const newLinks: ConnectionLink[] = [];
        for (const nodeRenderer of this.nodeRenderers.values()) {
            for (const output of nodeRenderer.outputs) {
                if (inputConnectionIdMap.has(output.streamId)) {
                    newLinks.push({
                        inputKey: inputConnectionIdMap.get(output.streamId)!,
                        inputNodeId: nodeId,
                        outputId: output.streamId,
                        outputNodeId: nodeRenderer.id
                    })
                }
            }
        }

        return newLinks;
    }

    private async connectLinkToInput(link: ConnectionLink) {
        const outputNode = this.nodeRenderers.get(link.outputNodeId);
        if (!outputNode) return;
        const outputConnection = outputNode.outputs.find(c => c.streamId === link.outputId);
        if (!outputConnection) return false;
        return await this.connectConnectionToInput(link.inputNodeId, link.inputKey, outputConnection)
    }

    private async connectConnectionToInput(inputNodeId: string, inputKey: string, outputConnection?: OutputConnection) {
        const inputNode = this.nodeRenderers.get(inputNodeId);
        if (!inputNode) return false;

        const result = await inputNode.connect(inputKey, outputConnection);
        if (!this.handleConnectionResult(result)) return false;
        return true;
    }

    private createConnectionLink(aNodeId: string | undefined, aConnectionId: string | number | undefined, bNodeId: string | undefined, bConnectionId: string | number | undefined): ConnectionLink | undefined {
        if (!aConnectionId || !bConnectionId || !aNodeId || !bNodeId) return;
        const aNode = this.nodeRenderers.get(aNodeId);
        const bNode = this.nodeRenderers.get(bNodeId);
        if (!aNode || !bNode) return;

        const aInputConnection = aNode.inputs.find(c => c.id === aConnectionId);
        const bInputConnection = bNode.inputs.find(c => c.id === bConnectionId);
        const aOutputConnection = aNode.outputs.find(c => c.id === aConnectionId);
        const bOutputConnection = bNode.outputs.find(c => c.id === bConnectionId);

        if ((!aInputConnection && !bInputConnection) || (!aOutputConnection && !bOutputConnection)) return;

        return {
            inputKey: aInputConnection ? aInputConnection.key : bInputConnection!.key,
            inputNodeId: aInputConnection ? aNodeId : bNodeId,
            outputId: aOutputConnection ? aOutputConnection.streamId : bOutputConnection!.streamId,
            outputNodeId: aOutputConnection ? aNodeId : bNodeId,
        }
    }

    private handleConnectionResult(result: ConnectResult): boolean {
        if (result === false) {
            this.emit("connectError", "Connection failed");
            return false;
        }
        else if (result === true) {
            return true;
        }
        else {
            this.emit("connectError", result);
            return false;
        }
    }

    private renderEditingLink(pos: Point) {
        if (this.editingLinkLine) {
            this.editingLinkLine?.removeFromParent();
        }
        const selectedConnectionIsInput = this.selectedInputConnection;
        const inputPos = selectedConnectionIsInput ? this.selectedConnectionPosition : pos;
        const outputPos = selectedConnectionIsInput ? pos : this.selectedConnectionPosition;
        if (!inputPos || !outputPos) return;
        this.editingLinkLine = this.drawConnectionLine(inputPos, outputPos);
    }

    private renderNode(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        node.render();
        this.renderNodeLinks(nodeId);
    }

    private async reconnectNodeOutputs(nodeId: string) {
        const removeLinks = [];
        for (const link of this.links.values) {
            if (link.outputNodeId === nodeId && !(await this.connectLinkToInput(link))) {
                removeLinks.push(link);
            }
        }
        this.removeLinks(removeLinks);
    }

    private renderUpdateInputLinks(nodeId: string, key: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        const foundInput = node.inputs.find(c => c.key === key);
        if (!foundInput) return;
        this.removeLinks(this.links.values.filter(c => c.inputNodeId === nodeId && c.inputKey === key && c.outputId !== foundInput.streamId));
    }

    private renderNodeLinks(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        this.links.values.filter(c => c.inputNodeId === nodeId || c.outputNodeId === nodeId).forEach(c => this.renderLink(c));
    }

    private renderLink(link: ConnectionLink) {
        if (link.rendered) {
            link.rendered.removeFromParent();
        }

        const inputNode = this.nodeRenderers.get(link.inputNodeId);
        const outputNode = this.nodeRenderers.get(link.outputNodeId);
        if (!inputNode || !outputNode) return false;

        const inputPosition = inputNode.connectorPositions.get(link.inputKey);
        const outputPosition = outputNode.connectorPositions.get(link.outputId);

        if (!inputPosition || !outputPosition) return;

        link.rendered = this.drawConnectionLine(inputPosition, outputPosition);

        return;
    }

    private removeLinks(links: ConnectionLink[]) {
        for (const link of links) {
            link.rendered?.removeFromParent();
            this.links.remove(link);
        }
    }

    private drawConnectionLine(inputPoint: Point, outputPoint: Point) {
        const dist = Math.sqrt(Math.pow(inputPoint.x - outputPoint.x, 2) + Math.pow(inputPoint.y - outputPoint.y, 2));

        let cpYOffset = Math.min(150, dist);
        if (outputPoint.y >= inputPoint.y) {
            cpYOffset *= -1;
        }
        if (inputPoint.x > outputPoint.x) {
            cpYOffset = 0;
        }

        const cpXOffset = Math.min(150, dist / 2);
        const line = new PIXI.Graphics();
        line.lineStyle(outlineWidth, outlineColor);
        line.moveTo(inputPoint.x, inputPoint.y);
        line.bezierCurveTo(inputPoint.x - cpXOffset, inputPoint.y + cpYOffset, outputPoint.x + cpXOffset, outputPoint.y + cpYOffset, outputPoint.x, outputPoint.y);
        this.connectionLayer.addChild(line);
        return line;
    }
}