import { Box, Stack, TextField } from "@mui/material";
import { TaskTemplateItem } from "./components/TaskTemplateItem";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useTaskManager } from "../state/task-manager";

export const TaskSelectionMenu = observer(() => {
    const taskManager = useTaskManager();
    const localState = useLocalObservable(() => ({
        searchText: "",
        get foundHosts() {
            return this.searchText ? taskManager.taskHosts.filter(th => Object.values(th.metadata).some(k => String(k).includes(this.searchText))) : taskManager.taskHosts
        }
    }));

    return (
        <Box sx={{ height: "100%", maxHeight: "100%", overflowY: "auto" }}>
            <Stack boxSizing="border-box" spacing={2.5} padding={1} minHeight="100%">
                <TextField sx={{ backgroundColor: "#eee" }} onInput={e => localState.searchText = (e.target as HTMLInputElement).value} variant="outlined" label="search"/>
                {localState.foundHosts.map(th => <TaskTemplateItem key={th.id} taskHost={th} />)}
            </Stack>
        </Box>
    );
});