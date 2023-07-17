import { TableContainer, Table, TableBody, TableRow, TableCell, Box, Stack, Typography, Divider, IconButton } from "@mui/material";
import { observer } from "mobx-react";
import React, { useMemo } from "react";
import { Task, TaskInputStream, TaskOutputStream, TaskStreamBase, streamToString } from "../../lib/task";
import { DeploymentState } from "../../state/deployment";
import { TaskNode } from "../../lib/task/node";
import { Delete as DeleteIcon } from "@mui/icons-material";

const TaskStreamDisplay = (props: { stream: TaskStreamBase }) => {
    const valueToString = (value: any) => {
        if (typeof value === "boolean") {
            return value ? "yes" : "no";
        }
        return String(value);
    }

    return (
        <Stack direction="column" alignItems="flex-start" paddingY={1}>
            <Typography variant="caption" lineHeight={1}>{streamToString(props.stream)}</Typography>
            {Object.entries(props.stream.extra ?? {}).map(([key, value], index) => (
                <Typography marginTop={index === 0 ? 0.5 : 0} lineHeight={1} variant="caption" color="GrayText">{key}: {valueToString(value)}</Typography>
            ))}
        </Stack>
    )
};

export const TaskEditor = observer((props: { taskNode: TaskNode, deployment: DeploymentState, onUnselect: () => void, onDelete: () => void }) => {
    const mappedStreams = useMemo(() => {
        const streams: [(TaskInputStream | undefined), (TaskOutputStream | undefined)][] = [];

        for (let i = 0; i < props.taskNode.task.stream_groups.length; i++) {
            const group = props.taskNode.task.stream_groups[i];

            for (let j = 0; j < Math.max(group.inputs.length, group.outputs.length); j++) {
                streams.push([group.inputs.at(j), group.outputs.at(j)]);
            }

            if (i + 1 !== props.taskNode.task.stream_groups.length) {
                streams.push([undefined, undefined]);
            }
        }

        return streams;
    }, [props.taskNode])

    return (
        <Stack direction="column" padding={2}>
            <Stack direction="row" alignItems="center" paddingBottom={1}>
                <Typography variant="subtitle1" gutterBottom>{props.taskNode.getName()}</Typography>
                <Box flex={1} />
                <Box>
                    <IconButton onClick={props.onDelete}>
                        <DeleteIcon sx={{ width: "15px", height: "15px" }} />
                    </IconButton>
                </Box>
            </Stack>
            <Divider sx={{ width: "100%" }} />
            <TableContainer>
                <Table size="small">
                    <TableBody>
                        {mappedStreams.map(([input, output], i) => (
                            <TableRow key={(input?.ref_id ?? "") + (output?.topic_id ?? "")}>
                                <TableCell padding="none" align="left">{input ? <TaskStreamDisplay stream={input} /> : <Box height={1} />}</TableCell>
                                <TableCell padding="none" align="left">{output ? <TaskStreamDisplay stream={output} /> : <Box height={1} />}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Stack>
    );
});