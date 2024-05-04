import { configure } from 'mobx';
configure({ enforceActions: "never" })

import { createRoot } from 'react-dom/client';
import { App } from './App';
import { RootStore, RootStoreContext } from '../state/root-store';

const root = createRoot(document.getElementById("root")!);
root.render((
    <RootStoreContext.Provider value={new RootStore()}>
        <App />
    </RootStoreContext.Provider>
))