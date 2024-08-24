import { observer, useLocalObservable } from "mobx-react-lite";
import { Dialog, DialogTitle, DialogContent, TextField, DialogActions, Button } from "@mui/material";
import { useEffect } from "react";
import { autorun } from "mobx";
import { useRootStore } from "../state/root-store";
import { Dashboard } from "../types/dashboard";
import { useNavigate } from "react-router-dom";

export const DashboardEditorDialog = observer(() => {
    const rootStore = useRootStore();
    const navigate = useNavigate();
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
        <Dialog fullWidth open={state.isOpen} onClose={() => rootStore.uiControl.closeDashboardEditor()}>
            <form onSubmit={async e => {
                e.preventDefault();
                if (!state.editingDashboard) return;
                await rootStore.dashboard.put(state.editingDashboard);
                navigate(`/dashboard/${state.editingDashboard.id}`);
                rootStore.uiControl.closeDashboardEditor();
            }}>
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
                        variant="filled"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={async () => {
                        if (!state.editingDashboard) return;
                        await rootStore.dashboard.delete(state.editingDashboard.id);
                        rootStore.uiControl.closeDashboardEditor();
                    }}>Delete</Button>
                    <Button type="submit">Save</Button>
                </DialogActions>
            </form>
        </Dialog>
    );
});