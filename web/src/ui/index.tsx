import { configure } from 'mobx';
configure({ enforceActions: "never" })

import { createRoot } from 'react-dom/client';
import { App } from './App';
import { TaskManager, TaskManagerContext } from '../state/task-manager';

const root = createRoot(document.getElementById("root")!);
root.render((
    <TaskManagerContext.Provider value={new TaskManager()}>
        <App />
    </TaskManagerContext.Provider>
))