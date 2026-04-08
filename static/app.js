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
const resultsContainer = document.getElementById('results-container');

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
    updateEvaluateButton();
    progressSection.classList.add('hidden');
    jdSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    progressLog.innerHTML = '';
    jdDetails.innerHTML = '';
    resultsContainer.innerHTML = '';
});

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
    progressLog.innerHTML = '';
    resultsContainer.innerHTML = '';

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
        // Send GET request (proxy blocks all POST requests)
        const params = new URLSearchParams({
            resume_folder: folder,
            job_description: jd,
        });
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
            addResultCard(event.result, resultsContainer.children.length);
            resultsSection.classList.remove('hidden');
            updateResultsRanking();
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
            // Re-render with final ranked order
            if (event.results && event.results.length > 0) {
                renderRankedResults(event.results);
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

// === Results Rendering ===
function addResultCard(result, index) {
    const card = createResultCard(result, index + 1);
    resultsContainer.appendChild(card);
}

function renderRankedResults(results) {
    resultsContainer.innerHTML = '';
    results.forEach((result, idx) => {
        const card = createResultCard(result, idx + 1);
        resultsContainer.appendChild(card);
    });
}

function updateResultsRanking() {
    // Re-sort existing cards by score
    const cards = Array.from(resultsContainer.children);
    cards.sort((a, b) => {
        const scoreA = parseFloat(a.dataset.score) || 0;
        const scoreB = parseFloat(b.dataset.score) || 0;
        return scoreB - scoreA;
    });
    cards.forEach((card, idx) => {
        const rankBadge = card.querySelector('.rank-badge');
        const rank = idx + 1;
        rankBadge.textContent = `#${rank}`;
        rankBadge.className = `rank-badge ${rank <= 3 ? 'rank-' + rank : 'rank-default'}`;
        resultsContainer.appendChild(card);
    });
}

function createResultCard(result, rank) {
    const eval_ = result.candidate_evaluation || {};
    const meta = result.reliability_metadata || {};
    const audit = result.audit_trail || {};
    const score = eval_.overall_score || 0;
    const filename = result.resume_filename || 'Unknown';

    const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
    const rankClass = rank <= 3 ? `rank-${rank}` : 'rank-default';

    const card = document.createElement('div');
    card.className = 'result-card';
    card.dataset.score = score;

    card.innerHTML = `
        <div class="result-header" onclick="this.parentElement.classList.toggle('expanded')">
            <div class="rank-badge ${rankClass}">#${rank}</div>
            <div class="result-info">
                <div class="result-filename">${escapeHtml(filename)}</div>
                <div class="result-meta">
                    <span>Confidence: ${meta.confidence || 'N/A'}</span>
                    <span>Status: ${meta.status || 'N/A'}</span>
                    <span>Attempts: ${meta.total_attempts || 1}</span>
                </div>
            </div>
            <div class="result-score ${scoreClass}">${score.toFixed(1)}</div>
            <div class="result-toggle">&#9662;</div>
        </div>
        <div class="result-details">
            ${renderDealBreaker(eval_.deal_breaker_check)}
            ${renderCategoryScores(eval_.category_scores)}
            ${renderMatched(eval_.matched_requirements)}
            ${renderGaps(eval_.gaps_and_missing)}
            ${renderSummary(eval_.summary)}
            ${renderReliability(meta)}
            ${renderAuditTrail(audit)}
        </div>
    `;

    return card;
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

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}


/* ========================================================================
   ORIGINAL FILE-UPLOAD UI CODE (commented out — proxy blocks multipart)
   ========================================================================

const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');
const fileList = document.getElementById('file-list');
let selectedFiles = [];

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files).filter(f =>
        f.name.endsWith('.pdf') || f.name.endsWith('.docx')
    );
    addFiles(files);
});

fileInput.addEventListener('change', () => {
    addFiles(Array.from(fileInput.files));
    fileInput.value = '';
});

function addFiles(files) {
    for (const file of files) {
        if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
            selectedFiles.push(file);
        }
    }
    renderFileList();
    updateEvaluateButton();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
    updateEvaluateButton();
}

function renderFileList() {
    fileList.innerHTML = selectedFiles.map((file, idx) => `
        <div class="file-item">
            <span class="file-name">${escapeHtml(file.name)}</span>
            <span class="file-size">${formatSize(file.size)}</span>
            <button class="remove-btn" onclick="removeFile(${idx})" title="Remove">&times;</button>
        </div>
    `).join('');
}

// Original FormData-based evaluate (used /api/evaluate with multipart upload):
//
// const formData = new FormData();
// formData.append('job_description', jd);
// for (const file of selectedFiles) {
//     formData.append('resumes', file);
// }
// const response = await fetch('/api/evaluate', { method: 'POST', body: formData });

======================================================================== */
