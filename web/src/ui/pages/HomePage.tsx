import { Add as AddIcon, Edit as EditIcon } from "@mui/icons-material";
import { Box, Button, Container, Dialog, DialogActions, DialogContent, DialogTitle, Fab, Grid, IconButton, Stack, TextField, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { Deployment, PartialDeployment } from "../../types/deployment";
import { useRootStore } from "../../state/root-store";
import { NodeOverlayTile } from "../components/NodeOverlayTile";
import { Link } from "react-router-dom";

export const HomePage = observer(() => {
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        editingDeployment: undefined as PartialDeployment | Deployment | undefined,
        get isNewDeployment() {
            return !(this.editingDeployment as any)?.id;
        }
    }));

    return (
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
                                        <IconButton size="small" onClick={() => state.editingDeployment = d}>
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
            <Dialog fullWidth open={!!state.editingDeployment} onClose={() => state.editingDeployment = undefined}>
                <DialogTitle>{state.isNewDeployment ? "Create" : "Edit"} Deployment</DialogTitle>
                <DialogContent>
                    <TextField
                        value={state.editingDeployment?.label || ""}
                        onInput={(e) => {
                            if (state.editingDeployment) {
                                state.editingDeployment.label = (e.target as HTMLInputElement).value;
                            }
                        }}
                        autoFocus
                        required
                        label="Label"
                        fullWidth
                        variant="standard"
                    />
                </DialogContent>
                <DialogActions>
                    {!state.isNewDeployment && (
                        <Button onClick={async () => {
                            const id = (state.editingDeployment as any)?.id;
                            if (!id) return;
                            await rootStore.deleteDeployment(id);
                            state.editingDeployment = undefined;
                        }}>Delete</Button>
                    )}
                    <Button onClick={async () => {
                        if (!state.editingDeployment) return;
                        if (state.isNewDeployment) {
                            await rootStore.createDeployment(state.editingDeployment);
                        }
                        else {
                            await rootStore.updateDeployment(state.editingDeployment as Deployment);
                        }
                        state.editingDeployment = undefined;
                    }}>Save</Button>
                </DialogActions>
            </Dialog>
            <Box position="fixed" bottom="2rem" right="2rem">
                <Fab color="primary" onClick={() => state.editingDeployment = { label: "" }}><AddIcon /></Fab>
            </Box>
        </Box>
    );
});