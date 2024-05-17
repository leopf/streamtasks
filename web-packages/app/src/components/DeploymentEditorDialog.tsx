import { observer, useLocalObservable } from "mobx-react-lite";
import { Dialog, DialogTitle, DialogContent, TextField, DialogActions, Button } from "@mui/material";
import { useEffect } from "react";
import { autorun } from "mobx";
import { useRootStore } from "../state/root-store";
import { Deployment, PartialDeployment } from "../types/deployment";

export const DeploymentEditorDialog = observer(() => {
    const rootStore = useRootStore();

    const state = useLocalObservable(() => ({
        get isNew() {
            return !(this.editingDeployment as any)?.id
        },
        isOpen: false,
        editingDeployment: undefined as undefined | PartialDeployment | Deployment
    }));

    useEffect(() => autorun(() => {
        if (rootStore.uiControl.editingDeployment) {
            state.editingDeployment = { ...rootStore.uiControl.editingDeployment };
        }
        state.isOpen = !!rootStore.uiControl.editingDeployment;
    }), []);

    return (
        <Dialog fullWidth open={state.isOpen} onClose={() => rootStore.uiControl.closeDeploymentEditor()}>
            <DialogTitle>{state.isNew ? "Create" : "Edit"} Deployment</DialogTitle>
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
                {!state.isNew && (
                    <Button onClick={async () => {
                        const id = (state.editingDeployment as any)?.id;
                        if (!id) return;
                        await rootStore.deployment.delete(id);
                        rootStore.uiControl.closeDeploymentEditor()
                    }}>Delete</Button>
                )}
                <Button onClick={async () => {
                    if (!state.editingDeployment) return;
                    if (state.isNew) {
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