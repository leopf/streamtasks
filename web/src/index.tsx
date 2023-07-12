import React from "react";
import ReactDOM from "react-dom";
import { NodeDisplay } from "./components/NodeDisplay";
import { GateTask, NumberGeneratorTask } from "./sample-nodes";
import { NodeEditorRenderer } from "./lib/node-editor";
import { NodeEditor } from "./components/NodeEditor";


const editor = new NodeEditorRenderer()
editor.addNode(new GateTask({ x: 100, y: 100 }))
editor.addNode(new GateTask({ x: 300, y: 300 }))
editor.addNode(new GateTask({ x: 700, y: 700 }))
editor.addNode(new NumberGeneratorTask({ x: 400, y: 400 }))

ReactDOM.render((
    <div style={{ width: "100%", height: "100%" }}>
        <NodeEditor editor={editor}/>
    </div>
), document.getElementById("root")!);