import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Connection, Node, ConnectResult, InputConnection } from "./types";

const paddingVertical = 10;
const nodeLabelHPadding = 20;
const streamsBottomOffset = paddingVertical;
const streamHeight = 30;
const xOffset = streamHeight / 2;
const streamCircleRadius = 8;
const outlineColor = 0x333333;
const selectedOutlineColor = 0x999999;
const outlineWidth = 2;
const labelEdgeOffset = streamCircleRadius + 5;
const minLabelSpace = 20;

export class NodeRenderer {
    private group: PIXI.Container;
    private node: Node;
    private editor: NodeEditorRenderer;
    
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
    private get isSelected() {
        return this.editor.selectedNode === this;
    }
    private get outlineColor() {
        return this.isSelected ? selectedOutlineColor : outlineColor;
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

    constructor(editor: NodeEditorRenderer, node: Node) {
        this.node = node;
        this.node.onUpdated?.call(this.node, () => this.editor.updateNode(this.id));
        this.editor = editor;

        this.group = new PIXI.Container();
        this.group.interactive = true;

        this.group.on('pointerdown', () => this.editor.onPressNode(this.node.id));

        this.editor.viewport.addChild(this.group);
    }

    public connect(inputConnectionId: string, outputConnection?: Connection): ConnectResult {
        return this.node.connect(inputConnectionId, outputConnection);
    }

    public move(x: number, y: number) {
        const currentPosition = this.node.getPosition();
        const newX = currentPosition.x + x;
        const newY = currentPosition.y + y;
        this.node.setPosition(newX, newY);
        this.group.position.set(newX, newY);
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
        containerRect.lineStyle(outlineWidth, this.outlineColor);
        containerRect.beginFill(0xffffff);
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
        circle.lineStyle(outlineWidth, this.outlineColor);
        circle.beginFill(this.getStreamColor(connection));
        circle.drawCircle(0, 0, streamCircleRadius);
        circle.endFill();

        circle.interactive = true;

        circle.on('pointerdown', () => this.editor.onSelectStartConnection(connection.refId));
        circle.on('pointerup', () => this.editor.onSelectEndConnection(this.node.id, connection.refId));

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

export class NodeEditorRenderer {
    public viewport: Viewport;
    private app: PIXI.Application;
    private connectionLayer = new PIXI.Container();
    private nodeRenderers = new Map<string, NodeRenderer>();
    private links = new ConnectionLinkCollection();
    
    private pressActive = false;
    private selectedNodeId?: string;

    private selectedConnectionId?: string;
    private currentConnectionLine?: PIXI.Graphics;

    public get selectedNode(): NodeRenderer | undefined {
        if (!this.selectedNodeId) {
            return undefined;
        }
        return this.nodeRenderers.get(this.selectedNodeId);
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
            backgroundColor: 0xeeeeee,
            antialias: true,
            autoDensity: true,
        });
        this.viewport = new Viewport({
            worldWidth: 1000,
            worldHeight: 1000,
            events: this.app.renderer.events,
        });
        this.viewport.addChild(this.connectionLayer);
        this.viewport.on("pointermove", (e) => {
            if (!this.pressActive || !this.selectedNodeId) return;
            const selectedConnectionPosition = this.selectedConnectionPosition;
            if (!selectedConnectionPosition) {
                this.selectedNode?.move(e.movementX / this.viewport.scale.x, e.movementY / this.viewport.scale.y);
                this.renderNodeLinks(this.selectedNodeId);
            }
            else {
                if (this.currentConnectionLine) {
                    this.currentConnectionLine?.removeFromParent();
                }

                this.currentConnectionLine = this.drawConnectionLine(selectedConnectionPosition, this.viewport.toWorld(e.x, e.y));
            }
        })
        this.viewport.on("pointerup", () => this.onReleaseNode())

        this.viewport
            .drag()
            .pinch()
            .wheel()
    }

    public addNode(node: Node) {
        const nodeRenderer = new NodeRenderer(this, node);

        const links = [
            ...this.createLinksFromInputConnections(nodeRenderer.id, nodeRenderer.inputs),
            ...this.createLinksFromOutputConnections(nodeRenderer.id, nodeRenderer.outputs)
        ];
        this.nodeRenderers.set(node.id, nodeRenderer);
        links.filter(c => this.connectLinkToInput(c)).forEach(c => this.links.add(c));
        this.renderNode(node.id);
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

        // check if is input
        const node = this.selectedNode;
        if (!node) return;
        const foundInput = node.inputs.find(c => c.refId === connectionId);
        if (!foundInput) return;

        // remove input connection
        if (this.connectConnectionToInput(node.id, connectionId)) {
            this.removeLinks(this.links.values.filter(c => c.inputNodeId === this.selectedNodeId && c.inputId === connectionId));
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
            this.currentConnectionLine?.removeFromParent();
            this.viewport.plugins.resume('drag');
        }
    }
    public mount(container: HTMLElement) {
        const resizeApp = () => {
            this.app.renderer.resize(container.clientWidth, container.clientHeight);
            this.viewport.resize(container.clientWidth, container.clientHeight, 1000, 1000);
        };

        container.appendChild(this.app.view as HTMLCanvasElement);
        this.app.stage.addChild(this.viewport);

        resizeApp();
        const hostResizeObserver = new ResizeObserver(resizeApp);
        hostResizeObserver.observe(container);
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
        const line = new PIXI.Graphics();
        line.lineStyle(outlineWidth, outlineColor);
        line.moveTo(inputPoint.x, inputPoint.y);
        line.lineTo(outputPoint.x, outputPoint.y);
        this.connectionLayer.addChild(line);
        return line;
    }
}