// === Screening Page Logic ===
// Auto-executes screening_call.py for each selected candidate sequentially.

const screeningTbody = document.getElementById('screening-tbody');
const candidateCount = document.getElementById('candidate-count');
const statusText = document.getElementById('status-text');
const statusIndicator = document.getElementById('status-indicator');
const stopAllBtn = document.getElementById('stop-all-btn');
const screeningLog = document.getElementById('screening-log');

let candidates = [];
let currentIndex = -1;
let stopped = false;
let currentAbortController = null;

// === Initialize ===
(function init() {
    const raw = sessionStorage.getItem('screeningCandidates');
    if (!raw) {
        statusText.textContent = 'No candidates selected.';
        statusIndicator.className = 'status-dot dot-none';
        logScreen('No candidates found in session. Go back and select candidates.', 'error');
        stopAllBtn.disabled = true;
        return;
    }

    try {
        candidates = JSON.parse(raw);
    } catch (e) {
        statusText.textContent = 'Error loading candidates.';
        logScreen('Failed to parse candidate data from session.', 'error');
        return;
    }

    if (candidates.length === 0) {
        statusText.textContent = 'No candidates selected.';
        return;
    }

    candidateCount.textContent = candidates.length;
    renderTable();
    logScreen(`Loaded ${candidates.length} candidate(s) for screening.`, 'info');

    // Start auto-screening
    startScreeningFlow();
})();

// === Render Table ===
function renderTable() {
    screeningTbody.innerHTML = '';
    candidates.forEach((c, idx) => {
        const tr = document.createElement('tr');
        tr.id = `screen-row-${idx}`;
        tr.innerHTML = `
            <td class="col-rank">${idx + 1}</td>
            <td class="col-name">${escapeHtml(c.name)}</td>
            <td class="col-score"><span class="${c.score >= 7 ? 'score-high' : c.score >= 5 ? 'score-mid' : 'score-low'}">${c.score.toFixed(1)}</span></td>
            <td class="col-status" id="status-${idx}">
                <span class="status-badge status-pending">Pending</span>
            </td>
            <td class="col-result" id="result-${idx}">—</td>
            <td class="col-actions">
                <button class="btn-sm btn-stop-row" id="stop-btn-${idx}" onclick="stopSingle(${idx})" disabled>Stop</button>
                <button class="btn-sm btn-schedule" onclick="scheduleInterview(${idx})">Schedule Interview</button>
            </td>
        `;
        screeningTbody.appendChild(tr);
    });
}

// === Auto Screening Flow ===
async function startScreeningFlow() {
    statusText.textContent = 'Screening in progress...';
    statusIndicator.className = 'status-dot dot-active';

    for (let i = 0; i < candidates.length; i++) {
        if (stopped) break;

        currentIndex = i;
        await screenCandidate(i);

        if (stopped) break;

        // Wait 4 seconds before next candidate
        if (i < candidates.length - 1) {
            logScreen(`Waiting 4 seconds before next candidate...`, 'info');
            await delay(4000);
        }
    }

    if (stopped) {
        // Mark remaining as cancelled
        for (let j = currentIndex + 1; j < candidates.length; j++) {
            setStatus(j, 'cancelled', 'Cancelled');
            setResult(j, 'Skipped — screening stopped by user');
        }
        statusText.textContent = 'Screening stopped.';
        statusIndicator.className = 'status-dot dot-stopped';
        logScreen('Screening stopped by user.', 'error');
    } else {
        statusText.textContent = 'Screening complete.';
        statusIndicator.className = 'status-dot dot-complete';
        logScreen('All candidates have been screened.', 'success');
    }

    stopAllBtn.disabled = true;
}

