import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Connection, Node, ConnectResult } from "./types";

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

    public get id() {
        return this.node.id;
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

    public connect(inputConnectionId: string, outputConnection: Connection): ConnectResult {
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

    public render() {
        this.group.removeChildren();
        this._relConnectorPositions.clear();
        this.connectorPositionsOutdated = true;

        const pos = this.node.getPosition();
        this.group.position.set(pos.x, pos.y);

        // rect width and height
        const streamGroups = this.node.getConnectionGroups();
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

type NodeConnection = {
    inputId: string;
    inputNodeId: string;
    outputId: string;
    outputNodeId: string;
    rendered?: PIXI.DisplayObject
};

export class NodeEditorRenderer {
    public viewport: Viewport;
    private app: PIXI.Application;
    private connectionLayer = new PIXI.Container();
    private nodeRenderers = new Map<string, NodeRenderer>();
    private connections: NodeConnection[] = [];
    
    private pressActive = false;
    private selectedNodeId?: string;

    private selectedConnectionId?: string;
    private currentConnectionLine?: PIXI.Graphics;

    private get selectedNode() {
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
                this.updateNodeConnections(this.selectedNodeId);
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
            .decelerate()
    }

    public addNode(node: Node) {
        const taskRenderer = new NodeRenderer(this, node);
        taskRenderer.render();
        this.nodeRenderers.set(node.id, taskRenderer);
        this.updateNodeConnections(node.id);
    }
    public deleteNode(id: string) {
        const node = this.nodeRenderers.get(id);
        if (!node) return;

        const connections = this.connections.filter(c => c.inputNodeId === id || c.outputNodeId === id);
        for (const connection of connections) {
            connection.rendered?.removeFromParent();
            this.connections.splice(this.connections.indexOf(connection), 1);
        }
    }
    public updateNode(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;
        node.render();
        this.reconnectNodeOutputs(nodeId);
        this.updateNodeConnections(nodeId);
    }

    public onSelectStartConnection(connectionId: string) {
        this.selectedConnectionId = connectionId;
    }
    public onSelectEndConnection(nodeId: string, connectionId: string) {
        const aConnectionId = this.selectedConnectionId;
        const bConnectionId = connectionId;
        if (!aConnectionId || !bConnectionId) return;

        const aNode = this.selectedNode;
        const bNode = this.nodeRenderers.get(nodeId);
        if (!aNode || !bNode) return;

        const aInputConnection = aNode.inputs.find(c => c.refId === aConnectionId);
        const bInputConnection = bNode.inputs.find(c => c.refId === bConnectionId);
        const aOutputConnection = aNode.outputs.find(c => c.refId === aConnectionId);
        const bOutputConnection = bNode.outputs.find(c => c.refId === bConnectionId);

        if ((!aInputConnection && !bInputConnection) || (!aOutputConnection && !bOutputConnection)) return;

        const inputNode = aInputConnection ? aNode : bNode;
        const outputNode = aOutputConnection ? aNode : bNode;
        const inputConnection = (aInputConnection ?? bInputConnection)!;
        const outputConnection = (aOutputConnection ?? bOutputConnection)!;

        const result = inputNode.connect(inputConnection.refId, outputConnection);
        if (!this.handleConnectionResult(result)) return;

        const connection: NodeConnection = {
            inputId: inputConnection.refId,
            inputNodeId: inputNode.id,
            outputId: outputConnection.refId,
            outputNodeId: outputNode.id,
        };
        this.connections.push(connection);
        this.updateNodeConnection(connection);
    }

    public onPressNode(id: string) {
        this.selectedNodeId = id;
        this.pressActive = true;
        this.viewport.plugins.pause('drag');
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

    private updateNodeConnections(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;

        const removeConnections = this.connections.filter(c => c.inputNodeId === nodeId || c.outputNodeId === nodeId).filter(c => !this.updateNodeConnection(c));
        for (const connection of removeConnections) {
            this.connections.splice(this.connections.indexOf(connection), 1);
        }
    }

    private reconnectNodeOutputs(nodeId: string) {
        const node = this.nodeRenderers.get(nodeId);
        if (!node) return;

        const outputConnectionMap = new Map<string, Connection>(node.outputs.map(c => [c.refId, c]));

        const removeConnections = [];
        for (const connection of this.connections.filter(c => c.outputNodeId === nodeId)) {
            const inputNode = this.nodeRenderers.get(connection.inputNodeId);
            const outputConnection = outputConnectionMap.get(connection.outputId);

            if (!inputNode || !outputConnection) {
                removeConnections.push(connection);
                continue;
            }


            const result = inputNode.connect(connection.inputId, outputConnection);
            if (!this.handleConnectionResult(result)) {
                removeConnections.push(connection);
            }
        }
        for (const connection of removeConnections) {
            this.connections.splice(this.connections.indexOf(connection), 1);
        }
    }

    private updateNodeConnection(connection: NodeConnection) {
        if (connection.rendered) {
            connection.rendered.removeFromParent();
        }

        const inputNode = this.nodeRenderers.get(connection.inputNodeId);
        const outputNode = this.nodeRenderers.get(connection.outputNodeId);
        if (!inputNode || !outputNode) return false;

        const inputPosition = inputNode.connectorPositions.get(connection.inputId);
        const outputPosition = outputNode.connectorPositions.get(connection.outputId);

        if (!inputPosition || !outputPosition) return false;

        connection.rendered = this.drawConnectionLine(inputPosition, outputPosition);

        return true;
    }

    private drawConnectionLine(a: Point, b: Point) {
        const line = new PIXI.Graphics();
        line.lineStyle(outlineWidth, outlineColor);
        line.moveTo(a.x, a.y);
        line.lineTo(b.x, b.y);
        this.connectionLayer.addChild(line);
        return line;
    }
}