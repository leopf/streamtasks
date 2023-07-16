import React from "react";
import ReactDOM from "react-dom";
import { GateTask, NumberGeneratorTask } from "./sample-nodes";
import { NodeEditorRenderer } from "./lib/node-editor";
import { createServer } from "miragejs"
import { App } from "./App";
import { Deployment, Task, cloneTask } from "./lib/task";
import { v4 as uuidv4 } from "uuid";
import { configure  } from "mobx";
import { Dashboard } from "./types";
import { RPCTaskConnectRequest, RPCTaskConnectResponse } from "./lib/task/node";

configure({
    observableRequiresReaction: false,
    enforceActions: "never",
})

// createServer({
//     routes() {
//         this.namespace = "/"
//         this.timing = 100;

//         this.get("/api/dashboards", () => {
//             const dashboards: Dashboard[] = [
//                 {
//                     id: uuidv4(),
//                     label: "Dashboard 1",
//                     url: "https://www.google.com"
//                 },
//                 {
//                     id: uuidv4(),
//                     label: "Dashboard 2",
//                     url: "https://www.bing.com"
//                 }
//             ];
//             return dashboards;
//         })

//         const deployments: Deployment[] = [
//             {
//                 id: "abc",
//                 label: 'New Deployment',
//                 status: 'offline',
//                 tasks: [],
//             }
//         ];

//         this.get("/api/deployments", () => deployments)
//         this.get("/api/deployment/:id", (schema, req) => {
//             const id = req.params.id;
//             const d = deployments.find(d => d.id === id) ?? {};
//             console.log("respond: ", d);
//             return d;
//         })

//         this.post("/api/deployment", () => {
//             const deployment: Deployment = {
//                 id: uuidv4(),
//                 label: 'New Deployment',
//                 status: 'offline',
//                 tasks: [],
//             };
//             deployments.push(deployment);
//             return deployment;
//         })

//         this.post("/api/deployment/:id/start", async () => {
//             await new Promise((resolve) => setTimeout(resolve, 1000));
//             return {
//                 status: Math.random() > 0.1 ? "running" : "error"
//             };
//         });
//         this.post("/api/deployment/:id/stop", async () => {
//             await new Promise((resolve) => setTimeout(resolve, 1000));
//             return {
//                 status: "offline"
//             };
//         });
//         this.get("/api/task-templates", () => {
//             const tasks: Task[] = [
//                 {
//                     id: uuidv4(),
//                     task_factory_id: "a",
//                     config: {
//                         label: "Gate",
//                     },
//                     stream_groups: [
//                         {
//                             inputs: [
//                                 {
//                                     ref_id: uuidv4(),
//                                     topic_id: uuidv4(),
//                                     label: "Input Stream",
//                                 },
//                                 {
//                                     ref_id: uuidv4(),
//                                     topic_id: uuidv4(),
//                                     label: "Gate Value",
//                                     content_type: "number"
//                                 }
//                             ],
//                             outputs: [
//                                 {
//                                     topic_id: uuidv4(),
//                                     label: "Output Stream",
//                                     content_type: "video",
//                                     encoding: "h264",
//                                     extra: {
//                                         width: 1920,
//                                         height: 1080,
//                                         framerate: 30,
//                                         bitrate: 1000000,
//                                     }
//                                 }
//                             ]
//                         }
//                     ]
//                 }
//             ]

//             for (let i = 0; i< 3; i++) {
//                 tasks.push(...tasks);
//             }

//             return tasks.map(t => cloneTask(t))
//         })

//         this.post("/task-factory/:id/rpc/connect", async (schema, req) => {
//             const request: RPCTaskConnectRequest = JSON.parse(req.requestBody);
//             request.task.stream_groups.forEach((stream_group) => {
//                 stream_group.inputs.forEach((input) => {
//                     if (input.ref_id === request.input_id) {
//                         input.topic_id = request.output_stream?.topic_id;
//                     }
//                 })
//             })
//             const response: RPCTaskConnectResponse = {
//                 task: request.task, 
//             };
//             return response;
//         });
//         console.log("mirage server started")
//     }
// })

const editor = new NodeEditorRenderer()
editor.addNode(new GateTask({ x: 100, y: 100 }))
editor.addNode(new GateTask({ x: 300, y: 300 }))
editor.addNode(new GateTask({ x: 700, y: 700 }))
editor.addNode(new NumberGeneratorTask({ x: 400, y: 400 }))

ReactDOM.render((
    <App/>
), document.getElementById("root")!);