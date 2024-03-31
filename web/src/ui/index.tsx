import { createRoot } from 'react-dom/client';
import { App } from './App';
import { GlobalStateContext } from '../state';
import { TaskManager } from '../state/task-manager';

const root = createRoot(document.getElementById("root")!);
root.render((
    <GlobalStateContext.Provider value={{ taskManager: new TaskManager() }}>
        <App />
    </GlobalStateContext.Provider>
))