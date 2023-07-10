import * as PIXI from 'pixi.js';
import objectHash from "object-hash";
import { Viewport } from 'pixi-viewport'
import { Point, Node } from './types';
import { NodeEditorRenderer, NodeRenderer } from './renderer';

class TestGateTask implements Node {
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

    public getConnectionGroups() {
        return [
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
    }
}

// Create a Pixi Application in #root element

const hostEl = document.getElementById('root');
if (!hostEl) {
    throw new Error('Root element not found');
}

const renderer = new NodeEditorRenderer()
renderer.mount(hostEl);

renderer.addTask(new TestGateTask({ x: 100, y: 100 }))
renderer.addTask(new TestGateTask({ x: 300, y: 300 }))