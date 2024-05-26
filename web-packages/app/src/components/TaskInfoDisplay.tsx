import { useMemo, useState } from "react";
import { Accordion, AccordionDetails, AccordionSummary, Box, Table, TableBody, TableCell, TableContainer, TableRow, Typography } from "@mui/material";
import { TaskIOTable } from "./TaskIOTable";
import { ExpandMore as ExpandMoreIcon } from "@mui/icons-material";
import { ManagedTask, TaskIO } from "@streamtasks/core";
import { generalStatusColors } from "../lib/status";
import { useRootStore } from "../state/root-store";

export function TaskInfoDisplay(props: { task: ManagedTask, updateCounter: number }) {
    const [infoExpanded, setInfoExpanded] = useState(false);
    const taskIO: TaskIO = useMemo(() => ({ inputs: props.task.inputs, outputs: props.task.outputs }), [props.task, props.updateCounter])
    const rootStore = useRootStore();
    const allowOpen = !!props.task.taskInstance;

    const taskHostInfo = useMemo(() => {
        const parsedTaskHost = props.task.parsedTaskHost;
        return [
            ["label", parsedTaskHost.label],
            ["node", parsedTaskHost.nodeName],
            ["description", parsedTaskHost.description],
            ["tags", parsedTaskHost.tags.join(", ") || undefined],
        ].filter(row => row[1] !== undefined) as [string, string][];
    }, [props.task])

    return (
        <>
            <Box padding={1} boxSizing="border-box">
                <Accordion expanded={infoExpanded} onChange={() => setInfoExpanded(pv => !pv)}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography>task host information</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <TableContainer>
                            <Table size="small">
                                <TableBody>
                                    {taskHostInfo.map(row => (
                                        <TableRow key={row[0]}>
                                            <TableCell valign="top"><Typography fontSize="0.8rem" fontWeight="600">{row[0]}</Typography></TableCell>
                                            <TableCell><Typography fontSize="0.8rem">{row[1]}</Typography></TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </AccordionDetails>
                </Accordion>
            </Box>
            <Box marginBottom={2}>
                <TaskIOTable
                    taskIO={taskIO}
                    onOpen={(tid) => rootStore.uiControl.selectedTopic = { topicId: tid, topicSpaceId: props.task.taskInstance?.topic_space_id ?? undefined }}
                    allowOpen={allowOpen} />
            </Box>
            <Box padding={1}>
                {!!props.task.taskInstance?.error && <Typography variant="h6" color={generalStatusColors.error}>Error: {props.task.taskInstance?.error}</Typography>}
            </Box>
        </>
    );
}