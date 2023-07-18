import { TableContainer, Table, TableBody, TableRow, TableCell, Box, Stack, Typography, Divider, IconButton } from "@mui/material";
import { observer } from "mobx-react";
import React, { useMemo } from "react";
import { Task, TaskInputStream, TaskOutputStream, TaskStreamBase, streamToString } from "../../lib/task";
import { DeploymentState } from "../../state/deployment";
import { TaskNode } from "../../lib/task/node";
import { Delete as DeleteIcon, OpenInNew as OpenInNewIcon } from "@mui/icons-material";
import { TopicDataModal } from "../stateless/TopicDataModal";

const TaskStreamDisplay = (props: { stream: TaskStreamBase, allowOpen: boolean, onOpen: () => void }) => {
    const valueToString = (value: any) => {
        if (typeof value === "boolean") {
            return value ? "yes" : "no";
        }
        return String(value);
    }

    return (
        <Stack direction="column" alignItems="flex-start" paddingY={1}>
            <Stack direction="row" spacing={2} alignItems="center">
                <Typography variant="caption" lineHeight={1}>{streamToString(props.stream)}</Typography>
                {props.allowOpen && (
                    <IconButton onClick={props.onOpen}>
                        <OpenInNewIcon sx={{ width: "15px", height: "15px" }} />
                    </IconButton>
                )}
            </Stack>
            {Object.entries(props.stream.extra ?? {}).map(([key, value], index) => (
                <Typography marginTop={index === 0 ? 0.5 : 0} lineHeight={1} variant="caption" color="GrayText">{key}: {valueToString(value)}</Typography>
            ))}
        </Stack>
    )
};

export const TaskEditor = observer((props: { taskNode: TaskNode, deployment: DeploymentState, onUnselect: () => void, onDelete: () => void }) => {
    const [openStreamId, setOpenStreamId] = React.useState<string | undefined>(undefined);
    const [openStreamTitle, setOpenStreamTitle] = React.useState<string>("");

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

    const openStream = (stream: TaskInputStream | TaskOutputStream) => {
        setOpenStreamId(stream.topic_id);
        setOpenStreamTitle(`${props.taskNode.getName()}: ${streamToString(stream)}`);
    };

    return (
        <>
            <TopicDataModal topic_id={openStreamId} title={openStreamTitle} onClose={() => setOpenStreamId(undefined)} />
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
                                    <TableCell padding="none" align="left">{
                                        input ?
                                            <TaskStreamDisplay allowOpen={props.deployment.isStarted} stream={input} onOpen={() => openStream(input)} /> :
                                            <Box height={1} />
                                    }</TableCell>
                                    <TableCell padding="none" align="left">{
                                        output ?
                                            <TaskStreamDisplay allowOpen={props.deployment.isStarted} stream={output} onOpen={() => openStream(output)} /> :
                                            <Box height={1} />
                                    }</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Stack>
        </>
    );
});