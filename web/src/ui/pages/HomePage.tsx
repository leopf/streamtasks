import { Add as AddIcon, Edit as EditIcon } from "@mui/icons-material";
import { Box, Button, Container, Dialog, DialogActions, DialogContent, DialogTitle, Fab, Grid, IconButton, Stack, TextField, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { Deployment, PartialDeployment } from "../../types/deployment";
import { useRootStore } from "../../state/root-store";
import { NodeOverlayTile } from "../components/NodeOverlayTile";
import { Link } from "react-router-dom";
import { PageLayout } from "../Layout";
import { useUIControl } from "../../state/ui-control-store";

export const HomePage = observer(() => {
    const rootStore = useRootStore();
    const uiControl = useUIControl();

    return (
        <PageLayout>
            <Box width="100%" height="100%" sx={{ overflowY: "auto" }}>
                <Container>
                    <Box paddingY={10}>
                        <Typography variant="h2" gutterBottom>Deployments</Typography>
                        <Grid container spacing={2}>
                            {rootStore.deployments.map(d => (
                                <Grid item key={d.id} xs={3}>
                                    <NodeOverlayTile header={(
                                        <Stack direction="row">
                                            <Box flex={1} />
                                            <IconButton size="small" onClick={() => uiControl.editingDeployment = d}>
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
                    <Fab color="primary" onClick={() => uiControl.createNewDeployment()}><AddIcon /></Fab>
                </Box>
            </Box>
        </PageLayout>
    );
});