async function screenCandidate(idx) {
    const candidate = candidates[idx];
    setStatus(idx, 'in-progress', 'In Progress');
    document.getElementById(`stop-btn-${idx}`).disabled = false;
    logScreen(`Starting screening call for ${candidate.name}...`, 'info');

    try {
        currentAbortController = new AbortController();

        // Step 1: Start the screening call
        const startResp = await fetch('/api/screen-start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ candidate_name: candidate.name }),
            signal: currentAbortController.signal,
        });

        if (!startResp.ok) {
            const err = await startResp.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(err.detail || `HTTP ${startResp.status}`);
        }

        const startData = await startResp.json();
        logScreen(`Screening server started for ${candidate.name} on port ${startData.port}`, 'success');
        logScreen(`Interview URL: ${startData.local_url}`, 'info');

        setStatus(idx, 'in-progress', 'Call Active');
        setResult(idx, `<a href="${escapeHtml(startData.local_url)}" target="_blank" class="interview-link">Open Interview</a>`);

        // Step 2: Poll for results (check every 15 seconds, up to 10 minutes)
        let resultData = null;
        const maxAttempts = 40;
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            if (stopped) return;

            await delay(15000);

            try {
                const resResp = await fetch(`/api/screen-results?candidate_name=${encodeURIComponent(candidate.name)}`, {
                    signal: currentAbortController.signal,
                });

                if (resResp.ok) {
                    resultData = await resResp.json();
                    if (resultData.transcript && resultData.transcript.length > 0) {
                        break;
                    }
                }
            } catch (pollErr) {
                if (pollErr.name === 'AbortError') return;
                // Continue polling
            }
        }

        if (stopped) return;

        if (resultData && resultData.transcript && resultData.transcript.length > 0) {
            const proceed = resultData.proceed_to_next_round || 'N/A';
            const summary = resultData.transcript_summary || 'No summary available';
            setStatus(idx, 'completed', 'Completed');
            setResult(idx, `
                <div class="screen-result">
                    <strong>Proceed:</strong> <span class="${proceed === 'YES' ? 'score-high' : 'score-low'}">${escapeHtml(proceed)}</span><br>
                    <span class="result-summary">${escapeHtml(summary)}</span>
                </div>
            `);
            logScreen(`Screening completed for ${candidate.name} — Proceed: ${proceed}`, 'success');
        } else {
            setStatus(idx, 'completed', 'No Response');
            setResult(idx, 'Interview not completed or no transcript available');
            logScreen(`No transcript received for ${candidate.name}`, 'error');
        }

    } catch (err) {
        if (err.name === 'AbortError') {
            setStatus(idx, 'cancelled', 'Cancelled');
            setResult(idx, 'Cancelled by user');
            return;
        }
        setStatus(idx, 'error', 'Error');
        setResult(idx, `Error: ${escapeHtml(err.message)}`);
        logScreen(`Error screening ${candidate.name}: ${err.message}`, 'error');
    } finally {
        document.getElementById(`stop-btn-${idx}`).disabled = true;
        currentAbortController = null;
    }
}

// === Stop Screening ===
stopAllBtn.addEventListener('click', async () => {
    stopped = true;
    if (currentAbortController) {
        currentAbortController.abort();
    }
    // Stop any running server
    try {
        await fetch('/api/screen-stop', { method: 'POST' });
    } catch (e) {
        // ignore
    }
    logScreen('Stop requested — cancelling remaining candidates.', 'error');
});

function stopSingle(idx) {
    if (idx === currentIndex) {
        // Stop current candidate's screening
        if (currentAbortController) {
            currentAbortController.abort();
        }
        fetch('/api/screen-stop', { method: 'POST' }).catch(() => {});
        setStatus(idx, 'cancelled', 'Cancelled');
        setResult(idx, 'Cancelled by user');
        logScreen(`Cancelled screening for ${candidates[idx].name}`, 'error');
    }
}

// === Schedule Interview (placeholder) ===
function scheduleInterview(idx) {
    alert('Coming Soon — Interview scheduling will be available in a future update.');
}

// === Helpers ===
function setStatus(idx, statusClass, label) {
    const el = document.getElementById(`status-${idx}`);
    if (el) {
        el.innerHTML = `<span class="status-badge status-${statusClass}">${escapeHtml(label)}</span>`;
    }
}

function setResult(idx, html) {
    const el = document.getElementById(`result-${idx}`);
    if (el) {
        el.innerHTML = html;
    }
}

function logScreen(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    screeningLog.appendChild(entry);
    screeningLog.scrollTop = screeningLog.scrollHeight;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
