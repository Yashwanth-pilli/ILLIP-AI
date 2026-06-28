// All API calls use the host the page was served from — no hardcoded URLs
const API_BASE_URL = `${window.location.protocol}//${window.location.host}/api`;
const HEALTH_CHECK_INTERVAL = 10000;

let messagesContainer, messageInput, chatForm, statusDot, statusText;
let isLoading = false;
let _activeModel = '';
let _forceLarge  = false;
let _forceSearch = false;
let _activeProject = 'default';
let _suggestedModel = null;   // from hardware recommendation

// ── Mobile sidebar toggle ─────────────────────────────────────────────────────

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const btn     = document.getElementById('sidebarToggle');
    if (!sidebar) return;
    const open = sidebar.classList.toggle('open');
    if (btn) btn.textContent = open ? '✕' : '☰';
}

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
    messagesContainer = document.getElementById('messagesContainer');
    messageInput      = document.getElementById('messageInput');
    chatForm          = document.getElementById('chatForm');
    statusDot         = document.getElementById('statusDot');
    statusText        = document.getElementById('statusText');

    chatForm.addEventListener('submit', handleSubmit);

    checkHealth();
    updateSystemStatus();
    updateHardwareStatus();
    updateAgentsList();
    updateStats();
    loadProjects();
    updateSkillsPanel();
    updateModelsPanel();
    updatePluginsPanel();
    updateHardwareLive();
    initVoice();

    setInterval(checkHealth, HEALTH_CHECK_INTERVAL);
    setInterval(updateSystemStatus, HEALTH_CHECK_INTERVAL);
    setInterval(updateAgentsList, HEALTH_CHECK_INTERVAL * 3);
    setInterval(updateHardwareLive, 5000);
    setInterval(updateModelsPanel, 60000);   // refresh model list every minute
}

// ── Chat ──────────────────────────────────────────────────────────────────────

function toggleForceLarge() {
    _forceLarge = !_forceLarge;
    document.getElementById('forceLarge')?.classList.toggle('active', _forceLarge);
}

function toggleForceSearch() {
    _forceSearch = !_forceSearch;
    document.getElementById('searchToggle')?.classList.toggle('active', _forceSearch);
}

async function handleSubmit(event) {
    event.preventDefault();
    const message = messageInput.value.trim();
    if (isLoading) return;
    // Special commands
    if (message === '!refresh' || message === '/refresh') {
        messageInput.value = '';
        await refreshSystem();
        return;
    }

    // Image + optional text
    if (_pendingImage) {
        const prompt = message || 'Describe this image in detail.';
        displayMessage('user', `[Image] ${prompt}`);
        messageInput.value = '';
        clearImage();
        isLoading = true;
        toggleInput(true);
        const thinkingId = displayThinking();
        const desc = await sendImageToVision(_pendingImage.file, prompt);
        removeThinking(thinkingId);
        displayMessage('assistant', desc);
        isLoading = false;
        toggleInput(false);
        return;
    }

    if (!message) return;
    displayMessage('user', message);
    messageInput.value = '';
    await handleChat(message);
}

