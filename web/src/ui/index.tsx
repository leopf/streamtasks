import { configure } from 'mobx';
configure({ enforceActions: "never" })

import { createRoot } from 'react-dom/client';
import { App } from './App';
import { TaskManager, TaskManagerContext } from '../state/task-manager';
import { RootStore, RootStoreContext } from '../state/root-store';
import { UIControlContext, UIControlStore } from '../state/ui-control-store';

const root = createRoot(document.getElementById("root")!);
root.render((
    <RootStoreContext.Provider value={new RootStore()}>
        <UIControlContext.Provider value={new UIControlStore()}>
            <TaskManagerContext.Provider value={new TaskManager()}>
                <App />
            </TaskManagerContext.Provider>
        </UIControlContext.Provider>
    </RootStoreContext.Provider>
))