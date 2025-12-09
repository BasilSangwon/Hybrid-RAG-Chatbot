// Section 4: Monitoring & Debugging

async function loadUsageStats() {
    try {
        const resStats = await fetch(API + '/api/stats');
        const dataStats = await resStats.json();
        document.getElementById('total_cost').innerText = `$${dataStats.total_cost}`;
        document.getElementById('total_input').innerText = dataStats.total_input_tokens || 0;
        document.getElementById('total_output').innerText = dataStats.total_output_tokens || 0;

        const resUsage = await fetch(API + '/api/usage');
        const dataUsage = await resUsage.json();
        const list = document.getElementById('usageList');
        if (dataUsage.length === 0) {
            list.innerHTML = '<div style="text-align:center; color:#94a3b8; font-size:12px; padding:10px;">No usage data yet.</div>';
            return;
        }
        list.innerHTML = `<table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead style="background:#f1f5f9; color:#64748b;">
                <tr><th style="padding:8px; text-align:left;">Model</th><th style="padding:8px; text-align:right;">Input</th><th style="padding:8px; text-align:right;">Output</th><th style="padding:8px; text-align:right;">Cost</th><th style="padding:8px; text-align:right;">Time</th></tr>
            </thead>
            <tbody>
                ${dataUsage.map(d => `
                    <tr style="border-bottom:1px solid #e2e8f0;">
                        <td style="padding:8px; color:#334155; font-weight:600;">${d.model_name}</td>
                        <td style="padding:8px; text-align:right; color:#475569;">${d.input_tokens}</td>
                        <td style="padding:8px; text-align:right; color:#475569;">${d.output_tokens}</td>
                        <td style="padding:8px; text-align:right; color:#059669; font-weight:bold;">$${d.cost_usd.toFixed(5)}</td>
                        <td style="padding:8px; text-align:right; color:#94a3b8; font-size:11px;">${new Date(d.timestamp).toLocaleTimeString()}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>`;
    } catch (e) { console.error("Usage Stats Load Error", e); }
}

async function runSearchTest() {
    const mode = document.getElementById('debug_mode').value;
    const query = document.getElementById('debug_query').value;
    if (!query) return alert("질문을 입력하세요");
    document.getElementById('debugResult').innerText = "검색 중...";
    try {
        const res = await fetch(API + '/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: query, model: 'gemini-2.0-flash', rag_type: mode, session_id: 'debug' })
        });
        const text = await res.text();
        document.getElementById('debugResult').innerText = text;
    } catch (e) {
        document.getElementById('debugResult').innerText = "Error: " + e;
    }
}
