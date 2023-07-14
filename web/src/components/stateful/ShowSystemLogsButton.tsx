import { Tooltip, IconButton } from "@mui/material";
import { observer } from "mobx-react";
import React from "react";
import { ReceiptLong as LogsIcon } from "@mui/icons-material";
import { state } from "../../state";

export const ShowSystemLogsButton = observer((props: {}) => {
    return (
        <Tooltip title="logs">
        <IconButton size="small" sx={{ marginRight: 1 }} onClick={() => state.systemLogOpen = true}>
            <LogsIcon htmlColor="#fff" />
        </IconButton>
    </Tooltip>
    );
});
