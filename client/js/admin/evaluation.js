// Section 3: Evaluation & QA

async function generateAIQA() {
    const file = document.getElementById('qa_source_file').value;
    if (!file) return alert("분석할 PDF 파일을 선택해주세요.");

    if (!confirm(`'${file}' 파일을 분석하여 QA 데이터셋을 자동 생성하시겠습니까? (시간이 소요됩니다)`)) return;

    try {
        const res = await fetch(API + '/api/generate_qa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: file })
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
    document.getElementById('btnEval').disabled = true;
    document.getElementById('btnEval').innerText = "⏳ 평가 진행 중...";
    try {
        const res = await fetch(API + '/api/evaluate', { method: 'POST' });
        const data = await res.json();
        const r = data.result;
        document.getElementById('evalResult').style.display = 'block';
        document.getElementById('score_faith').innerText = r.faithfulness;
        document.getElementById('score_rel').innerText = r.answer_relevancy;
        document.getElementById('score_prec').innerText = r.context_precision;
        document.getElementById('evalDetails').innerHTML = r.details.map(d => `
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
