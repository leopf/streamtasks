import { Box, IconButton, Stack, Tooltip, Typography } from "@mui/material";
import { useMemo } from "react";
import { Launch as LaunchIcon } from "@mui/icons-material";
import { getStreamColor } from "../lib/node-editor";
import { Metadata } from "@streamtasks/core";
import { ioMetadataHideKeys, ioFieldNameToLabel, ioFieldValueToText } from "../lib/task";

const ignoreFieldsForIOColor = new Set(["topic_id", "label", "key", "id"]);


export function TaskIOLabel(props: { io: Metadata, alignRight?: true, allowOpen?: boolean, onOpen?: () => void }) {
    const metadataKV = useMemo(() =>
        [...Object.entries(props.io)]
            .filter(([k, v]) => !ioMetadataHideKeys.has(k) && v !== undefined)
            .map(([k, v]) => [k, String(v)])
            .map(([k, v]) => [ioFieldNameToLabel(k), ioFieldValueToText(k, v)]), [props.io])
    const label = props.io["label"] ?? " - ";
    const color = useMemo(() => getStreamColor(props.io as Record<string, string | number | boolean>, ignoreFieldsForIOColor), [props.io]);

    return (
        <Tooltip title={(
            <Stack>
                {metadataKV.map(([k, v]) => (<Typography key={k} fontSize="0.8rem">{k}: {v}</Typography>))}
            </Stack>
        )}>
            <Stack spacing={1} direction={props.alignRight ? "row-reverse" : "row"} alignItems="center">
                <Box border="1px solid black" bgcolor={color} borderRadius="100%" height="0.7rem" width="0.7rem" />
                <Typography fontSize="0.9rem">{label}</Typography>
                {props.allowOpen && (
                    <IconButton size="small" onClick={props.onOpen}><LaunchIcon fontSize="inherit"/></IconButton>
                )}
            </Stack>
        </Tooltip>
    );
}