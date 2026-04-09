// === DOM Elements ===
const jdInput = document.getElementById('jd-input');
const folderInput = document.getElementById('folder-input');
const evaluateBtn = document.getElementById('evaluate-btn');
const clearBtn = document.getElementById('clear-btn');
const progressSection = document.getElementById('progress-section');
const progressLog = document.getElementById('progress-log');
const jdSection = document.getElementById('jd-section');
const jdDetails = document.getElementById('jd-details');
const resultsSection = document.getElementById('results-section');
const resultsCount = document.getElementById('results-count');
const resultsTbody = document.getElementById('results-tbody');
const detailPanel = document.getElementById('detail-panel');
const selectAllCheckbox = document.getElementById('select-all');
const screenBtn = document.getElementById('screen-btn');
const selectedCountSpan = document.getElementById('selected-count');
const inputSection = document.getElementById('input-section');
const reqTbody = document.getElementById('req-tbody');
const selectedReqInfo = document.getElementById('selected-req-info');

// State
let allResults = [];
let allRequisitions = [];
let selectedRequisition = null;

// === Requisition Loading ===
async function loadRequisitions() {
    reqTbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:2rem;">Loading...</td></tr>';
    try {
        const resp = await fetch('/api/requisitions');
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Failed to load' }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        allRequisitions = data.requisitions || [];
        renderRequisitions(allRequisitions);
    } catch (e) {
        reqTbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--danger);padding:2rem;">Error: ${escapeHtml(e.message)}</td></tr>`;
    }
}

function renderRequisitions(reqs) {
    if (reqs.length === 0) {
        reqTbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:2rem;">No requisitions found.</td></tr>';
        return;
    }

    reqTbody.innerHTML = reqs.map((r, idx) => {
        const reqId = r['Requisition ID'] || '';
        const designation = r['Designation'] || '';
        const skill = r['Skill'] || '';
        const location = r['Location'] || '';
        const grade = r['Grade'] || '';
        const status = r['Status'] || '';

        return `<tr class="req-row" data-index="${idx}" onclick="selectRequisition(${idx})">
            <td class="col-check"><input type="radio" name="req-select" class="req-radio" data-index="${idx}"></td>
            <td>${escapeHtml(reqId)}</td>
            <td>${escapeHtml(designation)}</td>
            <td>${escapeHtml(skill)}</td>
            <td>${escapeHtml(location)}</td>
            <td>${escapeHtml(grade)}</td>
            <td>${escapeHtml(status)}</td>
        </tr>`;
    }).join('');
}

function selectRequisition(idx) {
    selectedRequisition = allRequisitions[idx];

    if (!selectedRequisition) return;

    // Update radio
    const radios = reqTbody.querySelectorAll('.req-radio');
    radios.forEach((r, i) => { r.checked = (i === idx); });

    // Highlight row
    const rows = reqTbody.querySelectorAll('.req-row');
    rows.forEach(r => r.classList.remove('row-selected'));
    rows[idx].classList.add('row-selected');

    // Compose job description from Skill + Designation + JD
    const skill = selectedRequisition['Skill'] || '';
    const designation = selectedRequisition['Designation'] || '';
    const jd = selectedRequisition['JD'] || '';
    const location = selectedRequisition['Location'] || '';
    const grade = selectedRequisition['Grade'] || '';
    const reqId = selectedRequisition['Requisition ID'] || '';

    let composedJD = '';
    if (designation) composedJD += `Role: ${designation}\n`;
    if (skill) composedJD += `Required Skills: ${skill}\n`;
    if (location) composedJD += `Location: ${location}\n`;
    if (grade) composedJD += `Grade: ${grade}\n`;
    if (jd) composedJD += `\nJob Description:\n${jd}`;

    jdInput.value = composedJD.trim();

    // Update info panel
    selectedReqInfo.innerHTML = `<strong>${escapeHtml(reqId)}</strong> — ${escapeHtml(designation)} | ${escapeHtml(skill)}`;

    // Show input section
    inputSection.classList.remove('hidden');
    updateEvaluateButton();
}

// === Enable/disable evaluate button ===
function updateEvaluateButton() {
    evaluateBtn.disabled = !(jdInput.value.trim() && folderInput.value.trim());
}

jdInput.addEventListener('input', updateEvaluateButton);
folderInput.addEventListener('input', updateEvaluateButton);

