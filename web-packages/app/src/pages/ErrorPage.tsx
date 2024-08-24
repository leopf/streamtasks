import { Box, Container, Typography } from "@mui/material";
import { useRouteError } from "react-router-dom";

export function ErrorPage() {
    const error = useRouteError();

    return (
        <Box width="100%" height="100%" sx={{ overflowY: "auto" }}>
            <Container>
                <Box paddingY={10}>
                    <Typography variant="h2" gutterBottom>{error ? String(error) : "Not found"}</Typography>
                </Box>
            </Container>
        </Box>
    );
};