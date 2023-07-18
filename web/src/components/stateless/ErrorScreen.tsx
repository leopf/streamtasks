import { Button, Stack, Typography } from "@mui/material";
import React from "react";

export function ErrorScreen() {
    return(
        <Stack direction="column" alignItems="center" justifyContent="center" height="100%" width="100%">
            <Typography variant="h4">Error</Typography>
            <Typography variant="body1">Something went wrong!</Typography>
            <Button href="/" sx={{ marginTop: 2 }}>Back to Homepage</Button>
        </Stack>
    );
}