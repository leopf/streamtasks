import { Box, Button, Card, CardActions, CardContent, Stack } from "@mui/material";
import { observer } from "mobx-react";
import React, { useMemo } from "react";
import { Task, taskToTemplateNode } from "../../lib/task";
import { NodeDisplay } from "../stateless/NodeDisplay";
import { state } from "../../state";
import { toJS } from "mobx";

export const TaskTemplateItem = observer((props: { item: Task }) => {
    console.log("TaskTemplateItem",  toJS(props.item));
    const node = useMemo(() => taskToTemplateNode(props.item), [props.item]);
    console.log("TaskTemplateItem",  toJS(node.getConnectionGroups()));


    return (
        <Card sx={{ width: "300px" }}>
            <CardContent>
                <Box width={300} height={300}>
                    <NodeDisplay node={node}/>
                </Box>
            </CardContent>
            <CardActions>
                <Button size="small">add</Button>
            </CardActions>
        </Card>
    );

});

export const TaskTemplateList = observer(() => {
    return (
        <Stack direction="column" spacing={2}>
            {state.taskTemplates.map((item) => <TaskTemplateItem key={item.id} item={item}/>)}
        </Stack>
    )
});