const BASE = `${window.location.protocol}//${window.location.host}/api`

export const api = {
  // Health
  health: () => fetch(`${BASE}/health`).then(r => r.json()),

  // System
  systemStatus: () => fetch(`${BASE}/system/status`).then(r => r.json()),
  systemModels: () => fetch(`${BASE}/system/models`).then(r => r.json()),
  systemHardware: () => fetch(`${BASE}/system/hardware`).then(r => r.json()),
  systemHardwareLive: () => fetch(`${BASE}/system/hardware/live`).then(r => r.json()),
  switchModel: (model) => fetch(`${BASE}/system/models/switch`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  }).then(r => r.json()),
  ghostEngine: (model) => fetch(`${BASE}/system/ghost-engine/${encodeURIComponent(model)}`).then(r => r.json()),
  refresh: (project_id) => fetch(`${BASE}/system/refresh`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id }),
  }).then(r => r.json()),

  // Chat
  chatStream: (payload) => fetch(`${BASE}/chat/stream`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),

  // Projects
  projects: () => fetch(`${BASE}/projects/`).then(r => r.json()),
  createProject: (name) => fetch(`${BASE}/projects/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then(r => r.json()),

  // Skills
  skills: () => fetch(`${BASE}/skills/`).then(r => r.json()),
  installSkill: (url) => fetch(`${BASE}/skills/install`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).then(r => r.json()),

  // Agents
  agents: () => fetch(`${BASE}/agents/`).then(r => r.json()),

  // Plugins
  plugins: () => fetch(`${BASE}/plugins/`).then(r => r.json()),
  pluginTemplates: () => fetch(`${BASE}/plugins/templates`).then(r => r.json()),
  savePlugin: (spec) => fetch(`${BASE}/plugins/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(spec),
  }).then(r => r.json()),
  deletePlugin: (name) => fetch(`${BASE}/plugins/${name}`, { method: 'DELETE' }),

  // Governance
  govPending: () => fetch(`${BASE}/governance/pending`).then(r => r.json()),
  govApprove: (id) => fetch(`${BASE}/governance/approve/${id}`, { method: 'POST' }),
  govDeny: (id) => fetch(`${BASE}/governance/deny/${id}`, { method: 'POST' }),

  // Scheduler
  schedulerJobs: () => fetch(`${BASE}/scheduler/jobs`).then(r => r.json()),
  createJob: (data) => fetch(`${BASE}/scheduler/jobs`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json()),
  runJob: (id) => fetch(`${BASE}/scheduler/jobs/${id}/run`, { method: 'POST' }),
  toggleJob: (id, enable) => fetch(`${BASE}/scheduler/jobs/${id}/${enable ? 'enable' : 'disable'}`, { method: 'POST' }),

  // Monitoring
  monitoringCurrent: () => fetch(`${BASE}/monitoring/current`).then(r => r.json()),

  // Stats
  taskStats: () => fetch(`${BASE}/tasks/stats/overview`).then(r => r.json()),
  memoryStats: () => fetch(`${BASE}/memory/stats/overview`).then(r => r.json()),

  // Voice
  voiceStatus: () => fetch(`${BASE}/voice/status`).then(r => r.json()),
  transcribe: (formData) => fetch(`${BASE}/voice/transcribe`, { method: 'POST', body: formData }).then(r => r.json()),
  speak: (text) => fetch(`${BASE}/voice/speak`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  }),
  visionAnalyze: (formData) => fetch(`${BASE}/voice/vision/analyze`, { method: 'POST', body: formData }).then(r => r.json()),
  documentAnalyze: (formData) => fetch(`${BASE}/voice/document/analyze`, { method: 'POST', body: formData }).then(r => r.json()),

  // Image
  imageGenerate: (data) => fetch(`${BASE}/image/generate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json()),
  imageGallery: () => fetch(`${BASE}/image/gallery?limit=12`).then(r => r.json()),

  // Video
  videoGenerate: (data) => fetch(`${BASE}/video/generate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json()),
  videoGallery: () => fetch(`${BASE}/video/gallery?limit=12`).then(r => r.json()),

  // Learning
  learningApprove: (question, response) => fetch(`${BASE}/learning/approve`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, response }),
  }),
  learningCorrect: (original_input, original_output) => fetch(`${BASE}/learning/correct`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ original_input, original_output, corrected_output: '' }),
  }),

  // Research SSE URL
  researchStreamUrl: (query, depth) =>
    `/api/research/stream?query=${encodeURIComponent(query)}&depth=${depth}`,

  // Browser SSE URL
  browserStreamUrl: (task, startUrl, headless) => {
    let params = `task=${encodeURIComponent(task)}&headless=${headless ? 'false' : 'true'}`
    if (startUrl) params += `&start_url=${encodeURIComponent(startUrl)}`
    return `/api/browser/stream?${params}`
  },
}

export function formatUptime(s) {
  if (s < 60)    return `${Math.floor(s)}s`
  if (s < 3600)  return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}h`
  return `${Math.floor(s / 86400)}d`
}

export function formatSecs(s) {
  if (s < 60)   return `${Math.round(s)}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  return `${Math.round(s / 3600)}h`
}

export function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

export const MARKETPLACE_PLUGINS = [
  { name: "slack-notify", display: "Slack Notifier", desc: "Send messages to Slack channels", type: "http",
    spec: { name: "slack-notify", display_name: "Slack Notifier", plugin_type: "http", url: "", headers: { "Content-Type": "application/json" }, method: "POST", body_template: '{"text": "{{message}}"}' } },
  { name: "discord-webhook", display: "Discord Webhook", desc: "Post to Discord channels", type: "http",
    spec: { name: "discord-webhook", display_name: "Discord Webhook", plugin_type: "http", url: "", headers: { "Content-Type": "application/json" }, method: "POST", body_template: '{"content": "{{message}}"}' } },
  { name: "telegram-notify", display: "Telegram Bot", desc: "Send Telegram messages", type: "http",
    spec: { name: "telegram-notify", display_name: "Telegram Notify", plugin_type: "http", url: "https://api.telegram.org/bot{{token}}/sendMessage", headers: {}, method: "POST", body_template: '{"chat_id": "{{chat_id}}", "text": "{{message}}"}' } },
  { name: "github-issues", display: "GitHub Issues", desc: "Create GitHub issues via API", type: "http",
    spec: { name: "github-issues", display_name: "GitHub Issues", plugin_type: "http", url: "https://api.github.com/repos/{{owner}}/{{repo}}/issues", headers: { "Authorization": "Bearer {{token}}", "Accept": "application/vnd.github.v3+json" }, method: "POST", body_template: '{"title": "{{title}}", "body": "{{body}}"}' } },
  { name: "n8n-webhook", display: "n8n Webhook", desc: "Trigger n8n automation workflows", type: "http",
    spec: { name: "n8n-webhook", display_name: "n8n Webhook", plugin_type: "http", url: "", headers: { "Content-Type": "application/json" }, method: "POST", body_template: '{"data": "{{message}}"}' } },
  { name: "notion-log", display: "Notion Logger", desc: "Append entries to Notion database", type: "http",
    spec: { name: "notion-log", display_name: "Notion Logger", plugin_type: "http", url: "https://api.notion.com/v1/pages", headers: { "Authorization": "Bearer {{token}}", "Notion-Version": "2022-06-28", "Content-Type": "application/json" }, method: "POST", body_template: '{"parent": {"database_id": "{{db_id}}"}, "properties": {"Name": {"title": [{"text": {"content": "{{message}}"}}]}}}' } },
]
