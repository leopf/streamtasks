import { Box, Stack } from "@mui/material";
import { TaskHost, TaskOutput } from "../types/task";
import { TaskTemplateItem } from "./TaskTemplateItem";
import { TaskPartialInput } from "../configurators/std/static";

const testHost: TaskHost = {
    id: String(Math.random()),
    metadata: {
        "js:configurator": "std:static",
        "cfg:label": "Test Task :)",
        "cfg:inputs": JSON.stringify(Array.from(Array(2)).map((_, idx) => ({
            key: String(Math.random()),
            label: `input ${idx + 1}`
        })) as TaskPartialInput[]),
        "cfg:outputs": JSON.stringify(Array.from(Array(2)).map((_, idx) => ({
            topic_id: Math.floor(Math.random() * 1000000),
            label: `output ${idx + 1}`,
        })) as TaskOutput[]),
    }
};

export function TaskSelectionMenu() {
    const taskHosts: TaskHost[] = Array.from(Array(20)).map(() => testHost);
    return (
        <Box sx={{ height: "100%", maxHeight: "100%", overflowY: "auto" }}>
            <Stack boxSizing="border-box" spacing={1} padding={1} bgcolor="gray">
                {taskHosts.map(th => <TaskTemplateItem key={th.id} taskHost={th} />)}
            </Stack>
        </Box>
    );
}