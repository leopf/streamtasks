import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Connection, Node, ConnectResult, InputConnection } from "./types";

const appBackgroundColor = 0xeeeeee;
const paddingVertical = 10;
const nodeLabelHPadding = 20;
const streamsBottomOffset = paddingVertical;
const streamHeight = 30;
const streamCircleRadius = 8;
const outlineColor = 0x333333;
const outlineWidth = 2;
const xOffset = streamCircleRadius +  outlineWidth / 2;
const labelEdgeOffset = streamCircleRadius + 5;
const minLabelSpace = 20;
const selectedNodeFillColor = 0xf0f6ff;

export class NodeRenderer {
    private group: PIXI.Container;
    private node: Node;
    private editor?: NodeEditorRenderer;
    
    private _relConnectorPositions = new Map<string, Point>();
    private _absuluteConnectorPositions = new Map<string, Point>();
    private connectorPositionsOutdated = true;

    private connectionLabelTextStyle = new PIXI.TextStyle({
        fontFamily: 'Arial',
        fontSize: 13,
        fill: '#000000',
        wordWrap: false
    });
    private nodeLabelTextStyle = new PIXI.TextStyle({
        fontFamily: 'Arial',
        fontSize: 15,
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
        return this.node.getConnectionGroups().map(cg => cg.inputs).reduce((a, b) => a.concat(b), []);
    }
    public get outputs() {
        return this.node.getConnectionGroups().map(cg => cg.outputs).reduce((a, b) => a.concat(b), []);
    }

    constructor(node: Node, editor?: NodeEditorRenderer) {
        this.node = node;
        this.node.onUpdated?.call(this.node, () => this.editor?.updateNode(this.id));
        this.editor = editor;

        this.group = new PIXI.Container();
        this.group.interactive = true;

        this.group.on('pointerdown', () => this.editor?.onPressNode(this.node.id));

        this.editor?.viewport.addChild(this.group);
    }

    public connect(inputConnectionId: string, outputConnection?: Connection): ConnectResult {
        return this.node.connect(inputConnectionId, outputConnection);
    }

    public move(x: number, y: number) {
        const currentPosition = this.node.getPosition();
        this.position = { x: currentPosition.x + x, y: currentPosition.y + y };
    }

    public get position() {
        return this.node.getPosition();
    }

    public set position(pos: Point) {
        this.node.setPosition(pos.x, pos.y);
        this.group.position.set(pos.x, pos.y);
        this.connectorPositionsOutdated = true;
    }


    public remove() {
        this.group.removeFromParent();
    }

    public render() {
        this.group.removeChildren();
        this._relConnectorPositions.clear();
        this.connectorPositionsOutdated = true;

        const pos = this.node.getPosition();
        this.group.position.set(pos.x, pos.y);

        const nodeLabel = new PIXI.Text(this.node.getName(), this.nodeLabelTextStyle);
        nodeLabel.resolution = 2;
        const streamsTopOffset = paddingVertical * 2 + nodeLabel.height;


        // rect width and height
        const streamGroups = this.node.getConnectionGroups();
        const ioHeight = streamGroups.map(sg => Math.max(sg.inputs.length, sg.outputs.length)).reduce((a, b) => a + b, 0);
        const rectHeight = ioHeight * streamHeight + streamsBottomOffset + streamsTopOffset;

        const inputLabelMaxSize = this.measureStreamLabelSizes(streamGroups.map(sg => sg.inputs).reduce((a, b) => a.concat(b), []));
        const outputLabelMaxSize = this.measureStreamLabelSizes(streamGroups.map(sg => sg.outputs).reduce((a, b) => a.concat(b), []));

        const rectWidth = Math.max(
            inputLabelMaxSize.width + outputLabelMaxSize.width + minLabelSpace + labelEdgeOffset * 2,
            nodeLabel.width + nodeLabelHPadding * 2
        );

        // set label position
        nodeLabel.position.set(xOffset + (rectWidth - nodeLabel.width) / 2, paddingVertical);

        // gray rect with rounded corners
        const containerRect = new PIXI.Graphics();
        containerRect.lineStyle(outlineWidth, outlineColor);
        containerRect.beginFill(this.fillColor);
        containerRect.drawRoundedRect(xOffset, 0, rectWidth, rectHeight, streamCircleRadius);
        containerRect.endFill();
        this.group.addChild(containerRect);
        this.group.addChild(nodeLabel);

        // draw streams
        let heightIndex = 0;
        for (const streamGroup of streamGroups) {
            for (let i = 0; i < streamGroup.inputs.length; i++) {
                const stream = streamGroup.inputs[i];
                const yOffsetCenter = (heightIndex + i + 0.5) * streamHeight + streamsTopOffset;

                // draw a circle on the edge of the rect
                const circle = this.createConnectionCircle(stream);
                circle.position.set(xOffset, yOffsetCenter);
                this._relConnectorPositions.set(stream.refId, circle.position);

                // draw the stream label
                const label = new PIXI.Text(stream.label, this.connectionLabelTextStyle);
                label.position.set(xOffset + labelEdgeOffset, yOffsetCenter - label.height / 2);
                label.resolution = 2;

                this.group.addChild(circle);
                this.group.addChild(label);
            }
            for (let i = 0; i < streamGroup.outputs.length; i++) {
                const stream = streamGroup.outputs[i];
                const yOffsetCenter = (heightIndex + i + 0.5) * streamHeight + streamsTopOffset;

                const circle = this.createConnectionCircle(stream);
                circle.position.set(xOffset + rectWidth, yOffsetCenter);
                this._relConnectorPositions.set(stream.refId, circle.position);

                // draw the stream label
                const label = new PIXI.Text(stream.label, this.connectionLabelTextStyle);
                label.position.set(xOffset + rectWidth - labelEdgeOffset - label.width, yOffsetCenter - label.height / 2);
                label.resolution = 2;

                this.group.addChild(circle);
                this.group.addChild(label);
            }
            heightIndex += Math.max(streamGroup.inputs.length, streamGroup.outputs.length);
        }
    }

    private createConnectionCircle(connection: Connection) {
        const circle = new PIXI.Graphics();
        circle.lineStyle(outlineWidth, outlineColor);
        circle.beginFill(this.getStreamColor(connection));
        circle.drawCircle(0, 0, streamCircleRadius);
        circle.endFill();

        circle.interactive = true;

        circle.on('pointerdown', () => this.editor?.onSelectStartConnection(connection.refId));
        circle.on('pointerup', () => this.editor?.onSelectEndConnection(this.node.id, connection.refId));

        return circle;
    }

    private measureStreamLabelSizes(streams: Connection[]) {
        let maxWidth = 0;
        let maxHeight = 0;
        for (const stream of streams) {
            const size = PIXI.TextMetrics.measureText(stream.label, this.connectionLabelTextStyle);
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

type ConnectionLink = {
    inputId: string;
    inputNodeId: string;
    outputId: string;
    outputNodeId: string;
    rendered?: PIXI.DisplayObject
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

    private getKey(link: ConnectionLink) {
        return objectHash([ link.inputId, link.outputId ])
    }
}

export class NodeDisplayRenderer {
    private app: PIXI.Application;
    private nodeRenderer: NodeRenderer;
    private resizeObserver: ResizeObserver;
    private _perfectWidth: number = 0;
    private _perfectHeight: number = 0;
    private updateHandlers: (() => void)[] = [];
    
    public padding: number = 20;

    public get perfectWidth() {
        return this._perfectWidth;
    }
    public get perfectHeight() {
        return this._perfectHeight;
    }

    constructor(node: Node, hostEl: HTMLElement) {
        this.nodeRenderer = new NodeRenderer(node);
        this.app = new PIXI.Application({
            width: hostEl.clientWidth,
            height: hostEl.clientHeight,
            backgroundColor: appBackgroundColor,
            antialias: true,
            autoDensity: true,
            autoStart: false,
        });
        this.app.stage.addChild(this.nodeRenderer.container);

        hostEl.appendChild(this.app.view as HTMLCanvasElement);

        this.resizeObserver = new ResizeObserver(() => {
            this.app.renderer.resize(hostEl.clientWidth, hostEl.clientHeight);
            this.update();
        });
        this.resizeObserver.observe(hostEl);
    }

    public onUpdated(callback: () => void) {
        this.updateHandlers.push(callback);
    }

    public update() {
        this.nodeRenderer.render();

        const containerWidth = this.nodeRenderer.container.width / this.nodeRenderer.container.scale.x;
        const containerHeight = this.nodeRenderer.container.height / this.nodeRenderer.container.scale.y;
        
        const widthScale = (this.app.renderer.width - this.padding * 2) / containerWidth;
        const heightScale = (this.app.renderer.height - this.padding * 2) / containerHeight;
        const scale = Math.min(widthScale, heightScale);

        const newWidth = containerWidth * scale;
        const newHeight = containerHeight * scale;

        this.nodeRenderer.container.transform.scale.set(scale, scale);
        this.nodeRenderer.container.position.set(
            (this.app.renderer.width - newWidth) / 2,
            (this.app.renderer.height - newHeight) / 2
        );

        this._perfectWidth = heightScale * containerWidth + this.padding * 2;
        this._perfectHeight = widthScale * containerHeight + this.padding * 2;

        this.app.render();

        this.updateHandlers.forEach(h => h());
    }

    public destroy() {
        this.nodeRenderer.remove();
        this.app.destroy();
        this.resizeObserver.disconnect();
        this.updateHandlers = [];
    }
}

export class NodeEditorRenderer {
    public viewport: Viewport;
    private app: PIXI.Application;
    private connectionLayer = new PIXI.Container();
    private nodeRenderers = new Map<string, NodeRenderer>();
    private links = new ConnectionLinkCollection();
    
    private pressActive = false;
    private selectedNodeId?: string;

    private selectedConnectionId?: string;
    private editingLinkLine?: PIXI.Graphics;

    private container?: HTMLElement;
    private containerResizeObserver?: ResizeObserver;

    public get selectedNode(): NodeRenderer | undefined {
        if (!this.selectedNodeId) {
            return undefined;
        }
        return this.nodeRenderers.get(this.selectedNodeId);
    }
    private get selectedConnectionIsInput() {
        if (!this.selectedConnectionId) {
            return false;
        }
        return this.selectedNode?.inputs.find(c => c.refId === this.selectedConnectionId) !== undefined;
    }
    private get selectedConnectionPosition() {
        if (!this.selectedConnectionId) {
            return undefined;
        }
        return this.selectedNode?.connectorPositions.get(this.selectedConnectionId);
    }

    constructor() {
        this.app = new PIXI.Application({
            width: 1,
            height: 1,
            backgroundColor: appBackgroundColor,
            antialias: true,
            autoDensity: true,
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
            if (!this.pressActive || !this.selectedNodeId) return;
            const selectedConnectionPosition = this.selectedConnectionPosition;
            if (!selectedConnectionPosition) {
                this.selectedNode?.move(e.movementX / this.viewport.scale.x, e.movementY / this.viewport.scale.y);
                this.renderNodeLinks(this.selectedNodeId);
            }
            else {
                this.renderEditingLink(this.viewport.toWorld(e.x, e.y))
            }
        })
        this.viewport.on("pointerup", () => this.onReleaseNode())
        this.viewport
            .drag()
            .pinch()
            .wheel()
    }

    public addNode(node: Node, center: boolean = false) {
        const nodeRenderer = new NodeRenderer(node, this);

        this.nodeRenderers.set(node.id, nodeRenderer);
        const links = [
            ...this.createLinksFromInputConnections(nodeRenderer.id, nodeRenderer.inputs),
            ...this.createLinksFromOutputConnections(nodeRenderer.id, nodeRenderer.outputs)
        ];
        links.filter(c => this.connectLinkToInput(c)).forEach(c => this.links.add(c));
        this.renderNode(node.id);

        if (center) {
            const xOffset = nodeRenderer.container.width / 2;
            const yOffset = nodeRenderer.container.height / 2;
            nodeRenderer.position = {
                x: this.viewport.center.x - xOffset,
                y: this.viewport.center.y - yOffset
            }
            this.renderNode(node.id);
        }
    }
    public deleteNode(id: string) {
        this.nodeRenderers.get(id)?.remove();
        this.nodeRenderers.delete(id);
        this.removeLinks(this.links.values.filter(c => c.inputNodeId === id || c.outputNodeId === id));
    }
    public updateNode(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        node.render();
        this.reconnectNodeOutputs(nodeId);
        this.renderNodeLinks(nodeId);
    }

    public onSelectStartConnection(connectionId: string) {
        this.selectedConnectionId = connectionId;

        if (this.selectedConnectionIsInput) {
            if (this.connectConnectionToInput(this.selectedNodeId!, connectionId)) {
                this.removeLinks(this.links.values.filter(c => c.inputNodeId === this.selectedNodeId && c.inputId === connectionId));
            }
        }
    }
    public onSelectEndConnection(nodeId: string, connectionId: string) {
        const connection: ConnectionLink | undefined= this.createConnectionLink(this.selectedNodeId, this.selectedConnectionId, nodeId, connectionId);
        if (!connection) return;

        if (this.connectLinkToInput(connection)) {
            this.links.add(connection);
            this.renderLink(connection);
            this.renderInputLinks(connection.inputNodeId, connection.inputId);
        }
    }

    public unselectNode() {
        if (this.selectedNodeId === undefined) return;
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

        this.pressActive = true;
        this.viewport.plugins.pause('drag');

        this.renderNode(id);
        this.selectedNode?.render();
        this.renderNodeLinks(id);
    }
    public onReleaseNode() {
        if (this.pressActive) {
            this.pressActive = false;
            this.selectedConnectionId = undefined;
            this.editingLinkLine?.removeFromParent();
            this.viewport.plugins.resume('drag');
        }
    }
    public unmount() {
        if (!this.container) return;
        this.containerResizeObserver?.disconnect();
        this.containerResizeObserver = undefined;
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }
    }
    public mount(container: HTMLElement) {
        this.unmount();
        this.container = container;
        container.appendChild(this.app.view as HTMLCanvasElement);

        this.resize()
        this.containerResizeObserver = new ResizeObserver(this.resize.bind(this));
        this.containerResizeObserver.observe(container);
    }

    private resize() {
        if (!this.container) return;
        this.app.renderer.resize(this.container.clientWidth, this.container.clientHeight);
        this.viewport.resize(this.container.clientWidth, this.container.clientHeight, 1000, 1000);
    }
    private createLinksFromOutputConnections(nodeId: string, outputConnections: Connection[]) {
        const outputConnectionIdsSet = new Set(outputConnections.map(c => c.refId));

        const newLinks: ConnectionLink[] = [];
        for (const nodeRenderer of this.nodeRenderers.values()) {
            for (const input of nodeRenderer.inputs) {
                if (input.linkedStreamId && outputConnectionIdsSet.has(input.linkedStreamId)) {
                    newLinks.push({
                        inputId: input.refId,
                        inputNodeId: nodeRenderer.id,
                        outputId: input.linkedStreamId,
                        outputNodeId: nodeId
                    })
                }
            }
        }

        return newLinks;
    }
    private createLinksFromInputConnections(nodeId: string, inputConnections: InputConnection[]) {
        const inputConnectionIdMap = new Map<string, string>();
        for (const input of inputConnections) {
            if (input.linkedStreamId) {
                inputConnectionIdMap.set(input.linkedStreamId, input.refId);
            }
        }


        const newLinks: ConnectionLink[] = [];
        for (const nodeRenderer of this.nodeRenderers.values()) {
            for (const output of nodeRenderer.outputs) {
                if (inputConnectionIdMap.has(output.refId)) {
                    newLinks.push({
                        inputId: inputConnectionIdMap.get(output.refId)!,
                        inputNodeId: nodeId,
                        outputId: output.refId,
                        outputNodeId: nodeRenderer.id
                    })
                }
            }
        }

        return newLinks;
    }

    private connectLinkToInput(link: ConnectionLink) {
        const outputNode = this.nodeRenderers.get(link.outputNodeId);
        if (!outputNode) return;
        const outputConnection = outputNode.outputs.find(c => c.refId === link.outputId);
        if (!outputConnection) return false;
        return this.connectConnectionToInput(link.inputNodeId, link.inputId, outputConnection)
    }

    private connectConnectionToInput(inputNodeId: string, inputConnectionId: string, outputConnection?: Connection) {
        const inputNode = this.nodeRenderers.get(inputNodeId);
        if (!inputNode) return false;

        const result = inputNode.connect(inputConnectionId, outputConnection);
        if (!this.handleConnectionResult(result)) return false;
        return true;
    }

    private createConnectionLink(aNodeId: string | undefined, aConnectionId: string | undefined, bNodeId: string | undefined, bConnectionId: string | undefined) : ConnectionLink | undefined {
        if (!aConnectionId || !bConnectionId || !aNodeId || !bNodeId) return;
        const aNode = this.nodeRenderers.get(aNodeId);
        const bNode = this.nodeRenderers.get(bNodeId);
        if (!aNode || !bNode) return;

        const aInputConnection = aNode.inputs.find(c => c.refId === aConnectionId);
        const bInputConnection = bNode.inputs.find(c => c.refId === bConnectionId);
        const aOutputConnection = aNode.outputs.find(c => c.refId === aConnectionId);
        const bOutputConnection = bNode.outputs.find(c => c.refId === bConnectionId);

        if ((!aInputConnection && !bInputConnection) || (!aOutputConnection && !bOutputConnection)) return;

        return {
            inputId: aInputConnection ? aConnectionId : bConnectionId,
            inputNodeId: aInputConnection ? aNodeId : bNodeId,
            outputId: aOutputConnection ? aConnectionId : bConnectionId,
            outputNodeId: aOutputConnection ? aNodeId : bNodeId,
        }
    }

    private handleConnectionResult(result: ConnectResult): boolean {
        if (result === false) {
            console.log('Connection failed');
            return false;
        }
        else if (result === true) {
            return true;
        }
        else {
            console.error(result);
            return false;
        }
    }

    private renderEditingLink(pos: Point) {
        if (this.editingLinkLine) {
            this.editingLinkLine?.removeFromParent();
        }
        const selectedConnectionIsInput = this.selectedConnectionIsInput;
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

    private reconnectNodeOutputs(nodeId: string) {
        this.removeLinks(this.links.values.filter(c => c.outputNodeId === nodeId).filter(c => !this.connectLinkToInput(c)))
    }

    private renderInputLinks(nodeId: string, connectionId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        const foundInput = node.inputs.find(c => c.refId === connectionId);
        if (!foundInput) return;
        this.removeLinks(this.links.values.filter(c => c.inputNodeId === nodeId && c.inputId === connectionId && c.outputId !== foundInput.linkedStreamId));
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

        const inputPosition = inputNode.connectorPositions.get(link.inputId);
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
        let cpYOffset = Math.max(150 - Math.abs(inputPoint.y - outputPoint.y), 0);
        if (outputPoint.y >= inputPoint.y) {
            cpYOffset *= -1;
        }
        if (inputPoint.x > outputPoint.x) {
            cpYOffset = 0;
        }

        const dist = Math.sqrt(Math.pow(inputPoint.x - outputPoint.x, 2) + Math.pow(inputPoint.y - outputPoint.y, 2));
        const cpXOffset = Math.min(150, dist / 2);
        const line = new PIXI.Graphics();
        line.lineStyle(outlineWidth, outlineColor);
        line.moveTo(inputPoint.x, inputPoint.y);
        line.bezierCurveTo(inputPoint.x - cpXOffset, inputPoint.y + cpYOffset, outputPoint.x + cpXOffset, outputPoint.y + cpYOffset, outputPoint.x, outputPoint.y);
        this.connectionLayer.addChild(line);
        return line;
    }
}