async function handleChat(message) {
    const thinkingId = displayThinking();
    isLoading = true;
    toggleInput(true);

    try {
        const payload = {
            message,
            include_memory: true,
            model:        _forceLarge  ? null : null,   // router decides; Boost is handled below
            force_search: _forceSearch,
            project_id:   _activeProject,
        };
        // Boost = skip router, use whatever is currently active (not hardcoded model name)
        if (_forceLarge && _activeModel) payload.model = _activeModel;

        const res = await fetch(`${API_BASE_URL}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        removeThinking(thinkingId);

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            displayMessage('assistant', `**Error:** ${err.detail || res.statusText}`);
            return;
        }

        const div = document.createElement('div');
        div.className = 'message assistant';
        const inner = document.createElement('div');
        inner.className = 'message-content';
        div.appendChild(inner);
        messagesContainer.appendChild(div);
        scrollToBottom();

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let raw = '';
        let buffer = '';
        let routingShown = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const payload = line.slice(6).trim();
                if (payload === '[DONE]') break;
                try {
                    const parsed = JSON.parse(payload);
                    if (parsed.routing && !routingShown) {
                        routingShown = true;
                        const r = parsed.routing;
                        const searchTag = r.needs_search ? ' · 🔍 searched' : '';
                        const badge = `<span class="routing-badge">🤖 ${r.model} · ${r.complexity} · ${r.pressure} pressure${searchTag}</span>`;
                        inner.innerHTML = badge;
                        _activeModel = r.model;
                        const mb = document.getElementById('modelBadge');
                        if (mb) mb.textContent = `🤖 ${r.model}`;
                        _forceLarge = false;
                        document.getElementById('forceLarge')?.classList.remove('active');
                        _forceSearch = false;
                        document.getElementById('searchToggle')?.classList.remove('active');
                        const banner = document.getElementById('pressureBanner');
                        if (banner) {
                            if (r.warning) {
                                banner.textContent = r.warning;
                                banner.className = `pressure-banner ${r.pressure}`;
                            } else {
                                banner.className = 'pressure-banner hidden';
                            }
                        }
                    } else if (parsed.token) {
                        raw += parsed.token;
                        const badge = inner.querySelector('.routing-badge');
                        inner.innerHTML = (badge ? badge.outerHTML : '') + marked.parse(raw);
                        scrollToBottom();
                    }
                } catch {}
            }
        }

        // Attach feedback buttons + speaker icon after response complete
        addFeedbackButtons(div, message, raw);
        addSpeakerButton(div, raw);
        if (_autoSpeak && raw) speakText(raw);

    } catch (e) {
        removeThinking(thinkingId);
        displayMessage('assistant', `**Connection error:** ${e.message}`);
    } finally {
        isLoading = false;
        toggleInput(false);
    }
}

// ── Feedback (learning loop) ──────────────────────────────────────────────────

function addFeedbackButtons(msgDiv, question, response) {
    if (!response.trim()) return;
    const bar = document.createElement('div');
    bar.className = 'feedback-bar';
    bar.innerHTML = `
        <span class="feedback-label">Was this helpful?</span>
        <button class="feedback-btn good" onclick="submitFeedback(this, '${escapeAttr(question)}', '${escapeAttr(response)}', true)">👍</button>
        <button class="feedback-btn bad"  onclick="submitFeedback(this, '${escapeAttr(question)}', '${escapeAttr(response)}', false)">👎</button>
    `;
    msgDiv.appendChild(bar);
}

async function submitFeedback(btn, question, response, isGood) {
    const bar = btn.closest('.feedback-bar');
    bar.innerHTML = '<span class="feedback-label" style="color:#22c55e">✓ Saved</span>';
    try {
        if (isGood) {
            await fetch(`${API_BASE_URL}/learning/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, response }),
            });
        } else {
            await fetch(`${API_BASE_URL}/learning/correct`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ original_input: question, original_output: response, corrected_output: '' }),
            });
        }
    } catch {}
}

function addSpeakerButton(msgDiv, text) {
    if (!text.trim()) return;
    const btn = document.createElement('button');
    btn.className = 'speaker-btn';
    btn.title = 'Read aloud';
    btn.textContent = '🔊';
    btn.onclick = () => speakText(text);
    const bar = msgDiv.querySelector('.feedback-bar');
    if (bar) bar.appendChild(btn);
}

function escapeAttr(str) {
    return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n').slice(0, 500);
}

// ── Projects ──────────────────────────────────────────────────────────────────

async function loadProjects() {
    try {
        const res = await fetch(`${API_BASE_URL}/projects/`);
        if (!res.ok) return;
        const data = await res.json();
        const sel = document.getElementById('projectSelect');
        if (!sel) return;
        sel.innerHTML = '';
        for (const p of data.projects || []) {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `📁 ${p.name}`;
            if (p.id === _activeProject) opt.selected = true;
            sel.appendChild(opt);
        }
        // Ensure default always present
        if (!data.projects?.length) {
            sel.innerHTML = '<option value="default">📁 Default</option>';
        }
    } catch {}
}

function switchProject(id) {
    _activeProject = id;
    messagesContainer.innerHTML = '';
    displayMessage('assistant', `Switched to project **${id}**. History is isolated to this project.`);
}

function showNewProjectDialog() {
    document.getElementById('newProjectDialog').classList.remove('hidden');
    document.getElementById('newProjectName').focus();
}

function closeDialog() {
    document.getElementById('newProjectDialog').classList.add('hidden');
    document.getElementById('newProjectName').value = '';
}

