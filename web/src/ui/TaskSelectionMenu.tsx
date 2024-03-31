import { Box, Stack } from "@mui/material";
import { TaskTemplateItem } from "./TaskTemplateItem";
import { observer } from "mobx-react-lite";
import { useGlobalState } from "../state";

export const TaskSelectionMenu = observer(() => {
    const state = useGlobalState();
    
    return (
        <Box sx={{ height: "100%", maxHeight: "100%", overflowY: "auto" }} bgcolor={"#ccc"}>
            <Stack boxSizing="border-box" spacing={5} padding={1} minHeight="100%">
                {state.taskManager.taskHosts.map(th => <TaskTemplateItem key={th.id} taskHost={th} />)}
            </Stack>
        </Box>
    );
});