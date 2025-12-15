// Main Entry Point & Polling

async function checkServerStatus() {
    const statusBadge = document.getElementById('server-status');
    const statusText = document.getElementById('status-text');

    // AbortController for older browser compatibility
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
        const res = await fetch(API + '/api/personas', { method: 'GET', signal: controller.signal });
        clearTimeout(timeoutId);
        if (res.ok) {
            if (!isServerOnline) {
                if (statusBadge) statusBadge.className = 'status-badge online';
                if (statusText) statusText.innerText = "서버 정상 (Online)";
                isServerOnline = true;
                refreshAllData();
            }
        } else throw new Error();
    } catch (e) {
        clearTimeout(timeoutId);
        if (isServerOnline || (statusText && statusText.innerText.includes("시도 중"))) {
            if (statusBadge) statusBadge.className = 'status-badge offline';
            if (statusText) statusText.innerText = "연결 끊김 (Offline)";
            isServerOnline = false;
        }
    }
}

async function checkJobStatus() {
    if (!isServerOnline) return;
    try {
        const res = await fetch(API + '/api/job_status');
        const status = await res.json();

        const btnVec = document.getElementById('btnVector');
        if (btnVec) {
            if (status.vector === 'running') {
                btnVec.disabled = true;
                btnVec.innerText = "⏳ Vector 임베딩 진행 중...";
            } else {
                btnVec.disabled = false;
                btnVec.innerText = "⚡ Vector DB 임베딩 시작";
                if (lastVectorStatus === 'running') {
                    loadDBStats(); loadUsageStats(); loadExperiments();
                    alert("Vector 임베딩이 완료되었습니다!");
                }
            }
        }
        lastVectorStatus = status.vector;

        const btnGraph = document.getElementById('btnGraph');
        if (btnGraph) {
            if (status.graph === 'running') {
                btnGraph.disabled = true;
                btnGraph.innerText = "⏳ Graph 구축 진행 중...";
            } else {
                btnGraph.disabled = false;
                btnGraph.innerText = "🏗️ 구축 시작 (데이터 추가)";
                if (lastGraphStatus === 'running') {
                    loadDBStats(); loadUsageStats(); loadExperiments();
                    alert("Graph 구축이 완료되었습니다!");
                }
            }
        }
        lastGraphStatus = status.graph;
    } catch (e) { }
}

function refreshAllData() {
    loadPersonas();
    loadFiles();
    loadAnswers();
    loadFeedback();
    loadFileOptions();
    loadDBStats();
    loadAvailableModels();
    loadUsageStats();
    loadExperiments();
}

// Start Loops
setInterval(checkServerStatus, 3000);
checkServerStatus();
setInterval(checkJobStatus, 2000);