async function createProject() {
    const name = document.getElementById('newProjectName').value.trim();
    if (!name) return;
    try {
        const res = await fetch(`${API_BASE_URL}/projects/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (res.ok) {
            const p = await res.json();
            closeDialog();
            await loadProjects();
            document.getElementById('projectSelect').value = p.id;
            switchProject(p.id);
        }
    } catch {}
}

// ── Model management ──────────────────────────────────────────────────────────

let _dismissedSuggestion = false;

async function updateModelsPanel() {
    const panel = document.getElementById('modelsList');
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE_URL}/system/models`);
        if (!res.ok) { panel.innerHTML = '<p>Ollama not running</p>'; return; }
        const d = await res.json();

        if (!d.ollama_running) {
            panel.innerHTML = '<p style="color:#ef4444">Ollama offline — run: <code>ollama serve</code></p>';
            return;
        }

        // Show model suggestion banner if recommended != active and user hasn't dismissed
        if (d.recommended && d.active && !_dismissedSuggestion) {
            const recBase = d.recommended.split(':')[0];
            const activeBase = d.active.split(':')[0];
            if (recBase !== activeBase) {
                _suggestedModel = d.recommended;
                const banner = document.getElementById('modelSuggestion');
                const text   = document.getElementById('modelSuggestionText');
                if (banner && text) {
                    text.textContent = `💡 Your ${d.hardware_summary} is best matched to ${d.recommended}. Currently using ${d.active}.`;
                    banner.classList.remove('hidden');
                    document.getElementById('modelSuggestionBtn').textContent = `Switch to ${d.recommended}`;
                }
            }
        }

        let html = '';
        for (const m of d.models) {
            const stratColor = { full_gpu: '#22c55e', hybrid: '#f59e0b', cpu_only: '#ef4444' }[m.strategy] || '#94a3b8';
            const tag = m.is_recommended ? ' ⭐' : '';
            const active = m.name === d.active ? ' <span style="color:#667eea">(active)</span>' : '';
            html += `<div class="model-item" onclick="switchModelUI('${m.name}')">
                <div class="model-name">${m.name}${tag}${active}</div>
                <div class="model-meta">
                    <span style="color:${stratColor}">${m.strategy || 'unknown'}</span>
                    <span>${m.size_gb}GB</span>
                    <span>${m.vram_used_gb ? m.vram_used_gb + 'GB VRAM' : ''}</span>
                </div>
                ${m.warnings?.length ? `<div class="model-warn">⚠ ${m.warnings[0]}</div>` : ''}
            </div>`;
        }
        panel.innerHTML = html || '<p>No models installed. Run: <code>ollama pull qwen2.5:7b</code></p>';
        panel.innerHTML += `<div style="font-size:11px;color:#94a3b8;margin-top:8px">Click model to switch · ${d.hardware_summary}</div>`;
    } catch {
        panel.innerHTML = '<p>Unavailable</p>';
    }
}

async function switchModelUI(name) {
    try {
        await fetch(`${API_BASE_URL}/system/models/switch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: name }),
        });
        _activeModel = name;
        const mb = document.getElementById('modelBadge');
        if (mb) mb.textContent = `🤖 ${name}`;
        await updateModelsPanel();
    } catch {}
}

async function acceptModelSuggestion() {
    if (_suggestedModel) await switchModelUI(_suggestedModel);
    dismissModelSuggestion();
}

function dismissModelSuggestion() {
    _dismissedSuggestion = true;
    document.getElementById('modelSuggestion')?.classList.add('hidden');
}

// ── Skills panel ──────────────────────────────────────────────────────────────

async function updateSkillsPanel() {
    const panel = document.getElementById('skillsList');
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE_URL}/skills/`);
        if (!res.ok) { panel.innerHTML = '<p>Failed</p>'; return; }
        const data = await res.json();
        const skills = data.skills || [];
        if (!skills.length) { panel.innerHTML = '<p>No skills loaded</p>'; return; }
        panel.innerHTML = skills.map(s =>
            `<div class="skill-item" title="${s.description || ''}">
                <span class="skill-name">${s.name}</span>
                <span class="skill-desc">${(s.description || '').slice(0, 50)}${(s.description || '').length > 50 ? '…' : ''}</span>
            </div>`
        ).join('');
    } catch {
        panel.innerHTML = '<p>Unavailable</p>';
    }
}

// ── System / Hardware panels ──────────────────────────────────────────────────

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (res.ok) {
            const data = await res.json();
            setStatus(data.status !== 'error', data.message || 'Online');
        } else {
            setStatus(false, 'Backend unavailable');
        }
    } catch {
        setStatus(false, 'Connection failed');
    }
}

function setStatus(online, message) {
    if (!statusDot || !statusText) return;
    statusDot.classList.toggle('offline', !online);
    statusText.textContent = message;
}

