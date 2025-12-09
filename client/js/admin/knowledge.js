// Section 2: Knowledge Base Ingestion (Files, Vector, Graph)

// --- Files ---
async function loadFiles() {
    try {
        const res = await fetch(API + '/api/files');
        const files = await res.json();
        const fileList = document.getElementById('fileList');
        if (fileList) {
            fileList.innerHTML = files.map(f => `
                <div class="list-item">
                    <span class="item-title">📄 ${f}</span>
                    <button onclick="deleteFile('${f}')" class="btn btn-sm btn-danger">삭제</button>
                </div>
            `).join('');
        }
    } catch (e) { console.error("Load Files Failed", e); }
}

async function deleteFile(filename) {
    if (confirm(`정말로 ${filename} 파일을 삭제하시겠습니까?`)) {
        await fetch(API + `/api/files/${filename}`, { method: 'DELETE' });
        loadFiles();
        loadFileOptions(); // update dropdowns
    }
}

async function uploadPdf() {
    const file = document.getElementById('pdfInput').files[0];
    if (!file) return alert("파일 선택 필요");
    const form = new FormData();
    form.append("file", file);
    await fetch(API + '/api/upload', { method: 'POST', body: form });
    alert("업로드 완료");
    loadFiles();
    loadFileOptions();
}

async function loadFileOptions() {
    try {
        const res = await fetch(API + '/api/files');
        const files = await res.json();
        const select = document.getElementById('qa_source_file');
        if (select) {
            select.innerHTML = '<option value="">파일 선택...</option>' +
                files.map(f => `<option value="${f}">${f}</option>`).join('');
        }
    } catch (e) { }
}

