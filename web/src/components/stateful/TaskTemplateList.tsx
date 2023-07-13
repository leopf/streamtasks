import { Box, Button, Card, CardActions, CardContent, Divider, Stack, Typography } from "@mui/material";
import { observer } from "mobx-react";
import React, { useMemo } from "react";
import { Task, taskToTemplateNode } from "../../lib/task";
import { NodeDisplay } from "../stateless/NodeDisplay";
import { state } from "../../state";

export const TaskTemplateItem = observer((props: { item: Task }) => {
    const node = useMemo(() => taskToTemplateNode(props.item), [props.item]);
    const description = props.item.config.description || "This is a node that you can use to do something.";

    return (
        <Stack direction="column" padding={1} sx={{
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
            <Box maxWidth={"100%"} width={"100%"}>
                <NodeDisplay resizeHeight padding={5} backgroundColor={"#fff0"} node={node}/>
            </Box>
            <Typography variant="caption">
                {description}
            </Typography>
        </Stack>
    );

});

export const TaskTemplateList = observer(() => {
    return (
        <Stack boxSizing="border-box" direction="column" flex={1} spacing={4} sx={{ "overflowY": "auto", height: "100%" }}>
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
        </Stack>
    )
});