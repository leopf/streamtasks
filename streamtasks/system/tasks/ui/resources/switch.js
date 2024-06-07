import "@material/web/switch/switch.js";
import { html } from "lit-html";

export function renderUI(value, config, setValue) {
    return html`
    <div class="flex-row flex-row--center flex-row--spaced">
        <md-switch ?selected=${value.value} @change=${e => setValue({ value: !!e.target.selected })}></md-switch>
        <label>${config.label}</label>
    </div>
    `;
}