// === Clear ===
clearBtn.addEventListener('click', () => {
    jdInput.value = '';
    folderInput.value = '';
    allResults = [];
    selectedRequisition = null;
    updateEvaluateButton();
    progressSection.classList.add('hidden');
    jdSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    detailPanel.classList.add('hidden');
    progressLog.innerHTML = '';
    jdDetails.innerHTML = '';
    resultsTbody.innerHTML = '';
    detailPanel.innerHTML = '';
    selectedReqInfo.innerHTML = 'None selected';
    // Deselect requisition
    const radios = reqTbody.querySelectorAll('.req-radio');
    radios.forEach(r => { r.checked = false; });
    const rows = reqTbody.querySelectorAll('.req-row');
    rows.forEach(r => r.classList.remove('row-selected'));
    updateSelectionCount();
});

// === Select All checkbox ===
selectAllCheckbox.addEventListener('change', () => {
    const checkboxes = resultsTbody.querySelectorAll('.row-check');
    checkboxes.forEach(cb => { cb.checked = selectAllCheckbox.checked; });
    updateSelectionCount();
});

// === Screen Selected Candidates ===
screenBtn.addEventListener('click', () => {
    const selected = getSelectedCandidates();
    if (selected.length === 0) return;
    sessionStorage.setItem('screeningCandidates', JSON.stringify(selected));
    window.location.href = '/screening';
});

function getSelectedCandidates() {
    const checkboxes = resultsTbody.querySelectorAll('.row-check:checked');
    const candidates = [];
    checkboxes.forEach(cb => {
        const idx = parseInt(cb.dataset.index, 10);
        if (allResults[idx]) {
            const r = allResults[idx];
            const contact = r.candidate_contact || {};
            candidates.push({
                name: contact.name || r.resume_filename || 'Unknown',
                email: contact.email || '',
                phone: contact.phone || '',
                score: (r.candidate_evaluation || {}).overall_score || 0,
                filename: r.resume_filename || '',
            });
        }
    });
    return candidates;
}

function updateSelectionCount() {
    const checked = resultsTbody.querySelectorAll('.row-check:checked').length;
    selectedCountSpan.textContent = `${checked} selected`;
    screenBtn.disabled = checked === 0;
}

// === Evaluate ===
evaluateBtn.addEventListener('click', startEvaluation);

async function startEvaluation() {
    const jd = jdInput.value.trim();
    const folder = folderInput.value.trim();
    if (!jd || !folder) return;

    // UI state: processing
    evaluateBtn.disabled = true;
    evaluateBtn.querySelector('.btn-text').classList.add('hidden');
    evaluateBtn.querySelector('.btn-loading').classList.remove('hidden');
    progressSection.classList.remove('hidden');
    jdSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    detailPanel.classList.add('hidden');
    progressLog.innerHTML = '';
    resultsTbody.innerHTML = '';
    detailPanel.innerHTML = '';
    allResults = [];

    logProgress('Starting evaluation pipeline...', 'info');

    // Pre-flight: check server is reachable
    try {
        const healthResp = await fetch('/api/health');
        if (!healthResp.ok) {
            throw new Error(`Server health check failed: HTTP ${healthResp.status}`);
        }
        const healthData = await healthResp.json();
        logProgress(`Server OK — provider: ${healthData.provider}, model: ${healthData.model}`, 'info');
        if (!healthData.api_key_set) {
            throw new Error(`${healthData.provider.toUpperCase()} API key not configured. Update your .env file.`);
        }
    } catch (healthErr) {
        if (healthErr.message.includes('API key')) throw healthErr;
        logProgress(`Warning: Health check failed (${healthErr.message}). Trying evaluate anyway...`, 'error');
    }

    try {
        logProgress('Using local folder evaluation path...', 'info');
        const params = new URLSearchParams({
            resume_folder: folder,
            job_description: jd,
        });

        // Pass requisition context if selected
        if (selectedRequisition) {
            const reqId = selectedRequisition['Requisition ID'] || '';
            if (reqId) params.set('requisition_id', reqId);
            params.set('requisition_json', JSON.stringify(selectedRequisition));
            logProgress(`Requisition: ${reqId} — ${selectedRequisition['Designation'] || ''}`, 'info');
        }

        const response = await fetch(`/api/evaluate-local?${params.toString()}`);

        if (!response.ok) {
            const rawText = await response.text().catch(() => '');
            let detail;
            try {
                const errJson = JSON.parse(rawText);
                detail = errJson.detail || response.statusText;
            } catch {
                detail = `HTTP ${response.status} ${response.statusText}`;
                if (rawText) detail += ` — ${rawText.substring(0, 500)}`;
            }
            throw new Error(detail);
        }

        // Read NDJSON stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const event = JSON.parse(line);
                    handleStreamEvent(event);
                } catch (e) {
                    console.warn('Failed to parse NDJSON line:', line);
                }
            }
        }

        // Process remaining buffer
        if (buffer.trim()) {
            try {
                handleStreamEvent(JSON.parse(buffer));
            } catch (e) {
                console.warn('Failed to parse final buffer');
            }
        }

    } catch (error) {
        logProgress(`Error: ${error.message}`, 'error');
    } finally {
        evaluateBtn.disabled = false;
        evaluateBtn.querySelector('.btn-text').classList.remove('hidden');
        evaluateBtn.querySelector('.btn-loading').classList.add('hidden');
        updateEvaluateButton();
    }
}

