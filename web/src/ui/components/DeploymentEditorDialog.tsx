import { observer, useLocalObservable } from "mobx-react-lite";
import { useRootStore } from "../../state/root-store";
import { Dialog, DialogTitle, DialogContent, TextField, DialogActions, Button } from "@mui/material";
import { Deployment, PartialDeployment } from "../../types/deployment";
import { useEffect } from "react";
import { autorun } from "mobx";

export const DeploymentEditorDialog = observer(() => {
    const rootStore = useRootStore();

    const state = useLocalObservable(() => ({
        get isNewDeployment() {
            return !(this.editingDeployment as any)?.id
        },
        editingDeployment: undefined as undefined | PartialDeployment | Deployment
    }));

    useEffect(() => autorun(() => {
        if (rootStore.uiControl.editingDeployment) {
            state.editingDeployment = { ...rootStore.uiControl.editingDeployment };
        }
        else {
            state.editingDeployment = undefined;
        }
    }), []);

    return (
        <Dialog fullWidth open={!!state.editingDeployment} onClose={() => rootStore.uiControl.closeDeploymentEditor()}>
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
                        await rootStore.deployment.delete(id);
                        rootStore.uiControl.closeDeploymentEditor()
                    }}>Delete</Button>
                )}
                <Button onClick={async () => {
                    if (!state.editingDeployment) return;
                    if (state.isNewDeployment) {
                        await rootStore.deployment.create(state.editingDeployment);
                    }
                    else {
                        await rootStore.deployment.update(state.editingDeployment as Deployment);
                    }
                    rootStore.uiControl.closeDeploymentEditor();
                }}>Save</Button>
            </DialogActions>
        </Dialog>
    );
});