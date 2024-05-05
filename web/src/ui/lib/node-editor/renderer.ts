import objectHash from "object-hash";
import { Connection, Node, ConnectResult, InputConnection, OutputConnection } from "./types";
import EventEmitter from 'eventemitter3';
import { HTMLViewport } from '../html-viewport';
import { Point, addPoints, pointDistance, scalarToPoint, subPoints } from '../point';

const streamCircleRadiusRem = 0.5;
const outlineColor = "#333";
const outlineWidth = 2;
const selectedNodeFillColor = "#f0f6ff";

const connectionColorSamples = [
    "#6528F7",
    "#A076F9",
    "#FFE300",
    "#FF7800",
    "#0CCA98",
    "#00FFCC",
    "#F9A828",
    "#EEB76B",
    "#ADE498",
    "#EDE682",
    "#91CA62",
    "#F1EBBB",
    "#F8B500",
    "#AA14F0",
    "#BC8CF2",
    "#6D67E4",
    "#FFC5A1",
    "#EF3F61",
    "#DF8931",
    "#85EF47",
    "#F9FD50"
]

const ignoreFieldsForContentComparison = new Set(["streamId", "label", "key", "id"]);

export function getStreamColor(connection: Record<string, number | string | boolean>, ignoreFields: Set<string> = ignoreFieldsForContentComparison) {
    const newConnection = { ...Object.fromEntries(Object.entries(connection).filter(([k, _]) => !ignoreFields.has(k))) };
    return connectionColorSamples[parseInt(objectHash([1, newConnection]).slice(0, 6), 16) % connectionColorSamples.length];
}

export class NodeRenderer {
    private group: HTMLDivElement;
    private node: Node;
    private editor?: NodeEditorRenderer;

    private connectorElements = new Map<string | number, HTMLElement>();

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
        return this.isSelected ? selectedNodeFillColor : "#ffffff";
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
        this.editor = editor;
        this.node.on?.call(this.node, "updated", async () => await this.editor?.updateNode(this.id));

        this.group = document.createElement("div");
        this.group.style.position = "absolute";
        this.group.style.width = "min-content";
        this.group.style.direction = "ltr";
        this.group.addEventListener('pointerdown', () => this.editor?.onPressNode(this.id));

