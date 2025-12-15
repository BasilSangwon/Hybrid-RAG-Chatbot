// Section 3: Evaluation & QA

async function generateAIQA() {
    const file = document.getElementById('qa_source_file').value;
    const modelSelect = document.getElementById('shared_model_select');
    const countInput = document.getElementById('qa_count');
    const selectedModel = modelSelect ? modelSelect.value : "gemini-2.0-flash";
    const count = countInput ? parseInt(countInput.value) || 10 : 10;

    if (!file) return alert("분석할 PDF 파일을 선택해주세요.");

    if (!confirm(`'${file}' 파일에서 ${count}개의 Q&A를 생성하시겠습니까?\n(모델: ${selectedModel})`)) return;

    try {
        const res = await fetch(API + '/api/generate_qa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: file,
                model: selectedModel,
                count: count
            })
        });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("요청 실패: " + e);
    }
}

// 파일 정보 및 토큰 예상치 업데이트 (파일/개수 변경 시)
async function updateFileInfo() {
    const fileSelect = document.getElementById('qa_source_file');
    const countInput = document.getElementById('qa_count');
    const tokenInfoDiv = document.getElementById('qa_token_info');

    if (!fileSelect || !countInput || !tokenInfoDiv) return;

    const filename = fileSelect.value;
    const count = parseInt(countInput.value) || 10;

    if (!filename) {
        tokenInfoDiv.innerHTML = '💡 파일을 선택하면 예상 토큰이 표시됩니다.';
        return;
    }

    tokenInfoDiv.innerHTML = '⏳ 파일 분석 중...';

    try {
        const res = await fetch(API + `/api/file_info/${encodeURIComponent(filename)}?count=${count}`);
        const data = await res.json();

        if (data.status === 'ok') {
            tokenInfoDiv.innerHTML = `
                <div style="margin-bottom:4px;">
                    📄 <b>PDF</b>: ${data.pdf_total_chars.toLocaleString()}자 
                    → <b>${data.num_chunks}개</b> 청크 (${data.chunk_size.toLocaleString()}자/청크)
                </div>
                <div style="margin-bottom:4px;">
                    📝 <b>처리</b>: ${data.chunks_needed}개 청크 × ${data.qa_per_chunk}개 Q&A
                </div>
                <div style="border-top:1px solid #bae6fd; padding-top:5px; margin-top:5px;">
                    💡 <b>예상 토큰</b>: Q&A ${count}개 ≈ <b>~${data.estimated_total_tokens.toLocaleString()} 토큰</b>
                    <br><span style="color:#64748b; font-size:10px;">
                        입력: ~${data.estimated_input_tokens.toLocaleString()} + 출력: ~${data.estimated_output_tokens.toLocaleString()}
                    </span>
                </div>
            `;
        } else {
            tokenInfoDiv.innerHTML = `❌ ${data.message}`;
        }
    } catch (e) {
        tokenInfoDiv.innerHTML = `❌ 파일 정보 로드 실패: ${e}`;
    }
}

// Q&A 생성 취소
async function cancelQAGen() {
    if (!confirm("Q&A 생성을 취소하시겠습니까?")) return;
    try {
        const res = await fetch(API + '/api/generate_qa/cancel', { method: 'POST' });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("취소 실패: " + e);
    }
}

let allAnswersData = [];

async function loadAnswers() {
    try {
        const res = await fetch(API + '/api/answers');
        allAnswersData = await res.json();
        renderAnswers(allAnswersData);
    } catch (e) { console.error("Load Answers Error", e); }
}

function renderAnswers(data) {
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
}

function filterAnswers() {
    const query = document.getElementById('qa_search').value.toLowerCase();
    if (!query) {
        renderAnswers(allAnswersData);
        return;
    }
    const filtered = allAnswersData.filter(a =>
        a.question.toLowerCase().includes(query) ||
        a.answer.toLowerCase().includes(query)
    );
    renderAnswers(filtered);
}

async function addAnswer() {
    const q = document.getElementById('q_input').value;
    const a = document.getElementById('a_input').value;
    if (!q || !a) return alert("질문과 답변을 입력하세요.");
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
    if (confirm("삭제하시겠습니까?")) {
        await fetch(API + `/api/answers/${id}`, { method: 'DELETE' });
        loadAnswers();
    }
}

async function deleteAllAnswers() {
    if (confirm("⚠️ 모든 지식 데이터를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다!")) {
        const res = await fetch(API + '/api/answers_all', { method: 'DELETE' });
        const data = await res.json();
        alert(data.message || "삭제 완료");
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
