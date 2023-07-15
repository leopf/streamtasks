import { CircularProgress, Stack } from "@mui/material";
import React from "react";

export function LoadingScreen() {
    return(
        <Stack direction="column" alignItems="center" justifyContent="center" height="100%" width="100%">
            <CircularProgress size={"4rem"} />
        </Stack>
    );
}