async function updateSystemStatus() {
    const panel = document.getElementById('systemStatus');
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE_URL}/system/status`);
        if (!res.ok) { panel.innerHTML = '<p class="error">Failed</p>'; return; }
        const d = await res.json();
        panel.innerHTML = `
            <div class="status-item"><span class="status-label">Provider:</span><span class="status-value">${d.model_provider}</span></div>
            <div class="status-item"><span class="status-label">Model:</span><span class="status-value" style="color:#2ecc71">${d.active_model || 'unknown'}</span></div>
            <div class="status-item"><span class="status-label">DB:</span><span class="status-value">${d.database_connected ? '✓ Connected' : '✗ Error'}</span></div>
            <div class="status-item"><span class="status-label">Uptime:</span><span class="status-value">${formatUptime(d.uptime_seconds)}</span></div>
            <div class="status-item"><span class="status-label">Tasks:</span><span class="status-value">${d.task_count}</span></div>
            <div class="status-item"><span class="status-label">Memory:</span><span class="status-value">${d.memory_count}</span></div>
        `;
    } catch { panel.innerHTML = '<p>Unavailable</p>'; }
}

async function updateHardwareStatus() {
    const panel = document.getElementById('hardwareStatus');
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE_URL}/system/hardware`);
        if (!res.ok) { panel.innerHTML = '<p class="error">Failed</p>'; return; }
        const d = await res.json();
        const tierColors = ['', '#e74c3c', '#f39c12', '#3498db', '#2ecc71'];
        const tierColor = tierColors[d.tier] || '#999';
        panel.innerHTML = `
            <div class="hw-static">
                <div class="status-item"><span class="status-label">Tier:</span><span class="status-value" style="color:${tierColor}">T${d.tier} — ${d.tier_label}</span></div>
                <div class="status-item"><span class="status-label">RAM:</span><span class="status-value">${d.ram_gb}GB (${d.ram_available_gb}GB free)</span></div>
                <div class="status-item"><span class="status-label">GPU:</span><span class="status-value">${d.gpu_name}</span></div>
                <div class="status-item"><span class="status-label">VRAM:</span><span class="status-value">${d.gpu_vram_gb}GB</span></div>
                <div class="status-item"><span class="status-label">Recommended:</span><span class="status-value" style="color:#7c6ff7;cursor:pointer" onclick="switchModelUI('${d.recommended_model}')" title="Click to use this model">${d.recommended_model}</span></div>
                <div class="status-item"><span class="status-label">Max ctx:</span><span class="status-value">${(d.max_context || 0).toLocaleString()} tokens</span></div>
                ${d.warnings.map(w => `<div class="hw-warning">⚠ ${w}</div>`).join('')}
            </div>
            <div class="hw-live" id="hwLive"></div>
        `;
    } catch { panel.innerHTML = '<p>Unavailable</p>'; }
}

async function updateHardwareLive() {
    const liveEl = document.getElementById('hwLive');
    if (!liveEl) { updateHardwareStatus(); return; }
    try {
        const res = await fetch(`${API_BASE_URL}/system/hardware/live`);
        if (!res.ok) return;
        const d = await res.json();
        const pressureColor = { low: '#2ecc71', medium: '#f59e0b', high: '#e67e22', critical: '#e74c3c' };
        const col = pressureColor[d.pressure] || '#999';
        const modelStatus = d.loaded_models?.length
            ? d.loaded_models.map(m => `<span style="color:#2ecc71">⚡ ${m.name} (${m.size_mb}MB GPU)</span>`).join('<br>')
            : '<span style="opacity:0.5">idle</span>';
        liveEl.innerHTML = `
            <div class="status-item"><span class="status-label">GPU:</span><span class="status-value" style="color:${d.gpu_temp_c > 75 ? '#e74c3c' : '#2ecc71'}">${d.gpu_temp_c}°C · ${d.gpu_util_percent}%</span></div>
            <div class="status-item"><span class="status-label">VRAM:</span><span class="status-value">${d.vram_used_mb.toFixed(0)}/${d.vram_total_mb.toFixed(0)} MB</span></div>
            <div class="status-item"><span class="status-label">CPU:</span><span class="status-value">${d.cpu_percent.toFixed(0)}% · RAM ${d.ram_percent.toFixed(0)}%</span></div>
            <div class="status-item"><span class="status-label">Pressure:</span><span class="status-value" style="color:${col}">${d.pressure}</span></div>
            <div class="status-item" style="flex-direction:column;align-items:flex-start"><span class="status-label">In GPU:</span>${modelStatus}</div>
        `;
    } catch {}
}

