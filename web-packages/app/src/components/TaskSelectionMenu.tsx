import { Box, Stack, TextField } from "@mui/material";
import { TaskTemplateItem } from "./TaskTemplateItem";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useRootStore } from "../state/root-store";
import { parseTaskHost } from "@streamtasks/core";
import { getTaskHostSearchValues } from "../lib/task-host";

export const TaskSelectionMenu = observer(() => {
    const rootStore = useRootStore();
    const localState = useLocalObservable(() => ({
        searchText: "",
        get foundHosts() {
            let taskHosts = Array.from(rootStore.taskManager.taskHosts.values()).map(taskHost => parseTaskHost(taskHost));
            const searchText = this.searchText.toLowerCase();
            if (this.searchText) {
                taskHosts = taskHosts.filter(th => getTaskHostSearchValues(th).some(t => t?.toLowerCase().includes(searchText)));
            }
            return taskHosts.sort((a, b) => a.label.localeCompare(b.label));
        }
    }));

    return (
        <Box sx={{ height: "100%", maxHeight: "100%", overflowY: "auto", direction: "rtl", minWidth: "200px" }}>
            <Stack boxSizing="border-box" spacing={7.5} padding={1} minHeight="100%" sx={{ direction: "ltr" }} bgcolor={theme => theme.palette.background.paper}>
                <TextField onInput={e => localState.searchText = (e.target as HTMLInputElement).value} variant="filled" label="search"/>
                {localState.foundHosts.map(th => <TaskTemplateItem key={th.id} taskHost={th} />)}
            </Stack>
        </Box>
    );
});