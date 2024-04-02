import { configure, observable } from 'mobx';
configure({ enforceActions: "never" })

import { createRoot } from 'react-dom/client';
import { App } from './App';
import { GlobalStateContext } from '../state';
import { TaskManager } from '../state/task-manager';
import { DeploymentState } from '../state/deployment';


const taskManager = new TaskManager();

const root = createRoot(document.getElementById("root")!);
root.render((
    <GlobalStateContext.Provider value={observable({ taskManager: taskManager, deployment: new DeploymentState("1", taskManager) })}>
        <App />
    </GlobalStateContext.Provider>
))