async function updateAgentsList() {
    const panel = document.getElementById('agentsList');
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE_URL}/agents/`);
        if (!res.ok) { panel.innerHTML = '<p>Failed</p>'; return; }
        const data = await res.json();
        panel.innerHTML = data.agents.map(a =>
            `<div class="agent-item">
                <span class="agent-name">${a.name || a.agent_type}</span>
                <span class="agent-status ${a.is_available ? 'ok' : 'err'}">${a.is_available ? '●' : '○'}</span>
            </div>`
        ).join('') || '<p>No agents</p>';
    } catch { panel.innerHTML = '<p>Unavailable</p>'; }
}

async function updateStats() {
    const panel = document.getElementById('statsContent');
    if (!panel) return;
    try {
        const [tr, mr] = await Promise.all([
            fetch(`${API_BASE_URL}/tasks/stats/overview`),
            fetch(`${API_BASE_URL}/memory/stats/overview`),
        ]);
        if (!tr.ok || !mr.ok) { panel.innerHTML = '<p>Failed</p>'; return; }
        const td = await tr.json();
        const md = await mr.json();
        panel.innerHTML = `
            <div class="stat-item"><span class="stat-label">Tasks:</span><span class="stat-value">${td.total}</span></div>
            <div class="stat-item"><span class="stat-label">Pending:</span><span class="stat-value">${td.pending}</span></div>
            <div class="stat-item"><span class="stat-label">Done:</span><span class="stat-value">${td.completed}</span></div>
            <div class="stat-item"><span class="stat-label">Memory:</span><span class="stat-value">${md.total_entries}</span></div>
        `;
    } catch { panel.innerHTML = '<p>Unavailable</p>'; }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function displayMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    const inner = document.createElement('div');
    inner.className = 'message-content';
    inner.innerHTML = marked.parse(content);
    div.appendChild(inner);
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function displayThinking(text = '⏳ ILLIP is thinking...') {
    const id = 'thinking-' + Date.now();
    const div = document.createElement('div');
    div.className = 'message assistant thinking';
    div.id = id;
    div.innerHTML = `<div class="message-content"><em>${text}</em></div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
    return id;
}

function removeThinking(id) {
    document.getElementById(id)?.remove();
}

function scrollToBottom() {
    setTimeout(() => { messagesContainer.scrollTop = messagesContainer.scrollHeight; }, 0);
}

function toggleInput(disabled) {
    messageInput.disabled = disabled;
    document.getElementById('sendBtn').disabled = disabled;
    if (!disabled) messageInput.focus();
}

function formatUptime(s) {
    if (s < 60)    return `${Math.floor(s)}s`;
    if (s < 3600)  return `${Math.floor(s / 60)}m`;
    if (s < 86400) return `${Math.floor(s / 3600)}h`;
    return `${Math.floor(s / 86400)}d`;
}

// ── Refresh (clear stuck context, keep all data) ──────────────────────────────

async function refreshSystem() {
    const btn = document.querySelector('.refresh-btn');
    if (btn) { btn.textContent = '↺ …'; btn.disabled = true; }
    try {
        const res = await fetch(`${API_BASE_URL}/system/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: _activeProject }),
        });
        const d = await res.json();
        // Show in chat as system message
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.innerHTML = `<div class="message-content" style="background:#f0fdf4;border:1px solid #bbf7d0;color:#166534">
            <strong>↺ Context refreshed</strong><br>
            ${d.cleared.join(' · ')}<br>
            <small>All history and memory preserved on disk. Fresh start, no data lost.</small>
        </div>`;
        messagesContainer.appendChild(div);
        scrollToBottom();
    } catch (e) {
        displayMessage('assistant', `**Refresh failed:** ${e.message}`);
    } finally {
        if (btn) { btn.textContent = '↺ Refresh'; btn.disabled = false; }
    }
}

// Also handle "!refresh" typed in chat
const _origHandleSubmit = null;  // override below in init

// ── Plugins / Connectors ──────────────────────────────────────────────────────

let _pluginTemplates = [];

async function updatePluginsPanel() {
    const panel = document.getElementById('pluginsList');
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE_URL}/plugins/`);
        if (!res.ok) { panel.innerHTML = '<p>Failed</p>'; return; }
        const d = await res.json();
        if (!d.plugins.length) {
            panel.innerHTML = '<p style="color:#94a3b8;font-size:12px">No plugins yet.<br>Click ＋ to add a connector.</p>';
            return;
        }
        panel.innerHTML = d.plugins.map(p => `
            <div class="plugin-item">
                <span class="plugin-name">${p.display_name || p.name}</span>
                <span class="plugin-type">${p.plugin_type || 'http'}</span>
                <button class="plugin-del" onclick="deletePlugin('${p.name}')" title="Remove">✕</button>
            </div>
        `).join('');
    } catch { panel.innerHTML = '<p>Unavailable</p>'; }
}