// === Stream Event Handler ===
function handleStreamEvent(event) {
    switch (event.type) {
        case 'status':
            logProgress(event.message, 'info');
            break;

        case 'jd_extracted':
            logProgress(event.message, 'success');
            renderJDRequirements(event.data);
            jdSection.classList.remove('hidden');
            break;

        case 'resume_started':
            logProgress(event.message, 'info');
            break;

        case 'resume_completed':
            logProgress(`Completed: ${event.filename} (Score: ${event.result.candidate_evaluation.overall_score}/10)`, 'success');
            addResultRow(event.result);
            resultsSection.classList.remove('hidden');
            break;

        case 'resume_error':
            logProgress(`Error: ${event.message}`, 'error');
            break;

        case 'error':
            logProgress(`Error: ${event.message}`, 'error');
            break;

        case 'all_complete':
            logProgress(`Pipeline complete. ${event.total_processed} resume(s) evaluated.`, 'success');
            resultsCount.textContent = event.total_processed;
            if (event.results && event.results.length > 0) {
                renderRankedTable(event.results);
            }
            break;

        default:
            console.log('Unknown event:', event);
    }
}

// === Progress Log ===
function logProgress(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    progressLog.appendChild(entry);
    progressLog.scrollTop = progressLog.scrollHeight;
}

// === JD Requirements Renderer ===
function renderJDRequirements(jd) {
    let html = '';

    if (jd.job_title) {
        html += `<div class="jd-category">
            <h3>Position</h3>
            <p style="font-weight:600;font-size:0.95rem;">${escapeHtml(jd.job_title)}</p>
            ${jd.domain ? `<p style="font-size:0.83rem;color:var(--text-secondary)">${escapeHtml(jd.domain)}</p>` : ''}
        </div>`;
    }

    if (jd.hard_skills && jd.hard_skills.length > 0) {
        html += `<div class="jd-category">
            <h3>Hard Skills (${jd.hard_skills.length})</h3>
            <ul>${jd.hard_skills.map(s =>
                `<li>${escapeHtml(s.skill)} <span class="tag-${s.priority}">${s.priority}</span></li>`
            ).join('')}</ul>
        </div>`;
    }

    if (jd.soft_skills && jd.soft_skills.length > 0) {
        html += `<div class="jd-category">
            <h3>Soft Skills (${jd.soft_skills.length})</h3>
            <ul>${jd.soft_skills.map(s =>
                `<li>${escapeHtml(s.skill)} <span class="tag-${s.priority}">${s.priority}</span></li>`
            ).join('')}</ul>
        </div>`;
    }

    if (jd.experience) {
        const exp = jd.experience;
        html += `<div class="jd-category">
            <h3>Experience</h3>
            <ul>
                ${exp.min_years != null ? `<li>Min: ${exp.min_years} years</li>` : ''}
                ${exp.max_years != null ? `<li>Max: ${exp.max_years} years</li>` : ''}
                ${exp.specific_roles && exp.specific_roles.length ? `<li>Roles: ${exp.specific_roles.map(escapeHtml).join(', ')}</li>` : ''}
                ${exp.target_industries && exp.target_industries.length ? `<li>Industries: ${exp.target_industries.map(escapeHtml).join(', ')}</li>` : ''}
            </ul>
        </div>`;
    }

    if (jd.deal_breakers && jd.deal_breakers.length > 0) {
        html += `<div class="jd-category">
            <h3>Deal-Breakers</h3>
            <ul>${jd.deal_breakers.map(d =>
                `<li style="color:var(--danger);font-weight:500;">${escapeHtml(d)}</li>`
            ).join('')}</ul>
        </div>`;
    }

    if (jd.certifications && jd.certifications.length > 0) {
        html += `<div class="jd-category">
            <h3>Certifications</h3>
            <ul>${jd.certifications.map(c =>
                `<li>${escapeHtml(c.certification)} <span class="tag-${c.priority}">${c.priority}</span></li>`
            ).join('')}</ul>
        </div>`;
    }

    jdDetails.innerHTML = html;
}

