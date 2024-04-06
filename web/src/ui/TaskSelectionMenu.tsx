import { Box, Stack, TextField } from "@mui/material";
import { TaskTemplateItem } from "./components/TaskTemplateItem";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useRootStore } from "../state/root-store";

export const TaskSelectionMenu = observer(() => {
    const rootStore = useRootStore();
    const localState = useLocalObservable(() => ({
        searchText: "",
        get foundHosts() {
            let taskHosts = rootStore.taskManager.taskHosts;
            if (this.searchText) {
                taskHosts = taskHosts.filter(th => Object.values(th.metadata).some(k => String(k).includes(this.searchText)));
            }
            return taskHosts;
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