import "@material/web/radio/radio.js";
import { html } from "lit-html";

export function renderUI(value, config, setValue) {
    return html`
    <div class="flex-column flex-column--spaced flex-column--padded">
    ${config.button_tracks.map(t => html`
    <div class="flex-row flex-row--center flex-row--spaced">
        <md-radio id=${"rb" + String(t.out_topic)} name="RADIO" ?checked=${value.selected_topic === t.out_topic} @change=${e => e.target.checked && setValue({ selected_topic: t.out_topic })}></md-radio>
        <label for=${"rb" + String(t.out_topic)} style="user-select:none;">${t.label}</label>
    </div>
    `)}
    <div>
    `;
}