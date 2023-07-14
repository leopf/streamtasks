import { Stack, Typography, Box, Container, Button, Divider } from "@mui/material";
import { observer } from "mobx-react";
import React from "react";
import { TitleBar } from "../components/stateful/TitleBar";
import { ShowSystemLogsButton } from "../components/stateful/ShowSystemLogsButton";

export const HomePage = observer((props: {}) => {
    return (
        <Stack direction="column" height={"100%"} maxHeight={"100%"}>
            <TitleBar>
                <Stack height="100%" direction="row" alignItems="center" boxSizing="border-box">
                    <Typography lineHeight={1} fontSize={18} >Home</Typography>
                    <Box flex={1} />
                    <ShowSystemLogsButton />
                </Stack>
            </TitleBar>
            <Box flex={1} sx={{ overflowY: "auto" }} width="100%">
                <Container>
                    <Box paddingTop={8}>
                        <Stack direction="row">
                            <Typography variant="h6">Create a deployment</Typography>
                            <Box flex={1} />
                            <Button variant="contained" color="primary">Create</Button>
                        </Stack>
                        <Divider/>
                    </Box>
                </Container>
            </Box>
        </Stack>
    );
});