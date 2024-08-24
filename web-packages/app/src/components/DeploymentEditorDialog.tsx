import { observer, useLocalObservable } from "mobx-react-lite";
import { Dialog, DialogTitle, DialogContent, TextField, DialogActions, Button } from "@mui/material";
import { useEffect } from "react";
import { autorun } from "mobx";
import { useRootStore } from "../state/root-store";
import { Deployment, FullDeployment, PartialDeployment } from "../types/deployment";
import { useNavigate } from "react-router-dom";

export const DeploymentEditorDialog = observer(() => {
    const rootStore = useRootStore();
    const navigate = useNavigate();
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
            <form onSubmit={async e => {
                e.preventDefault();
                if (!state.editingDeployment) return;
                let newDeployment: FullDeployment;
                if (state.isNew) {
                    newDeployment = await rootStore.deployment.create(state.editingDeployment);
                }
                else {
                    newDeployment = await rootStore.deployment.update(state.editingDeployment as Deployment);
                }
                navigate(`/deployment/${newDeployment.id}`);
                rootStore.uiControl.closeDeploymentEditor();
            }}>
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
                        variant="filled"
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
                    <Button type="submit">Save</Button>
                </DialogActions>
            </form>
        </Dialog>
    );
});