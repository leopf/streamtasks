import { Add as AddIcon, Edit as EditIcon } from "@mui/icons-material";
import { Box, Container, Fab, Grid, IconButton, Stack, Typography } from "@mui/material";
import { observer } from "mobx-react-lite";
import { useRootStore } from "../state/root-store";
import { NodeOverlayTile } from "../components/NodeOverlayTile";
import { Link } from "react-router-dom";
import { PageLayout } from "../Layout";

export const HomePage = observer(() => {
    const rootStore = useRootStore();

    return (
        <PageLayout>
            <Box width="100%" height="100%" sx={{ overflowY: "auto" }}>
                <Container>
                    <Box paddingY={10}>
                        <Typography variant="h2" gutterBottom>Deployments</Typography>
                        <Grid container spacing={2} columns={{ xs: 4, sm: 8, md: 12 }}>
                            {rootStore.deployment.deployments.map(d => (
                                <Grid item key={d.id} xs={4}>
                                    <NodeOverlayTile header={(
                                        <Stack direction="row">
                                            <Box flex={1} />
                                            <IconButton size="small" onClick={() => rootStore.uiControl.editingDeployment = d}>
                                                <EditIcon fontSize="inherit" />
                                            </IconButton>
                                        </Stack>
                                    )}>
                                        <Box component={Link} sx={{ display: "block", textDecoration: "none", color: "inherit" }} padding={2} to={`/deployment/${d.id}`}>
                                            <Typography variant="h5">{d.label}</Typography>
                                        </Box>
                                    </NodeOverlayTile>
                                </Grid>
                            ))}
                        </Grid>
                    </Box>
                </Container>
                <Box position="fixed" bottom="2rem" right="2rem">
                    <Fab color="primary" onClick={() => rootStore.uiControl.createNewDeployment()}><AddIcon /></Fab>
                </Box>
            </Box>
        </PageLayout>
    );
});