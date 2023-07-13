import { observer } from "mobx-react";
import { useEffect } from "react";
import { state } from "./state";
import { Stack } from "@mui/material";
import React from "react";
import { TaskTemplateList } from "./components/stateful/TaskTemplateList";

export const App = observer(() => {
    useEffect(() => {
        state.init();
    }, []);

    if (!state.initialized) {
        return <div>Loading...</div>;
    }

    return (
        <Stack direction="column" sx={{ width: "100%", height: "100%" }}>
            <Stack direction="row" sx={{ flexGrow: 1 }}>
                <TaskTemplateList/>
            </Stack>
        </Stack>
    );
})