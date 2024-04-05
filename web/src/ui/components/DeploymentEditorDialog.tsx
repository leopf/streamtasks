import { observer, useLocalObservable } from "mobx-react-lite";
import { useUIControl } from "../../state/ui-control-store";
import { useRootStore } from "../../state/root-store";
import { Dialog, DialogTitle, DialogContent, TextField, DialogActions, Button } from "@mui/material";
import { Deployment, PartialDeployment } from "../../types/deployment";
import { useEffect } from "react";
import { autorun } from "mobx";

export const DeploymentEditorDialog = observer(() => {
    const uiControl = useUIControl();
    const rootStore = useRootStore();

    const state = useLocalObservable(() => ({
        get isNewDeployment() {
            return !(this.editingDeployment as any)?.id
        },
        editingDeployment: undefined as undefined | PartialDeployment | Deployment
    }));

    useEffect(() => {
        return autorun(() => {
            if (uiControl.editingDeployment) {
                state.editingDeployment = { ...uiControl.editingDeployment };
            }
            else {
                state.editingDeployment = undefined;
            }
        })
    }, []);

    return (
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
                    uiControl.editingDeployment = undefined;
                }}>Save</Button>
            </DialogActions>
        </Dialog>
    );
});