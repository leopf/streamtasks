import { Stack, Typography, Box } from "@mui/material";
import { observer } from "mobx-react";
import React from "react";
import { TitleBar } from "../components/stateful/TitleBar";
import { ShowSystemLogsButton } from "../components/stateful/ShowSystemLogsButton";

export const HomePage = observer((props: {}) => {
    return (
        <Stack direction="column" height={"100%"} maxHeight={"100%"}>
            <TitleBar>
                <Stack height="100%" direction="row" alignItems="center" boxSizing="border-box">
                    <Typography  fontSize={18} >Home</Typography>
                    <Box flex={1} />
                    <ShowSystemLogsButton />
                </Stack>
            </TitleBar>
            <Box flex={1} sx={{ overflowY: "hidden" }} width="100%">
                <Stack direction="row" height="100%" maxHeight="100%" maxWidth="100%">
                    
                </Stack>
            </Box>
        </Stack>
    );
});