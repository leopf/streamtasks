import { observer } from "mobx-react";
import { useEffect, useMemo } from "react";
import { state } from "./state";
import { Box, Stack } from "@mui/material";
import React from "react";
import { TaskTemplateList } from "./components/stateful/TaskTemplateList";
import { NodeEditorRenderer } from "./lib/node-editor";
import { GateTask, NumberGeneratorTask } from "./sample-nodes";
import { NodeEditor } from "./components/stateless/NodeEditor";
import { Route, createBrowserRouter, createRoutesFromElements } from "react-router-dom";

// const router = createBrowserRouter(createRoutesFromElements(
//     <Route path="/" element={<App/>}/>
// ))

export const App = observer(() => {
    useEffect(() => {
        state.init();
    }, []);

    const editor = useMemo(() => {
        const e = new NodeEditorRenderer();
        e.addNode(new GateTask({ x: 100, y: 100 }));
        e.addNode(new GateTask({ x: 200, y: 200 }));
        e.addNode(new NumberGeneratorTask({ x: 300, y: 300 }));
        return e;
    }, []);

    if (!state.initialized) {
        return <div>Loading...</div>;
    }

    return (
        <Stack direction="column" sx={{ width: "100%", height: "100vh", maxHeight: "100vh"}}>
            <Box sx={{ flex: 1, overflowY: "hidden" }}>
                <Stack direction="row" sx={{ height: "100%", width: "100%" }}>
                    <TaskTemplateList/>
                    <Box flex={6} height={"100%"} onScroll={e => {
                        console.log("scroll", e);
                        e.preventDefault()
                    }}>
                        <NodeEditor editor={editor}/>
                    </Box>
                </Stack>
            </Box>
        </Stack>
    );
})