import { observer, useLocalObservable } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import { useRootStore } from "../../state/root-store";
import { PageLayout } from "../Layout";
import urlJoin from "url-join";
import { ConnectionManager } from "../components/path-regisrations/ConnectionManager";

export const PathRegistrationPage = observer(() => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        get dashboard() {
            return rootStore.pathRegistration.frontendPathRegistrations.find(r => r.id === params.id)
        }
    }));

    if (!state.dashboard) {
        throw new Error("Not found");
    }

    let innerContent: React.ReactNode = null;
    if (state.dashboard.frontend.path.startsWith("std:")) {
        if (state.dashboard.frontend.path === "std:connectionmanager") {
            innerContent = <ConnectionManager pathRegistration={state.dashboard}/>;
        }
    }
    else {
        const url = String(new URL(urlJoin("." + state.dashboard.path, state.dashboard.frontend.path), location.href));
        innerContent = <iframe style={{ display: "block", width: "100%", height: "100%", border: "none" }} src={url}></iframe>
    }


    return (
        <PageLayout>
            {innerContent}
        </PageLayout>
    )
});