// --- Vector RAG ---
async function runVectorIndex() {
    if (!isServerOnline) return alert("서버 연결 필요");
    const name = document.getElementById('vec_exp_name').value;
    const chunkSize = parseInt(document.getElementById('vec_chunk_size').value) || 1000;
    const overlap = parseInt(document.getElementById('vec_chunk_overlap').value) || 100;
    const topK = parseInt(document.getElementById('vec_top_k').value) || 5;

    if (!confirm(`[${name || 'Auto-Generate'}] Vector 실험을 시작하시겠습니까?`)) return;

    const payload = {
        type: 'vector',
        name: name,
        config: { chunk_size: chunkSize, chunk_overlap: overlap, top_k: topK }
    };

    await fetch(API + '/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    alert("백그라운드에서 임베딩 실험이 시작되었습니다.");
}

async function resetVectorDB() {
    if (confirm("정말로 Vector DB를 초기화하시겠습니까? (복구 불가)")) {
        await fetch(API + '/api/vector_store', { method: 'DELETE' });
        alert("초기화됨");
        loadDBStats();
    }
}

// --- Graph RAG ---
async function runGraphIndex() {
    if (!isServerOnline) return alert("서버 연결 필요");
    const name = document.getElementById('graph_exp_name').value;
    const model = document.getElementById('graph_llm_select').value;
    const temp = parseFloat(document.getElementById('graph_temp').value);
    const prompt = document.getElementById('graph_prompt').value;

    const chunkSize = parseInt(document.getElementById('graph_chunk_size').value) || 2000;
    const overlap = parseInt(document.getElementById('graph_chunk_overlap').value) || 200;

    if (!confirm(`[${name || 'Auto-Generate'}] Graph 실험을 시작하시겠습니까? (Model: ${model}, Chunk: ${chunkSize})`)) return;

    const payload = {
        type: 'graph',
        name: name,
        config: {
            llm_model: model,
            temperature: temp,
            prompt_template: prompt,
            chunk_size: chunkSize,
            chunk_overlap: overlap
        }
    };

    await fetch(API + '/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    alert("백그라운드에서 Graph 실험이 시작되었습니다.");
}

async function deleteGraphModel() {
    alert("기능 준비 중입니다. 위의 모델별 삭제 버튼을 이용해주세요.");
}

async function deleteGraphModelData(modelName) {
    if (!confirm(`정말로 '${modelName}' 모델로 생성된 모든 그래프 데이터를 삭제하시겠습니까?`)) return;
    try {
        const res = await fetch(API + `/api/graph/model/${modelName}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'ok') {
            alert(data.message);
            loadDBStats();
        } else {
            alert("삭제 실패: " + data.message);
        }
    } catch (e) { alert("오류: " + e); }
}

async function loadModels() {
    const sel = document.getElementById('graph_llm_select');
    try {
        const res = await fetch(API + '/api/models');
        const models = await res.json();
        const groups = { "Gemini 3 Series": [], "Gemini 2.5 Series": [], "Gemini 2.0 Series": [], "Gemini 1.5 Series": [], "Others": [] };

        models.forEach(m => {
            const name = m.id;
            if (name.includes("gemini-3")) groups["Gemini 3 Series"].push(m);
            else if (name.includes("gemini-2.5")) groups["Gemini 2.5 Series"].push(m);
            else if (name.includes("gemini-2.0")) groups["Gemini 2.0 Series"].push(m);
            else if (name.includes("gemini-1.5")) groups["Gemini 1.5 Series"].push(m);
            else groups["Others"].push(m);
        });

        let html = "";
        for (const [label, list] of Object.entries(groups)) {
            if (list.length > 0) {
                html += `<optgroup label="${label}">` + list.map(m => `<option value="${m.id}">${m.display_name}</option>`).join('') + `</optgroup>`;
            }
        }
        sel.innerHTML = html;
        checkGraphModelStatus();
    } catch (e) {
        sel.innerHTML = '<option value="gemini-2.0-flash">Gemini 2.0 Flash (Fallback)</option>';
    }
}

function checkGraphModelStatus() {
    const sel = document.getElementById('graph_llm_select');
    const statusDiv = document.getElementById('model_learn_status');
    if (!sel || !statusDiv) return;

    if (learnedModels.includes(sel.value)) statusDiv.innerHTML = `<span style="color:#166534;">✅ 이미 학습된 모델입니다.</span>`;
    else statusDiv.innerHTML = `<span style="color:#94a3b8;">❌ 아직 학습되지 않은 모델입니다.</span>`;
}

// --- Stats & Experiments ---
async function loadDBStats() {
    try {
        const res = await fetch(API + '/api/stats');
        const data = await res.json();

        // Vector Badge
        const vBadge = document.getElementById('stat_vector');
        const count = data.vector_count || 0;
        vBadge.innerText = `현재: ${count} Chunks`;
        if (count === 0) {
            vBadge.style.color = '#ef4444';
            vBadge.style.background = '#fee2e2';
            document.getElementById('vector_status_msg').style.display = 'block';
        } else {
            vBadge.style.color = '#0369a1';
            vBadge.style.background = '#e0f2fe';
            document.getElementById('vector_status_msg').style.display = 'none';
        }

        // Graph Badge
        const gBadge = document.getElementById('stat_graph');
        gBadge.innerText = `현재: ${data.graph_count} Nodes`;
        gBadge.style.color = data.graph_count > 0 ? '#7c3aed' : '#64748b';
        gBadge.style.background = data.graph_count > 0 ? '#f3e8ff' : '#f1f5f9';

        // Graph Details Table
        const graphDetails = data.graph_details || [];
        learnedModels = graphDetails.map(d => d.model);
        const graphStatusDiv = document.getElementById('current_graph_model_container');
        if (graphStatusDiv) {
            if (graphDetails.length === 0) {
                graphStatusDiv.innerHTML = `<div style="padding:10px; text-align:center; color:#94a3b8;">데이터 없음</div>`;
            } else {
                graphStatusDiv.innerHTML = `<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:5px;">
                    <thead style="background:#f5f3ff; color:#5b21b6;">
                        <tr><th style="padding:6px; text-align:left;">Model Name</th><th style="padding:6px; text-align:center;">Files</th><th style="padding:6px; text-align:right;">Nodes</th><th style="padding:6px; text-align:center;">Action</th></tr>
                    </thead>
                    <tbody>
                        ${graphDetails.map(d => `
                            <tr style="border-bottom:1px solid #ddd6fe;">
                                <td style="padding:6px; font-weight:600; color:#4c1d95;">${d.model}</td>
                                <td style="padding:6px; text-align:center;">${d.files ? d.files.length : 0} files</td>
                                <td style="padding:6px; text-align:right;">${d.count}</td>
                                <td style="padding:6px; text-align:center;">
                                    <button onclick="deleteGraphModelData('${d.model}')" style="padding:2px 6px; font-size:11px; background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; border-radius:4px; cursor:pointer;">삭제</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`;
            }
        }
        checkGraphModelStatus();
    } catch (e) { console.error("Load DB Stats Failed", e); }
}

async function loadExperiments() {
    try {
        const res = await fetch(API + '/api/experiments');
        const data = await res.json();

        renderTable('vectorTable', data.vector);
        renderTable('graphTable', data.graph);

        updateChart('vectorChart', data.vector, 'Vector Chunks', '#0284c7');
        updateChart('graphChart', data.graph, 'Graph Nodes', '#7c3aed');
    } catch (e) { console.error("Failed to load experiments", e); }
}

async function deleteExperiment(id) {
    if (!confirm("정말로 이 실험 데이터를 삭제하시겠습니까? (복구 불가)")) return;
    try {
        const res = await fetch(API + `/api/experiments/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'ok') {
            alert(data.message);
            loadExperiments();
            loadDBStats();
        } else {
            alert("삭제 실패: " + data.message);
        }
    } catch (e) { alert("Error: " + e); }
}
