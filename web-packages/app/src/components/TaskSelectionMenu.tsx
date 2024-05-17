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
            if (this.searchText) {
                taskHosts = taskHosts.filter(th => getTaskHostSearchValues(th).includes(this.searchText));
            }
            return taskHosts.sort((a, b) => a.label.localeCompare(b.label));
        }
    }));

    return (
        <Box sx={{ height: "100%", maxHeight: "100%", overflowY: "auto", direction: "rtl" }}>
            <Stack boxSizing="border-box" spacing={2.5} padding={1} minHeight="100%" sx={{ direction: "ltr" }}>
                <TextField sx={{ backgroundColor: "#eee" }} onInput={e => localState.searchText = (e.target as HTMLInputElement).value} variant="outlined" label="search"/>
                {localState.foundHosts.map(th => <TaskTemplateItem key={th.id} taskHost={th} />)}
            </Stack>
        </Box>
    );
});