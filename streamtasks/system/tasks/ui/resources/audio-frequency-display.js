import { html } from "lit-html";
import { ref, createRef } from "lit-html/directives/ref.js";

const script = document.createElement("script");
script.src = `https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.js`
document.body.appendChild(script);

let chartCanvasRef = createRef();
let chart = undefined;

export function renderUI(value, config) {
    const dataset = {
        label: 'Frequencies',
        data: value.freq_bins,
        fill: true,
        borderColor: 'rgb(75, 192, 192)',
    };

    if (chart == undefined && chartCanvasRef.value) {
        chart = new window.Chart(chartCanvasRef.value, {
            type: 'line',
            options: {
                animation: false,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        min: 0,
                        max: 1
                    }
                }
            },
            data: {
                labels: value.freq_bins.map((_, idx) => String(idx * config.bin_size) + "Hz"),
                datasets: [dataset]
            }
        });
    }
    if (chart !== undefined) {
        chart.data.datasets[0] = dataset;
        chart.update()
    }

    return html`<div style="width:100vw; height:100vh;"><canvas ${ref(chartCanvasRef)}></canvas></div>`;
}