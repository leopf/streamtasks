import React from "react";
import ReactDOM from "react-dom";
import { NodeDisplay } from "./components/NodeDisplay";
import { GateTask } from "./sample-nodes";


ReactDOM.render((
    <div style={{ width: "100%", height: "100%" }}>
        <NodeDisplay node={new GateTask({ x: 0, y: 0 })} />
    </div>
), document.getElementById("root")!);