async function showPluginDialog() {
    document.getElementById('pluginDialog').classList.remove('hidden');
    // Load templates if not loaded yet
    if (!_pluginTemplates.length) {
        try {
            const res = await fetch(`${API_BASE_URL}/plugins/templates`);
            if (res.ok) {
                const d = await res.json();
                _pluginTemplates = d.templates || [];
                const sel = document.getElementById('pluginTemplate');
                for (const t of _pluginTemplates) {
                    const opt = document.createElement('option');
                    opt.value = t.name;
                    opt.textContent = t.display_name || t.name;
                    sel.appendChild(opt);
                }
            }
        } catch {}
    }
}

function loadPluginTemplate(name) {
    if (!name) return;
    const t = _pluginTemplates.find(t => t.name === name);
    if (t) document.getElementById('pluginJson').value = JSON.stringify(t, null, 2);
}

async function savePlugin() {
    const raw = document.getElementById('pluginJson').value.trim();
    if (!raw) return;
    let spec;
    try { spec = JSON.parse(raw); }
    catch (e) { alert(`Invalid JSON: ${e.message}`); return; }
    try {
        const res = await fetch(`${API_BASE_URL}/plugins/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(spec),
        });
        if (!res.ok) { const e = await res.json(); alert(e.detail || 'Failed'); return; }
        closePluginDialog();
        await updatePluginsPanel();
        await updateSkillsPanel();   // plugin now shows as skill too
    } catch (e) { alert(`Error: ${e.message}`); }
}

async function deletePlugin(name) {
    if (!confirm(`Delete plugin "${name}"?`)) return;
    try {
        await fetch(`${API_BASE_URL}/plugins/${name}`, { method: 'DELETE' });
        await updatePluginsPanel();
        await updateSkillsPanel();
    } catch {}
}

function closePluginDialog() {
    document.getElementById('pluginDialog').classList.add('hidden');
    document.getElementById('pluginJson').value = '';
    document.getElementById('pluginTemplate').value = '';
}

// ── Voice ─────────────────────────────────────────────────────────────────────

let _mediaRecorder = null;
let _audioChunks   = [];
let _isRecording   = false;
let _autoSpeak     = false;
let _voiceAvailable = false;   // STT backend available
let _ttsMode       = 'browser'; // 'browser' | 'piper'

async function initVoice() {
    try {
        const res = await fetch(`${API_BASE_URL}/voice/status`);
        if (!res.ok) return;
        const d = await res.json();
        _voiceAvailable = d.stt;
        _ttsMode = d.tts_backend;
        const micBtn = document.getElementById('micBtn');
        if (micBtn) {
            micBtn.title = _voiceAvailable
                ? `Click to record · Whisper ${d.stt_model} · ${d.tts_note}`
                : `STT unavailable: ${d.install_stt}`;
            micBtn.disabled = !_voiceAvailable;
            if (!_voiceAvailable) micBtn.style.opacity = '0.4';
        }
        // Vision availability
        const imgBtn = document.querySelector('.img-btn');
        if (imgBtn && !d.vision_ready) {
            imgBtn.title = `Vision not ready: ${d.install_vision || 'ollama pull llava-phi3'}`;
        } else if (imgBtn) {
            imgBtn.title = `Attach image · Vision model: ${d.vision_model}`;
        }
    } catch {}
}

// ── Vision / Image ─────────────────────────────────────────────────────────────

let _pendingImage = null;  // { file, dataUrl }

function onImageSelected(input) {
    const file = input.files[0];
    if (!file) return;
    _pendingImage = { file };
    const reader = new FileReader();
    reader.onload = e => {
        _pendingImage.dataUrl = e.target.result;
        const preview = document.getElementById('imagePreview');
        const img = document.getElementById('imagePreviewImg');
        if (preview && img) {
            img.src = e.target.result;
            preview.classList.remove('hidden');
        }
    };
    reader.readAsDataURL(file);
    // Reset input so same file can be reselected
    input.value = '';
}

function clearImage() {
    _pendingImage = null;
    const preview = document.getElementById('imagePreview');
    if (preview) preview.classList.add('hidden');
}

async function sendImageToVision(file, prompt) {
    const form = new FormData();
    form.append('file', file);
    form.append('prompt', prompt || 'Describe this image in detail.');
    try {
        const res = await fetch(`${API_BASE_URL}/voice/vision/analyze`, {
            method: 'POST',
            body: form,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return `Vision error: ${err.detail || res.statusText}`;
        }
        const d = await res.json();
        return d.description || '(no description)';
    } catch (e) {
        return `Vision error: ${e.message}`;
    }
}

async function toggleMic() {
    if (!_voiceAvailable) {
        showVoiceStatus('STT not available — run: pip install faster-whisper', 'error');
        return;
    }
    if (_isRecording) {
        stopRecording();
    } else {
        await startRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        _audioChunks = [];
        // Prefer WebM (Chrome) then OGG (Firefox) — both supported by Whisper via ffmpeg
        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
        _mediaRecorder = new MediaRecorder(stream, { mimeType });
        _mediaRecorder.ondataavailable = e => { if (e.data.size > 0) _audioChunks.push(e.data); };
        _mediaRecorder.onstop = sendAudioToSTT;
        _mediaRecorder.start(250);   // collect chunks every 250ms
        _isRecording = true;
        const micBtn = document.getElementById('micBtn');
        if (micBtn) { micBtn.textContent = '⏹'; micBtn.classList.add('recording'); }
        showVoiceStatus('🎙 Recording… click ⏹ to stop', 'recording');
    } catch (e) {
        showVoiceStatus(`Mic error: ${e.message}`, 'error');
    }
}

function stopRecording() {
    if (_mediaRecorder && _isRecording) {
        _mediaRecorder.stop();
        _mediaRecorder.stream.getTracks().forEach(t => t.stop());
        _isRecording = false;
        const micBtn = document.getElementById('micBtn');
        if (micBtn) { micBtn.textContent = '🎤'; micBtn.classList.remove('recording'); }
        showVoiceStatus('⏳ Transcribing…', 'loading');
    }
}

async function sendAudioToSTT() {
    if (!_audioChunks.length) { hideVoiceStatus(); return; }
    const mimeType = _audioChunks[0].type || 'audio/webm';
    const ext = mimeType.includes('ogg') ? '.ogg' : '.webm';
    const blob = new Blob(_audioChunks, { type: mimeType });
    _audioChunks = [];

    const form = new FormData();
    form.append('file', blob, `recording${ext}`);
    try {
        const res = await fetch(`${API_BASE_URL}/voice/transcribe`, { method: 'POST', body: form });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showVoiceStatus(`STT error: ${err.detail || res.statusText}`, 'error');
            return;
        }
        const d = await res.json();
        if (d.text) {
            messageInput.value = d.text;
            messageInput.focus();
            showVoiceStatus(`✓ "${d.text.slice(0, 60)}${d.text.length > 60 ? '…' : ''}" (${d.language}, ${d.duration_s}s)`, 'ok');
            setTimeout(hideVoiceStatus, 3000);
        } else {
            showVoiceStatus('No speech detected', 'error');
            setTimeout(hideVoiceStatus, 2000);
        }
    } catch (e) {
        showVoiceStatus(`Transcription failed: ${e.message}`, 'error');
    }
}

function showVoiceStatus(msg, type) {
    const el = document.getElementById('voiceStatus');
    if (!el) return;
    el.textContent = msg;
    el.className = `voice-status ${type}`;
}

function hideVoiceStatus() {
    const el = document.getElementById('voiceStatus');
    if (el) el.className = 'voice-status hidden';
}

// TTS — speak assistant response text
function speakText(text) {
    // Strip markdown before speaking
    const plain = text.replace(/```[\s\S]*?```/g, 'code block')
                      .replace(/`[^`]+`/g, '')
                      .replace(/[#*_~[\]()]/g, '')
                      .trim();
    if (!plain) return;

    if (_ttsMode === 'piper') {
        // Stream audio from backend Piper TTS
        const audio = new Audio();
        audio.src = `${API_BASE_URL}/voice/speak`;
        fetch(`${API_BASE_URL}/voice/speak`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: plain.slice(0, 500) }),
        }).then(res => {
            if (res.status === 501) {
                // Piper not installed — fall back to browser
                _ttsMode = 'browser';
                browserSpeak(plain);
            } else if (res.ok) {
                return res.blob().then(blob => {
                    const url = URL.createObjectURL(blob);
                    const a = new Audio(url);
                    a.play();
                    a.onended = () => URL.revokeObjectURL(url);
                });
            }
        }).catch(() => browserSpeak(plain));
    } else {
        browserSpeak(plain);
    }
}

function browserSpeak(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text.slice(0, 500));
    utt.rate = 1.0;
    utt.pitch = 1.0;
    // Pick a natural-sounding voice if available
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.lang.startsWith('en') && v.localService) || voices[0];
    if (preferred) utt.voice = preferred;
    window.speechSynthesis.speak(utt);
}

