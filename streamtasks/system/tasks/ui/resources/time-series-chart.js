import { html } from "lit-html";
import { ref, createRef } from "lit-html/directives/ref.js";

const cjsScript = document.createElement("script");
cjsScript.src = `https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.js`;
document.body.appendChild(cjsScript);

const cjsDateScript = document.createElement("script");
cjsDateScript.src = `https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js`;
document.body.appendChild(cjsDateScript);

let chartCanvasRef = createRef();
let chart = undefined;

export function renderUI(value, config) {
  const dataset = {
    label: config.y_label,
    data: value.values.map((point) => ({
      x: point.date,
      y: point.value
    })),
    borderColor: 'rgb(75, 192, 192)',
    fill: false
  };

  if (chart === undefined && chartCanvasRef.value) {
    chart = new window.Chart(chartCanvasRef.value, {
      type: 'line',
      data: {
        datasets: [dataset]
      },
      options: {
        animation: false,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: 'time',
          },
          y: {
            type: 'linear',
            title: {
              display: true,
              text: config.y_label
            }
          }
        }
      }
    });
  } else if (chart !== undefined) {
    chart.data.datasets[0] = dataset;
    chart.update();
  }

  return html`
    <div style="width:100%; height:100%;">
      <canvas ${ref(chartCanvasRef)}></canvas>
    </div>
  `;
}