// === Table-based Results Rendering ===

function addResultRow(result) {
    const idx = allResults.length;
    allResults.push(result);
    const row = buildRow(result, idx, idx + 1);
    resultsTbody.appendChild(row);
}

function renderRankedTable(results) {
    resultsTbody.innerHTML = '';
    detailPanel.classList.add('hidden');
    detailPanel.innerHTML = '';
    allResults = results;

    results.forEach((result, idx) => {
        const row = buildRow(result, idx, idx + 1);
        resultsTbody.appendChild(row);
    });
    selectAllCheckbox.checked = false;
    updateSelectionCount();
}

function buildRow(result, idx, rank) {
    const eval_ = result.candidate_evaluation || {};
    const meta = result.reliability_metadata || {};
    const contact = result.candidate_contact || {};
    const score = eval_.overall_score || 0;
    const filename = result.resume_filename || 'Unknown';

    const candidateName = contact.name || deriveName(filename);
    const email = contact.email || 'N/A';
    const phone = contact.phone || 'N/A';
    const experience = contact.total_experience || 'N/A';
    const location = contact.location || 'N/A';
    const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
    const dealBreaker = (eval_.deal_breaker_check || {}).status || 'N/A';
    const dealClass = dealBreaker === 'PASS' ? 'tag-pass' : dealBreaker === 'FAIL' ? 'tag-fail' : '';

    const tr = document.createElement('tr');
    tr.className = 'result-row';
    tr.dataset.index = idx;

    tr.innerHTML = `
        <td class="col-check"><input type="checkbox" class="row-check" data-index="${idx}"></td>
        <td class="col-rank"><span class="rank-badge rank-${rank <= 3 ? rank : 'default'}">#${rank}</span></td>
        <td class="col-name">${escapeHtml(candidateName)}</td>
        <td class="col-email">${escapeHtml(email)}</td>
        <td class="col-phone">${escapeHtml(phone)}</td>
        <td>${escapeHtml(experience)}</td>
        <td>${escapeHtml(location)}</td>
        <td class="col-score"><span class="${scoreClass}">${score.toFixed(1)}</span></td>
        <td class="col-confidence">${escapeHtml(meta.confidence || 'N/A')}</td>
        <td class="col-deal"><span class="${dealClass}">${escapeHtml(dealBreaker)}</span></td>
        <td class="col-expand"><button class="expand-btn" title="View details">&#9662;</button></td>
    `;

    tr.querySelector('.row-check').addEventListener('change', (e) => {
        e.stopPropagation();
        updateSelectionCount();
    });

    tr.querySelector('.expand-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDetail(idx);
    });

    tr.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        toggleDetail(idx);
    });

    return tr;
}

