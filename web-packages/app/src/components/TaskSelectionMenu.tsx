import { Box, Chip, Stack, TextField } from "@mui/material";
import { TaskTemplateItem } from "./TaskTemplateItem";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useRootStore } from "../state/root-store";
import { parseTaskHost } from "@streamtasks/core";
import { getTaskHostSearchValues } from "../lib/task-host";

export const TaskSelectionMenu = observer(() => {
    const rootStore = useRootStore();
    const localState = useLocalObservable(() => ({
        searchText: "",
        selectedNodeNames: [] as string[],
        get parsedHosts() {
            return Array.from(rootStore.taskManager.taskHosts.values()).map(taskHost => parseTaskHost(taskHost));
        },
        get nodeNames() {
            return Array.from(new Set(this.parsedHosts.map(h => h.nodeName).filter(nn => !!nn) as string[])).sort((a, b) => a.localeCompare(b));
        },
        get foundHosts() {
            let taskHosts = Array.from(this.parsedHosts)
            const searchText = this.searchText.toLowerCase();
            if (this.searchText) {
                taskHosts = taskHosts.filter(th => getTaskHostSearchValues(th).some(t => t?.toLowerCase().includes(searchText)));
            }
            if (this.selectedNodeNames.length > 0) {
                taskHosts = taskHosts.filter(th => th.nodeName && this.selectedNodeNames.includes(th.nodeName));
            }
            return taskHosts.sort((a, b) => a.label.localeCompare(b.label));
        }
    }));

    return (
        <Box sx={{ height: "100%", maxHeight: "100%", overflowY: "auto", direction: "rtl", minWidth: "200px" }}>
            <Stack boxSizing="border-box" spacing={7.5} padding={1} minHeight="100%" sx={{ direction: "ltr" }} bgcolor={theme => theme.palette.background.paper}>
                <Stack spacing={1}>

                    <TextField onInput={e => localState.searchText = (e.target as HTMLInputElement).value} variant="filled" label="search" />
                    <Stack direction="row" flexWrap="wrap" sx={{ gap: 0.5 }}>
                        {localState.nodeNames.map(nn => (
                            <Chip
                                label={nn}
                                onClick={() => {
                                    if (localState.selectedNodeNames.includes(nn)) {
                                        localState.selectedNodeNames = localState.selectedNodeNames.filter(lnn => lnn !== nn);
                                    }
                                    else {
                                        localState.selectedNodeNames.push(nn);
                                    }
                                }}
                                color={localState.selectedNodeNames.includes(nn) ? "success" : "default"}
                                sx={{ fontSize: "0.7rem" }}
                                size="small"
                                clickable />
                        ))}
                    </Stack>
                </Stack>
                {localState.foundHosts.map(th => <TaskTemplateItem key={th.id} taskHost={th} />)}
            </Stack>
        </Box>
    );
});