import "@material/web/button/filled-button.js";
import "@material/web/textfield/filled-text-field.js";
import { html } from "lit-html";
import { ref, createRef } from "lit-html/directives/ref.js";


const textFieldRef = createRef();

export function renderUI(value, config, setValue) {
    return html`
    <div>
        <md-filled-text-field ${ref(textFieldRef)} style="width: 100%;resize: vertical;" label="Text" type="textarea"></md-filled-text-field>
        <div class="height-spacer"></div>
        <div class="flex-row flex-row--center">
            <div class="flex-spacer"></div>
            <md-filled-button @click=${e => {
                setValue({ value: textFieldRef.value.value });
                textFieldRef.value.value = "";
            }}>send</md-filled-button>
        </div>
    </div>
    `;
}