function toggleDetail(idx) {
    const result = allResults[idx];
    if (!result) return;

    if (detailPanel.dataset.activeIndex === String(idx) && !detailPanel.classList.contains('hidden')) {
        detailPanel.classList.add('hidden');
        detailPanel.dataset.activeIndex = '';
        return;
    }

    detailPanel.dataset.activeIndex = String(idx);
    detailPanel.innerHTML = renderDetailContent(result);
    detailPanel.classList.remove('hidden');
    detailPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderDetailContent(result) {
    const eval_ = result.candidate_evaluation || {};
    const meta = result.reliability_metadata || {};
    const audit = result.audit_trail || {};

    return `
        <div class="detail-inner">
            ${renderDealBreaker(eval_.deal_breaker_check)}
            ${renderCategoryScores(eval_.category_scores)}
            ${renderMatched(eval_.matched_requirements)}
            ${renderGaps(eval_.gaps_and_missing)}
            ${renderSummary(eval_.summary)}
            ${renderReliability(meta)}
            ${renderAuditTrail(audit)}
        </div>
    `;
}

function renderDealBreaker(check) {
    if (!check) return '';
    const cls = check.status === 'PASS' ? 'pass' : 'fail';
    return `<div class="deal-breaker ${cls}">
        Deal-Breaker Check: ${check.status} ${check.explanation ? '— ' + escapeHtml(check.explanation) : ''}
    </div>`;
}

function renderCategoryScores(scores) {
    if (!scores) return '';
    const categories = [
        { key: 'hard_skills_match', label: 'Hard Skills' },
        { key: 'soft_skills_match', label: 'Soft Skills' },
        { key: 'experience_relevance', label: 'Experience' },
        { key: 'education_certifications', label: 'Education & Certs' },
        { key: 'achievement_quality', label: 'Achievements' },
    ];

    return `<div class="category-scores">
        ${categories.map(cat => {
            const val = scores[cat.key] || 0;
            const pct = (val / 10) * 100;
            const color = val >= 7 ? 'var(--success)' : val >= 5 ? 'var(--warning)' : 'var(--danger)';
            return `<div class="cat-score">
                <div class="cat-name">${cat.label}</div>
                <div class="cat-bar"><div class="cat-fill" style="width:${pct}%;background:${color}"></div></div>
                <div class="cat-value">${val}/10</div>
            </div>`;
        }).join('')}
    </div>`;
}

function renderMatched(items) {
    if (!items || items.length === 0) return '';
    return `<div class="detail-section">
        <h4>Matched Requirements (${items.length})</h4>
        <ul class="detail-list">
            ${items.map(item => {
                const req = typeof item === 'string' ? item : (item.requirement || item);
                const evidence = typeof item === 'object' ? item.evidence : null;
                return `<li class="matched">
                    ${escapeHtml(req)}
                    ${evidence ? `<span class="evidence-quote">"${escapeHtml(evidence)}"</span>` : ''}
                </li>`;
            }).join('')}
        </ul>
    </div>`;
}

function renderGaps(items) {
    if (!items || items.length === 0) return '';
    return `<div class="detail-section">
        <h4>Gaps & Missing (${items.length})</h4>
        <ul class="detail-list">
            ${items.map(item => {
                const req = typeof item === 'string' ? item : (item.requirement || item);
                const priority = typeof item === 'object' ? item.priority : 'required';
                return `<li class="gap-${priority}">
                    ${escapeHtml(req)}
                    <span class="tag-${priority}">${priority}</span>
                </li>`;
            }).join('')}
        </ul>
    </div>`;
}

function renderSummary(summary) {
    if (!summary) return '';
    return `<div class="detail-section">
        <h4>Summary</h4>
        <p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.6">${escapeHtml(summary)}</p>
    </div>`;
}

function renderReliability(meta) {
    if (!meta) return '';
    const confidenceDot = `dot-${meta.confidence || 'none'}`;
    const adj = meta.score_adjustment || {};

    return `<div class="reliability-bar">
        <div class="reliability-item">
            <span class="reliability-dot ${confidenceDot}"></span>
            Confidence: ${meta.confidence || 'N/A'}
        </div>
        <div class="reliability-item">
            Verification: ${meta.verification_rate != null ? (meta.verification_rate * 100).toFixed(0) + '%' : 'N/A'}
        </div>
        <div class="reliability-item">
            Hallucinations caught: ${meta.hallucinations_caught || 0}
        </div>
        ${adj.delta && adj.delta !== 0 ? `<div class="reliability-item">
            Score adjusted: ${adj.delta > 0 ? '+' : ''}${adj.delta.toFixed(1)}
        </div>` : ''}
    </div>`;
}

function renderAuditTrail(audit) {
    if (!audit) return '';
    return `
        <button class="audit-toggle" onclick="this.nextElementSibling.classList.toggle('visible')">
            Show Audit Trail
        </button>
        <div class="audit-content">Path: ${(audit.path_taken || []).join(' → ')}

Tokens: ${JSON.stringify(audit.total_tokens || {}, null, 2)}
Cost: $${(audit.total_cost_estimate || 0).toFixed(4)}
Latency: ${audit.total_latency_ms || 0}ms
Model: ${audit.model_used || 'N/A'}
Trace ID: ${audit.trace_id || 'N/A'}</div>
    `;
}

// === Utilities ===
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function deriveName(filename) {
    if (!filename) return 'Unknown';
    let name = filename.replace(/\.[^/.]+$/, '');
    name = name.replace(/[_\-]+/g, ' ');
    name = name.replace(/\b(resume|cv)\b/gi, '').trim();
    if (!name) return filename;
    return name.replace(/\b\w/g, c => c.toUpperCase());
}

// === Init: load requisitions on page load ===
loadRequisitions();
