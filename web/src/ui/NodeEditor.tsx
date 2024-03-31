import Box from '@mui/material/Box';
import { useState, useRef, useEffect } from 'react';
import { Node, ConnectResult, InputConnection, NodeEditorRenderer, OutputConnection } from '../lib/node-editor';
import { TaskNode } from '../lib/task-node';
import { TaskPartialInput } from '../configurators/std/static';
import { TaskManager } from '../lib/task';
import { TaskHost, TaskOutput } from '../types/task';


class DemoNode implements Node {
    public id: string = String(Math.random());
    public label: string = "Test";
    public position: { x: number; y: number; } = { x: 200 + 100 * Math.random(), y: 200 + 100 * Math.random() };
    public outputs: OutputConnection[] = [Math.floor(Math.random() * 1000000), Math.floor(Math.random() * 1000000)].map((id, idx) => ({ id, streamId: id, label: `out ${idx + 1}` }));
    public inputs: InputConnection[] = [String(Math.random() * 1000000), String(Math.random() * 1000000)].map((id, idx) => ({ id, key: id, label: `in ${idx + 1}` }));

    public async connect(key: string, output?: OutputConnection | undefined): Promise<ConnectResult> {
        const input = this.inputs.find(i => i.key == key);
        if (!input) return "Input not found!";
        input.streamId = output?.streamId;
        return true;
    }
    onUpdated?: ((cb: () => void) => void) | undefined;
}


const testHost: TaskHost = {
    id: "1337",
    metadata: {
        "js:configurator": "std:static",
        "cfg:label": "Test Task :)",
        "cfg:inputs": JSON.stringify(Array.from(Array(2)).map((_, idx) => ({
            key: String(Math.random()),
            label: `input ${idx + 1}`
        })) as TaskPartialInput[]),
        "cfg:outputs": JSON.stringify(Array.from(Array(2)).map((_, idx) => ({
            topic_id: Math.floor(Math.random() * 1000000),
            label: `output ${idx + 1}`,
        })) as TaskOutput[]),
    }
};

const taskManager = new TaskManager();

export function NodeEditor() {
    const [nodeRenderer, _] = useState(() => new NodeEditorRenderer())
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        nodeRenderer.mount(containerRef.current!);
        taskManager.createManagedTaskInstance(testHost).then(task => nodeRenderer.addNode(new TaskNode(task)))
        nodeRenderer.addNode(new DemoNode())
        nodeRenderer.addNode(new DemoNode())

    }, [])

    return (
        <Box width="100%" height="100%" position="relative">
            <Box
                width="100%"
                height="100%"
                position="absolute"
                onDragOver={e => e.preventDefault()}
                onDrop={async e => {
                    const taskHostId = e.dataTransfer.getData("text/plain");
                    if (!taskHostId || testHost.id !== taskHostId) return;
                    const task = await taskManager.createManagedTaskInstance(testHost)
                    const containerOffset = containerRef.current!.getBoundingClientRect();
                    task.frontendConfig.position = nodeRenderer.getInternalPosition({ x: e.clientX - containerOffset.x, y: e.clientY - containerOffset.y });
                    await nodeRenderer.addNode(new TaskNode(task))
                }}
                sx={{
                    "& canvas": {
                        "display": "block"
                    }
                }}
                ref={containerRef} />
        </Box>
    );
}