function toggleAutoSpeak() {
    _autoSpeak = !_autoSpeak;
    const btn = document.getElementById('autoSpeakToggle');
    if (btn) {
        btn.textContent = _autoSpeak ? '🔊 Speak' : '🔇 Speak';
        btn.classList.toggle('active', _autoSpeak);
    }
}

// ── Deep Research (Perplexity-style) ─────────────────────────────────────────

let _researchDepth = 'standard';
let _researchSSE = null;

function setDepth(d) {
    _researchDepth = d;
    document.querySelectorAll('.depth-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById('depth' + d.charAt(0).toUpperCase() + d.slice(1));
    if (btn) btn.classList.add('active');
}

function startResearch() {
    const query = document.getElementById('messageInput').value.trim();
    if (!query) { alert('Type a question first, then click Research.'); return; }

    const panel = document.getElementById('researchPanel');
    const steps = document.getElementById('researchSteps');
    const answer = document.getElementById('researchAnswer');
    const sources = document.getElementById('researchSources');

    panel.classList.remove('hidden');
    steps.innerHTML = '';
    answer.classList.add('hidden');
    sources.classList.add('hidden');
    answer.innerHTML = '';
    sources.innerHTML = '';

    document.getElementById('researchBtn').disabled = true;
    document.getElementById('researchBtn').textContent = '⏳ Researching...';

    if (_researchSSE) { _researchSSE.close(); }

    const url = `/api/research/stream?query=${encodeURIComponent(query)}&depth=${_researchDepth}`;
    _researchSSE = new EventSource(url);

    _researchSSE.onmessage = (e) => {
        const data = JSON.parse(e.data);
        _handleResearchStep(data, steps, answer, sources);
    };

    _researchSSE.onerror = () => {
        _researchSSE.close();
        _researchSSE = null;
        _appendStep(steps, 'error', '❌ Connection lost. Try again.');
        document.getElementById('researchBtn').disabled = false;
        document.getElementById('researchBtn').textContent = '🔍 Research';
    };
}

function _handleResearchStep(data, steps, answer, sources) {
    const icons = {
        decompose: '🧠',
        search: '🔍',
        read: '📄',
        synthesize: '⚡',
        done: '✅',
        error: '❌',
    };
    const icon = icons[data.type] || '•';

    if (data.type === 'done') {
        _researchSSE.close();
        _researchSSE = null;

        // Show answer
        answer.classList.remove('hidden');
        answer.innerHTML = `<div class="research-answer-text">${_mdToHtml(data.data.answer || '')}</div>`;

        // Show sources
        if (data.data.sources && data.data.sources.length > 0) {
            sources.classList.remove('hidden');
            sources.innerHTML = '<div class="sources-title">Sources</div>' +
                data.data.sources.map((s, i) =>
                    `<a href="${s.url}" target="_blank" class="source-chip">
                        <span class="source-num">${i+1}</span>
                        <span class="source-title">${s.title || s.url}</span>
                    </a>`
                ).join('');
        }

        document.getElementById('researchBtn').disabled = false;
        document.getElementById('researchBtn').textContent = '🔍 Research';

        _appendStep(steps, 'done', `${icon} Done — ${data.data.steps_taken || ''} steps`);
        return;
    }

    if (data.type === 'error') {
        _researchSSE && _researchSSE.close();
        _researchSSE = null;
        document.getElementById('researchBtn').disabled = false;
        document.getElementById('researchBtn').textContent = '🔍 Research';
    }

    _appendStep(steps, data.type, `${icon} ${data.message}`);
}

function _appendStep(container, type, text) {
    const el = document.createElement('div');
    el.className = `research-step research-step-${type}`;
    el.textContent = text;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
}

function closeResearch() {
    if (_researchSSE) { _researchSSE.close(); _researchSSE = null; }
    document.getElementById('researchPanel').classList.add('hidden');
    document.getElementById('researchBtn').disabled = false;
    document.getElementById('researchBtn').textContent = '🔍 Research';
}

function _mdToHtml(text) {
    // Minimal markdown → HTML for research answer
    return text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\[(\d+)\]/g, '<sup class="cite">[$1]</sup>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^(.*)$/, '<p>$1</p>');
}

// ── Boot ──────────────────────────────────────────────────────────────────────

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
