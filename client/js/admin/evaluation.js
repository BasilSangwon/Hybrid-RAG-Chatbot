// Section 3: Evaluation & QA

async function generateAIQA() {
    const file = document.getElementById('qa_source_file').value;
    const modelSelect = document.getElementById('shared_model_select');
    const selectedModel = modelSelect ? modelSelect.value : "gemini-2.0-flash";

    if (!file) return alert("분석할 PDF 파일을 선택해주세요.");

    if (!confirm(`'${file}' 파일을 분석하여 QA 데이터셋을 자동 생성하시겠습니까?\n(선택된 모델: ${selectedModel})`)) return;

    try {
        const res = await fetch(API + '/api/generate_qa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: file,
                model: selectedModel
            })
        });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("요청 실패: " + e);
    }
}

async function loadAnswers() {
    try {
        const res = await fetch(API + '/api/answers');
        const data = await res.json();
        const tbody = document.querySelector('#qaTable tbody');
        if (!tbody) return;
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#94a3b8;">데이터가 없습니다.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(a => `
            <tr>
                <td style="text-align:center; color:#64748b;">${a.id}</td>
                <td style="font-weight:600;">${a.question}</td>
                <td style="color:#475569;">${a.answer}</td>
                <td style="text-align:center;">
                    <button onclick="deleteAnswer(${a.id})" class="btn btn-sm btn-danger">삭제</button>
                </td>
            </tr>
        `).join('');
    } catch (e) { }
}

async function addAnswer() {
    const q = document.getElementById('q_input').value;
    const a = document.getElementById('a_input').value;
    if (!q || !a) return;
    await fetch(API + '/api/answers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, answer: a })
    });
    document.getElementById('q_input').value = '';
    document.getElementById('a_input').value = '';
    loadAnswers();
}

async function deleteAnswer(id) {
    if (confirm("이 질문/답변을 삭제하시겠습니까?")) {
        await fetch(API + `/api/answers/${id}`, { method: 'DELETE' });
        loadAnswers();
    }
}

async function runEvaluation() {
    const btn = document.getElementById("btnEval");
    const resultDiv = document.getElementById("evalResult");
    const detailsDiv = document.getElementById("evalDetails");
    const modelSelect = document.getElementById("shared_model_select"); // [NEW] Shared Selector
    const selectedModel = modelSelect ? modelSelect.value : "gemini-2.0-flash";

    btn.disabled = true;
    btn.innerText = "⏳ 평가 진행 중...";
    try {
        const res = await fetch(API + '/api/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: selectedModel })
        });
        const data = await res.json();
        const r = data.result;
        resultDiv.style.display = 'block';
        document.getElementById('score_faith').innerText = r.faithfulness;
        document.getElementById('score_rel').innerText = r.answer_relevancy;
        document.getElementById('score_prec').innerText = r.context_precision;
        detailsDiv.innerHTML = r.details.map(d => `
            <div style="margin-bottom:8px; font-size:12px;">
                <strong>Q: ${d.question}</strong><br>
                A: ${d.answer}<br>
                <span style="color:#db2777;">Faith: ${d.faithfulness}, Rel: ${d.relevancy}</span>
            </div>
        `).join('');
    } catch (e) { alert("평가 실패"); }
    document.getElementById('btnEval').disabled = false;
    document.getElementById('btnEval').innerText = "📝 평가 시작 (Start Evaluation)";
}

// [NEW] Shared Model Loading Logic (Moved from knowledge.js)
async function loadAvailableModels() {
    const selectors = [
        document.getElementById("shared_model_select"),
        document.getElementById("graph_llm_select")
    ];

    console.log("🔄 Loading models...");

    // Fallback Options (Explicitly NO 1.5, Ensure 2.0+ exists)
    const fallbackOptions = `
        <optgroup label="Recommended">
            <option value="gemini-2.0-flash" selected>gemini-2.0-flash</option>
            <option value="gemini-2.0-flash-exp">gemini-2.0-flash-exp</option>
            <option value="gemini-2.5-computer-use-preview-10-2025">gemini-2.5-preview</option>
        </optgroup>
    `;

    try {
        const res = await fetch("/api/models");

        let models = [];
        if (res.ok) {
            models = await res.json();
            console.log("✅ Models loaded:", models);
        } else {
            console.warn("⚠️ API Failure, using fallback options.");
        }

        // Filter and Build HTML
        const groups = { "Gemini 2.0+ Series": [], "Others": [] };
        let hasModels = false;

        if (models && models.length > 0) {
            models.forEach(m => {
                const name = m.id;
                // Exclude 1.5/1.0
                if (name.includes("gemini-1.5") || name.includes("gemini-1.0")) return;

                if (name.includes("gemini-2.0") || name.includes("gemini-2.5")) {
                    groups["Gemini 2.0+ Series"].push(m);
                    hasModels = true;
                } else {
                    groups["Others"].push(m);
                    hasModels = true;
                }
            });
        }

        let html = "";
        for (const [label, list] of Object.entries(groups)) {
            if (list.length > 0) {
                html += `<optgroup label="${label}">` + list.map(m => `<option value="${m.id}">${m.display_name}</option>`).join('') + `</optgroup>`;
            }
        }

        // Use fallback if empty or API failed
        if (!hasModels || !html) {
            console.warn("⚠️ No relevant models found or API failed, using fallback.");
            html = fallbackOptions;
        }

        selectors.forEach(sel => {
            if (sel) {
                sel.innerHTML = html;
                // Set default
                if (sel.querySelector("option[value='gemini-2.0-flash']")) {
                    sel.value = "gemini-2.0-flash";
                }
            }
        });

    } catch (e) {
        console.error("❌ Failed to load models:", e);
        selectors.forEach(sel => {
            if (sel) sel.innerHTML = fallbackOptions;
        });
    }
}

// Ensure it runs
document.addEventListener("DOMContentLoaded", () => {
    loadAvailableModels();
});
