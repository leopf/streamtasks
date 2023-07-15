import { Box, Stack, Typography } from "@mui/material";
import { observer } from "mobx-react";
import React, { useMemo } from "react";
import { Task, taskToDisplayNode } from "../../lib/task";
import { NodeDisplay } from "../stateless/NodeDisplay";
import { state } from "../../state";

export const TaskTemplateItem = observer((props: { item: Task, onClick: () => void }) => {
    const node = useMemo(() => taskToDisplayNode(props.item), [props.item]);
    const description = props.item.config.description || "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam euismod, nisl eget aliquam ultricies, nunc nisl aliquet nunc, nec aliquam";
    const hostname = props.item.config.hostname || "localhost";

    return (
        <Stack onClick={props.onClick} direction="column" padding={2} sx={{
            "cursor": "pointer",
            "position": "relative",
        }}>
            <Box sx={{
                "position": "absolute",
                "top": 0,
                "right": 0,
                "bottom": 0,
                "left": 0,
                "zIndex": 1,
                "backgroundColor": "#0000",
                ":hover": {
                    backgroundColor: "#0001"
                }
            }} />
            <Box maxWidth={"100%"} width={"100%"} marginBottom={1}>
                <NodeDisplay node={node} />
            </Box>
            <Typography variant="caption" color="GrayText" lineHeight={1.25}>
                host: {hostname}
            </Typography>
            {description && (
                <Typography variant="caption"  lineHeight={1} marginTop={0.5}>
                    {description}
                </Typography>
            )}
        </Stack>
    );

});

export const TaskTemplateList = observer((props: { onSelect: (task: Task) => void }) => {
    return (
        <Box sx={{ "overflowY": "auto", height: "100%", width: "100%" }} >
            <Typography variant="h6" padding={2}>
                Task Templates
            </Typography>
            <Stack boxSizing="border-box" direction="column" spacing={2}>
                {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item} onClick={() => props.onSelect(item)} />)}
            </Stack>
        </Box>
    )
});