        this.editor?.viewport.host.appendChild(this.group);
    }

    public getConnectorPosition(id: string | number) {
        const element = this.connectorElements.get(id);
        if (!element) return undefined;
        const pos = this.calculateConnectionCirclePosition(element);
        return addPoints(pos, { x: this.group.offsetLeft + outlineWidth, y: this.group.offsetTop  + outlineWidth});
    }

    public async connect(key: string, output?: OutputConnection) {
        return await this.node.connect(key, output);
    }

    public updatePosition(pos: Point) {
        this.node.position = { x: pos.x, y: pos.y };
        this.group.style.left = `${pos.x}px`;
        this.group.style.top = `${pos.y}px`;
    }

    public move(x: number, y: number) {
        const currentPosition = this.position;
        this.updatePosition({ x: currentPosition.x + x, y: currentPosition.y + y });
    }

    public destroy() {
        this.group.remove();
        this.node.destroy?.call(this.node);
    }

    public render() {
        while (this.group.firstChild) this.group.removeChild(this.group.firstChild);
        this.connectorElements.clear();
        this.updatePosition(this.position);

        const containerRect = document.createElement("div");
        containerRect.style.position = "relative";
        containerRect.style.border = `${outlineWidth}px solid ${this.node.outlineColor ?? outlineColor}`
        containerRect.style.backgroundColor = this.fillColor;
        containerRect.style.borderRadius = `${streamCircleRadiusRem}rem`;
        containerRect.style.boxSizing = "border-box";
        this.group.appendChild(containerRect);

        const nodeLabel = document.createElement("div");
        nodeLabel.innerText = this.node.label;
        nodeLabel.style.fontFamily = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
        nodeLabel.style.fontSize = "1rem";
        nodeLabel.style.color = "#000";
        nodeLabel.style.whiteSpace = "nowrap";
        nodeLabel.style.width = "100%";
        nodeLabel.style.textAlign = "center";
        nodeLabel.style.padding = "0.5rem 0.75rem 0 0.75rem";
        nodeLabel.style.boxSizing = "border-box";
        containerRect.appendChild(nodeLabel);


        const ioContainer = document.createElement("div")
        ioContainer.style.display = "flex";
        ioContainer.style.flexDirection = "row";
        ioContainer.style.alignItems = "stretch";
        ioContainer.style.width = "100%";
        ioContainer.style.padding = "0.5rem 0";
        containerRect.appendChild(ioContainer);

        const ioSpacer = document.createElement("div");
        ioSpacer.style.minWidth = "0.5rem";
        ioSpacer.style.flex = "1";

        const inputsContainer = document.createElement("div");
        inputsContainer.style.display = "flex";
        inputsContainer.style.flexDirection = "column";
        inputsContainer.style.alignItems = "start";
        inputsContainer.style.gap = "0.5rem";
        inputsContainer.style.marginLeft = `calc(-${streamCircleRadiusRem}rem - ${outlineWidth / 2}px)`;
        ioContainer.appendChild(inputsContainer);

        ioContainer.appendChild(ioSpacer);

        const outputsContainer = document.createElement("div");
        outputsContainer.style.display = "flex";
        outputsContainer.style.flexDirection = "column";
        outputsContainer.style.alignItems = "end";
        outputsContainer.style.gap = "0.5rem";
        outputsContainer.style.marginRight = `calc(-${streamCircleRadiusRem}rem - ${outlineWidth / 2}px)`;
        ioContainer.appendChild(outputsContainer);

        for (const input of this.inputs) {
            const inputContainer = document.createElement("div")
            inputContainer.style.display = "flex";
            inputContainer.style.flexDirection = "row";
            inputContainer.style.alignItems = "center";
            inputContainer.style.gap = "0.25rem";
            inputsContainer.appendChild(inputContainer);

            const connectionCircle = this.createConnectionCircle(input);
            inputContainer.appendChild(connectionCircle);
            inputContainer.appendChild(this.createConnectionLabel(input.label ?? ""));
            this.connectorElements.set(input.key, connectionCircle);
        }

        for (const output of this.outputs) {
            const outputContainer = document.createElement("div")
            outputContainer.style.display = "flex";
            outputContainer.style.flexDirection = "row";
            outputContainer.style.alignItems = "center";
            outputContainer.style.gap = "0.25rem";
            outputsContainer.appendChild(outputContainer);

            outputContainer.appendChild(this.createConnectionLabel(output.label ?? ""));

            const connectionCircle = this.createConnectionCircle(output);
            outputContainer.appendChild(connectionCircle);
            this.connectorElements.set(output.streamId, connectionCircle);
        }
    }

    private calculateConnectionCirclePosition(element: HTMLElement) {
        const pos: Point = { x: element.offsetWidth / 2, y: element.offsetHeight / 2 };
        let currentElement: HTMLElement | null = element;
        while (currentElement !== null && currentElement !== this.group) {
            pos.x += currentElement.offsetLeft;
            pos.y += currentElement.offsetTop;
            if (currentElement.offsetParent instanceof HTMLElement) {
                currentElement = currentElement.offsetParent;
            }
            else {
                currentElement = null;
            }
        }
        return pos;
    }

    private createConnectionLabel(label: string) {
        const element = document.createElement("div");
        element.style.fontFamily = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
        element.style.fontSize = "0.9rem";
        element.style.color = "#000";
        element.style.whiteSpace = "nowrap";
        element.innerText = label;
        return element;
    }
    private createConnectionCircle(connection: Connection) {
        const element = document.createElement("div");
        element.style.borderRadius = "50%";
        element.style.width = `${streamCircleRadiusRem * 2}rem`
        element.style.height = `${streamCircleRadiusRem * 2}rem`
        element.style.boxSizing = "border-box";
        element.style.cursor = "pointer";
        element.style.border = `${outlineWidth}px solid ${this.node.outlineColor ?? outlineColor}`
        element.style.backgroundColor = getStreamColor(connection);

        element.addEventListener('pointerdown', async () => {
            await this.editor?.onSelectStartConnection(connection.id)
        });
        element.addEventListener('pointerup', async () => await this.editor?.onSelectEndConnection(this.id, connection.id));
        return element;
    }
}

