// Section 1: Configuration & Policy (Personas & Feedback)

async function loadPersonas() {
    try {
        const res = await fetch(API + '/api/personas');
        const data = await res.json();
        document.getElementById('personaList').innerHTML = data.map(p => `
            <div class="list-item" style="${p.active ? 'border: 2px solid var(--accent); background: #f3e8ff;' : ''}">
                <div class="item-content">
                    <span class="item-title">${p.active ? '✅ ' : ''}${p.name}</span>
                    <span class="item-desc">${p.system_prompt}</span>
                </div>
                ${!p.active ? `<button onclick="activatePersona(${p.id})" class="btn btn-sm btn-accent">선택</button>` : '<span style="color:var(--accent); font-size:11px; font-weight:bold;">Active</span>'}
            </div>
        `).join('');
    } catch (e) { console.error("Load Personas Failed", e); }
}

async function addPersona() {
    const n = document.getElementById('p_name').value;
    const p = document.getElementById('p_prompt').value;
    if (!n || !p) return;
    await fetch(API + '/api/personas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: n, system_prompt: p })
    });
    document.getElementById('p_name').value = '';
    document.getElementById('p_prompt').value = '';
    loadPersonas();
}

async function activatePersona(id) {
    if (confirm("이 페르소나를 활성화하시겠습니까? (기존 페르소나는 비활성화됨)")) {
        await fetch(API + `/api/personas/${id}/activate`, { method: 'POST' });
        loadPersonas();
    }
}

// Answer Guidelines (Feedback)
async function loadFeedback() {
    try {
        const res = await fetch(API + '/api/feedback');
        const data = await res.json();
        document.getElementById('feedbackList').innerHTML = data.map(f => `
            <div class="list-item">
                <div class="item-content">
                    <span class="item-title">Context: ${f.context}</span>
                    <span class="item-desc">Guide: ${f.guideline}</span>
                </div>
                <button onclick="deleteFeedback(${f.id})" class="btn btn-sm btn-danger">삭제</button>
            </div>
        `).join('');
    } catch (e) { console.error("Load Feedback Failed", e); }
}

async function addFeedback() {
    const c = document.getElementById('fb_context').value;
    const g = document.getElementById('fb_guideline').value;
    if (!c || !g) return;
    await fetch(API + '/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: c, guideline: g })
    });
    document.getElementById('fb_context').value = '';
    document.getElementById('fb_guideline').value = '';
    loadFeedback();
}

async function deleteFeedback(id) {
    if (confirm("이 지침을 삭제하시겠습니까?")) {
        await fetch(API + `/api/feedback/${id}`, { method: 'DELETE' });
        loadFeedback();
    }
}
