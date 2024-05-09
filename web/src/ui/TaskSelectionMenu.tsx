import { Box, Stack, TextField } from "@mui/material";
import { TaskTemplateItem } from "./components/TaskTemplateItem";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useRootStore } from "../state/root-store";
import { TaskHost } from "../types/task";

export const TaskSelectionMenu = observer(() => {
    const rootStore = useRootStore();
    const localState = useLocalObservable(() => ({
        searchText: "",
        get foundHosts() {
            let taskHosts = rootStore.taskManager.taskHosts;
            if (this.searchText) {
                taskHosts = taskHosts.filter(th => Object.values(th.metadata).some(k => String(k).includes(this.searchText)));
            }
            taskHosts = Array.from((new Map<string, TaskHost>(taskHosts.map(th => [th.id, th]))).values())
            taskHosts = taskHosts
                .map(th => [th, String(th.metadata["cfg:label"] ?? th.metadata["label"] ?? "")] as [TaskHost, string])
                .sort((a, b) => a[1].localeCompare(b[1]))
                .map(item => item[0])
            return taskHosts;
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