import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Node, ConnectResult, Connection, ConnectionGroup } from './types';
import { NodeDisplayRenderer, NodeEditorRenderer, NodeRenderer } from './node-editor';
import deepEqual from 'deep-equal';
import { v4 as uuidv4 } from "uuid";

interface TaskStreamConfig {
    content_type?: string
    encoding?: string  
}

class NumberGeneratorTask implements Node {
    private connectionGroups: ConnectionGroup[] = [
        {
            inputs: [],
            outputs: [
                {
                    refId: "1",
                    label: 'Output Stream',
                    config: { content_type: 'number' }
                }
            ]
        }
    ];
    private position: Point;
    public id: string;
    
    constructor(initialPosition: Point) {
        this.position = initialPosition;
        this.id = objectHash(initialPosition);
    }

    public setPosition(x: number, y: number) {
        this.position.x = x;
        this.position.y = y;
    }

    public getPosition() {
        return this.position;
    }

    public getName() {
        return 'Number Generator';
    }

    public getConnectionGroups() {
        return this.connectionGroups;
    }

    public connect(inputId: string, outputConnection?: Connection) {
        return false;
    }
}

class GateTask implements Node {
    private connectionGroups: ConnectionGroup[] = [
        {
            inputs: [
                {
                    refId: uuidv4(),
                    label: 'Input Stream',
                    config: {}
                },
                {
                    refId: uuidv4(),
                    label: 'Gate Value',
                    linkedStreamId: "1",
                    config: { content_type: 'number' }
                }
            ],
            outputs: [
                {
                    refId: uuidv4(),
                    label: 'Output Stream',
                    config: {}
                }
            ]
        }
    ];
    private position: Point;
    private updateHandlers: (() => void)[] = [];
    public id: string;

    constructor(initialPosition: Point) {
        this.position = initialPosition;
        this.id = objectHash(initialPosition);
    }

    public setPosition(x: number, y: number) {
        this.position.x = x;
        this.position.y = y;
    }

    public getPosition() {
        return this.position;
    }

    public getName() {
        return 'Gate';
    }

    public connect(inputId: string, outputConnection?: Connection) {
        if (this.connectionGroups[0].inputs[0].refId === inputId) {
            if (!outputConnection) {
                this.connectionGroups[0].inputs[0].linkedStreamId = undefined;
                return true;
            }
            this.connectionGroups[0].inputs[0].linkedStreamId = outputConnection.refId;
            this.setInputConfig(outputConnection.config);
            return true;
        }
        else if (this.connectionGroups[0].inputs[1].refId === inputId) {
            if (!outputConnection) {
                this.connectionGroups[0].inputs[1].linkedStreamId = undefined;
                return true;
            }

            const newConfig: TaskStreamConfig = outputConnection.config;
            if (newConfig.content_type !== 'number') {
                return 'Gate value must be a number';
            }

            this.connectionGroups[0].inputs[1].linkedStreamId = outputConnection.refId;
            return true;
        }
        else {
            return false;
        }
    }

    public getConnectionGroups() {
        return this.connectionGroups;
    }

    public onUpdated(cb: () => void) {
        this.updateHandlers.push(cb);
    }

    private setInputConfig(config: Record<string, any>) {
        if (!deepEqual(this.connectionGroups[0].inputs[0].config, config)) {
            this.connectionGroups[0].inputs[0].config = config;
            this.connectionGroups[0].outputs[0].config = config;
            this.updateHandlers.forEach(cb => cb());
        }
    }
}

// Create a Pixi Application in #root element

const hostEl = document.getElementById('root');
if (!hostEl) {
    throw new Error('Root element not found');
}

const display = new NodeDisplayRenderer(new GateTask({ x: 100, y: 100 }), hostEl)

// const renderer = new NodeEditorRenderer()
// renderer.mount(hostEl);

// renderer.addNode(new GateTask({ x: 100, y: 100 }))
// renderer.addNode(new GateTask({ x: 300, y: 300 }))
// renderer.addNode(new GateTask({ x: 700, y: 700 }))
// renderer.addNode(new NumberGeneratorTask({ x: 400, y: 400 }))