type ConnectionLink = {
    inputKey: string;
    inputNodeId: string;
    outputId: number;
    outputNodeId: string;
    rendered?: SVGSVGElement
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

export function renderNodeToElement(node: Node) {
    const renderer = new NodeRenderer(node);
    renderer.render();
    renderer.container.style.position = "static";
    return renderer.container;
}

export class NodeEditorRenderer extends EventEmitter<{
    "connectError": [string],
    "updated": [string],
    "selected": [string | undefined],
}> {
    public viewport: HTMLViewport;
    private connectionLayer: HTMLDivElement;
    private nodeRenderers = new Map<string, NodeRenderer>();
    private links = new ConnectionLinkCollection();

    private nodePressActive = false;
    private selectedNodeId?: string;

    private selectedConnectionId?: string | number;
    private keepEditingLinkLine = false;
    private editingLinkLine?: SVGSVGElement;

    private container?: HTMLElement;
    private onPointerUpHandler = () => this.onReleaseNode();

    private _readOnly: boolean = false;
    public get readOnly() {
        return this._readOnly;
    }
    public set readOnly(value: boolean) {
        this._readOnly = value;
        this.editingLinkLine?.remove();
    }

    public get selectedNode(): NodeRenderer | undefined {
        if (!this.selectedNodeId) {
            return undefined;
        }
        return this.nodeRenderers.get(this.selectedNodeId);
    }
    public get zoom() {
        return this.viewport.zoom;
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
        return this.selectedNode?.getConnectorPosition(this.selectedConnectionId);
    }

    constructor() {
        super();
        this.connectionLayer = document.createElement("div");
        this.connectionLayer.style.position = "absolute";
        this.connectionLayer.style.top = "0";
        this.connectionLayer.style.left = "0";

        this.viewport = new HTMLViewport();
        this.viewport.host.appendChild(this.connectionLayer);

        this.viewport.container.addEventListener("pointermove", (e) => {
            if (!this.nodePressActive || !this.selectedNodeId || this._readOnly) return;
            const selectedConnectionPosition = this.selectedConnectionPosition;
            if (!selectedConnectionPosition) {
                this.selectedNode?.move(e.movementX / this.viewport.zoom, e.movementY / this.viewport.zoom);
                this.renderNodeLinks(this.selectedNodeId);
            }
            else {
                const containerRect = this.viewport.container.getBoundingClientRect();
                this.renderEditingLink(this.viewport.toLocal({ 
                    x: e.clientX - containerRect.x, 
                    y: e.clientY - containerRect.y
                }));
            }
        })
        window.addEventListener("pointerup", this.onPointerUpHandler);
    }

    public getLocalPosition(p: Point): Point {
        return this.viewport.toLocal(p);
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
            const xOffset = nodeRenderer.container.clientWidth / 2;
            const yOffset = nodeRenderer.container.clientHeight / 2;
            nodeRenderer.updatePosition({
                x: this.viewport.localCenter.x - xOffset,
                y: this.viewport.localCenter.y - yOffset
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
        this.links.values.forEach(link => link.rendered?.remove());
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
            this.editingLinkLine?.remove();
            this.keepEditingLinkLine = false;
        }
    }

    public unmount() {
        if (!this.container) return;
        this.viewport.unmount();
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }
    }
    public mount(container: HTMLElement) {
        this.unmount();
        this.container = container;
        this.viewport.mount(container);
    }
    public destroy() {
        this.unmount();
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
        this.nodePressActive = true;
        this.viewport.disableDrag = true;

        this.renderNode(id);
        this.selectedNode?.render();
        this.renderNodeLinks(id);
    }
    private onReleaseNode() {
        if (this.nodePressActive) {
            this.nodePressActive = false;
            this.selectedConnectionId = undefined;
            if (!this.keepEditingLinkLine) {
                this.editingLinkLine?.remove();
            }
        }
        this.viewport.disableDrag = false;
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
            this.editingLinkLine?.remove();
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
            link.rendered.remove();
        }

        const inputNode = this.nodeRenderers.get(link.inputNodeId);
        const outputNode = this.nodeRenderers.get(link.outputNodeId);
        if (!inputNode || !outputNode) return false;

        const inputPosition = inputNode.getConnectorPosition(link.inputKey);
        const outputPosition = outputNode.getConnectorPosition(link.outputId);

        if (!inputPosition || !outputPosition) return;

        link.rendered = this.drawConnectionLine(inputPosition, outputPosition);

        return;
    }

    private removeLinks(links: ConnectionLink[]) {
        for (const link of links) {
            link.rendered?.remove();
            this.links.remove(link);
        }
    }

    private drawConnectionLine(inputPoint: Point, outputPoint: Point) {
        const svgPadding = 200 + outlineWidth; 
        const size: Point = {
            x: Math.abs(inputPoint.x - outputPoint.x) + svgPadding,
            y: Math.abs(inputPoint.y - outputPoint.y) + svgPadding,
        }
        const minPos: Point = {
            x: Math.min(inputPoint.x, outputPoint.x),
            y: Math.min(inputPoint.y, outputPoint.y)
        };

        const hPaddingVec = scalarToPoint(svgPadding / 2);

        const element = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        element.setAttribute("width", String(size.x));
        element.setAttribute("height", String(size.y));
        element.style.position = "absolute";

        const a = addPoints(subPoints(inputPoint, minPos), hPaddingVec);
        const b = addPoints(subPoints(outputPoint, minPos), hPaddingVec);
        const cpYOffset = inputPoint.x < outputPoint.x ? 100 : 0;
        const cpXOffset = Math.min(pointDistance(a, b) / 3, 50);

        const cpXOffsetScale = inputPoint.x < outputPoint.x ? 2 : 1;
        const cpYOffsetScale = inputPoint.y < outputPoint.y ? 1 : -1;

        const cp1 = { x: a.x - cpXOffset * cpXOffsetScale, y: a.y + cpYOffset * cpYOffsetScale };
        const cp2 = { x: b.x + cpXOffset * cpXOffsetScale, y: b.y - cpYOffset * cpYOffsetScale };
        element.innerHTML = `<path d="M ${a.x},${a.y} C ${cp1.x},${cp1.y} ${cp2.x},${cp2.y} ${b.x},${b.y}" style="fill:none; stroke:${outlineColor}; stroke-width:${outlineWidth}px;" />`;

        const position = subPoints(minPos, hPaddingVec);
        element.style.left = `${position.x}px`;
        element.style.top = `${position.y}px`;

        this.connectionLayer.appendChild(element);
        return element;
    }
}