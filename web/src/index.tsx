import React from "react";
import ReactDOM from "react-dom";
import { NodeDisplay } from "./components/stateless/NodeDisplay";
import { GateTask, NumberGeneratorTask } from "./sample-nodes";
import { NodeEditorRenderer } from "./lib/node-editor";
import { NodeEditor } from "./components/stateless/NodeEditor";
import { createServer } from "miragejs"
import { App } from "./App";
import { Deployment, Task } from "./lib/task";
import { v4 as uuidv4 } from "uuid";

createServer({
    routes() {
        this.namespace = "api"

        this.get("/deployments", () => [])

        this.post("/deployment", () => {
            const deployment: Deployment = {
                id: uuidv4(),
                label: 'New Deployment',
                status: 'offline',
                tasks: [],
            };
            return deployment;
        })

        this.get("/task-templates", () => {
            const tasks: Task[] = [
                {
                    id: uuidv4(),
                    task_factory_id: uuidv4(),
                    config: {
                        label: "Gate",
                    },
                    stream_groups: [
                        {
                            inputs: [
                                {
                                    ref_id: uuidv4(),
                                    topic_id: uuidv4(),
                                    label: "Input Stream",
                                },
                                {
                                    ref_id: uuidv4(),
                                    topic_id: uuidv4(),
                                    label: "Gate Value",
                                    content_type: "number"
                                }
                            ],
                            outputs: [
                                {
                                    topic_id: uuidv4(),
                                    label: "Output Stream",
                                }
                            ]
                        }
                    ]
                }
            ]

            return tasks
        })
    }
})

const editor = new NodeEditorRenderer()
editor.addNode(new GateTask({ x: 100, y: 100 }))
editor.addNode(new GateTask({ x: 300, y: 300 }))
editor.addNode(new GateTask({ x: 700, y: 700 }))
editor.addNode(new NumberGeneratorTask({ x: 400, y: 400 }))

ReactDOM.render((
    <App/>
), document.getElementById("root")!);