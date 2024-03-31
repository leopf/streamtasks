import { Box } from "@mui/material";
import { TaskHost } from "../types/task";

export function TaskTemplateItem(props: { taskHost: TaskHost }) {
    return (
        <Box 
            width="100%"
            height="10rem"
            bgcolor={"blue"}
            draggable={true}
            onDragStart={(e) => e.dataTransfer.setData("text/plain", props.taskHost.id)}></Box>
    );
}