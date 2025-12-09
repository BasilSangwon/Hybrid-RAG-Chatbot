// Chart & Table Utilities

/**
 * Renders a data table or a 'no data' message.
 * @param {string} tableId - The DOM ID of the table
 * @param {Array} data - Array of data objects
 */
function renderTable(tableId, data) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) return;

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#94a3b8;">데이터가 없습니다 (No experiments yet).</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(e => `
        <tr>
            <td>${e.id}</td>
            <td style="font-weight:bold;">${e.name}</td>
            <td style="font-size:11px;">
                ${e.config.chunk_size ? `Chunk: ${e.config.chunk_size}` : ''}
                ${e.config.llm_model ? `<br>Model: ${e.config.llm_model}` : ''}
            </td>
            <td style="text-align:right; font-weight:bold;">${e.count}</td>
            <td style="text-align:center;">
                <button onclick="deleteExperiment(${e.id})" class="btn btn-sm btn-danger">삭제</button>
            </td>
        </tr>
    `).join('');
}

/**
 * Updates or creates a Chart.js instance.
 * @param {string} canvasId 
 * @param {Array} data 
 * @param {string} label 
 * @param {string} color 
 */
function updateChart(canvasId, data, label, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const recent = data.slice(0, 5).reverse();
    const labels = recent.map(d => d.name);
    const counts = recent.map(d => d.count);

    const config = {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: counts,
                backgroundColor: color,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
        }
    };

    if (canvasId === 'vectorChart') {
        if (vectorChartInstance) vectorChartInstance.destroy();
        vectorChartInstance = new Chart(ctx, config);
    } else {
        if (graphChartInstance) graphChartInstance.destroy();
        graphChartInstance = new Chart(ctx, config);
    }
}
