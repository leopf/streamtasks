import { observer, useLocalObservable } from "mobx-react-lite";
import { useRootStore } from "../../state/root-store";
import { Dialog, DialogTitle, DialogContent, TextField, DialogActions, Button } from "@mui/material";
import { useEffect } from "react";
import { autorun } from "mobx";
import { Dashboard } from "../../types/dashboard";

export const DashboardEditorDialog = observer(() => {
    const rootStore = useRootStore();

    const state = useLocalObservable(() => ({
        isOpen: false,
        editingDashboard: undefined as undefined | Dashboard
    }));

    useEffect(() => autorun(() => {
        if (rootStore.uiControl.editingDashboard) {
            state.editingDashboard = { ...rootStore.uiControl.editingDashboard };
        }
        state.isOpen = !!rootStore.uiControl.editingDashboard;
    }), []);

    return (
        <Dialog fullWidth open={state.isOpen} onClose={() => rootStore.uiControl.closeDeploymentEditor()}>
            <DialogTitle>Edit Dashboard</DialogTitle>
            <DialogContent>
                <TextField
                    value={state.editingDashboard?.label || ""}
                    onInput={(e) => {
                        if (state.editingDashboard) {
                            state.editingDashboard.label = (e.target as HTMLInputElement).value;
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
                <Button onClick={async () => {
                    const id = state.editingDashboard?.id;
                    if (!id) return;
                    await rootStore.dashboard.delete(id);
                    rootStore.uiControl.closeDashboardEditor()
                }}>Delete</Button>
                <Button onClick={async () => {
                    if (!state.editingDashboard) return;
                    await rootStore.dashboard.put(state.editingDashboard);
                    rootStore.uiControl.closeDashboardEditor();
                }}>Save</Button>
            </DialogActions>
        </Dialog>
    );
});