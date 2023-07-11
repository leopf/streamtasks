import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Node, ConnectResult, Connection, ConnectionGroup } from './types';
import { NodeEditorRenderer, NodeRenderer } from './renderer';
import deepEqual from 'deep-equal';

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
                    refId: 'output1',
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

    public connect(inputId: string, outputConnection: Connection) {
        return false;
    }
}

class GateTask implements Node {
    private connectionGroups: ConnectionGroup[] = [
        {
            inputs: [
                {
                    refId: 'input1',
                    label: 'Input Stream',
                    config: {}
                },
                {
                    refId: 'input2',
                    label: 'Gate Value',
                    config: { content_type: 'number' }
                }
            ],
            outputs: [
                {
                    refId: 'output1',
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

    public connect(inputId: string, outputConnection: Connection) {
        if (this.connectionGroups[0].inputs[0].refId === inputId) {
            this.setInputConfig(outputConnection.config);
            return true;
        }
        else if (this.connectionGroups[0].inputs[1].refId === inputId) {
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

const renderer = new NodeEditorRenderer()
renderer.mount(hostEl);

renderer.addNode(new GateTask({ x: 100, y: 100 }))
renderer.addNode(new GateTask({ x: 300, y: 300 }))
renderer.addNode(new NumberGeneratorTask({ x: 400, y: 400 }))