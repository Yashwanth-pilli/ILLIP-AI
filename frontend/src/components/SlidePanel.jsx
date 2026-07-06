import React from 'react'
import SystemPanel from './panels/SystemPanel.jsx'
import HardwarePanel from './panels/HardwarePanel.jsx'
import ModelsPanel from './panels/ModelsPanel.jsx'
import GhostEnginePanel from './panels/GhostEnginePanel.jsx'
import SkillsPanel from './panels/SkillsPanel.jsx'
import HealthPanel from './panels/HealthPanel.jsx'
import GovernancePanel from './panels/GovernancePanel.jsx'
import SchedulerPanel from './panels/SchedulerPanel.jsx'
import PluginsPanel from './panels/PluginsPanel.jsx'
import StatsPanel from './panels/StatsPanel.jsx'
import MemoryPanel from './panels/MemoryPanel.jsx'
import WorkspacePanel from './panels/WorkspacePanel.jsx'
import ChatHistoryPanel from './panels/ChatHistoryPanel.jsx'

const TITLES = {
  chats: 'Chats',
  system: 'System & Health', models: 'Models & Ghost Engine',
  skills: 'Skills', governance: 'Governance',
  scheduler: 'Scheduler', plugins: 'Plugins', stats: 'Stats',
  memory: 'Memory', workspace: 'Workspace',
}

function PanelSection({ title, desc, children }) {
  return (
    <div className="panel-section">
      <div className="panel-section-title">{title}</div>
      {desc && <p className="panel-section-desc">{desc}</p>}
      {children}
    </div>
  )
}

// Merged: system status + live hardware + health bars were three separate
// tabs showing overlapping CPU/RAM/GPU numbers. One "System & Health" tab.
function SystemAndHealthPanel({ systemStatus, hardwareStatus, hwLive, healthData, onSwitchModel }) {
  return (
    <div>
      <PanelSection title="System" desc="Which model's running, is memory connected, how long ILLIP's been up.">
        <SystemPanel data={systemStatus} />
      </PanelSection>
      <PanelSection title="Hardware" desc="Your machine's specs, and how hot/busy it's running right now.">
        <HardwarePanel data={hardwareStatus} live={hwLive} onSwitchModel={onSwitchModel} />
      </PanelSection>
      <PanelSection title="Health" desc="Quick health check — CPU, RAM, GPU load and disk space.">
        <HealthPanel data={healthData} />
      </PanelSection>
    </div>
  )
}

// Merged: model list (switch) + Ghost Engine (per-model GPU/VRAM plan) were
// two separate tabs about the same models. One "Models & Ghost Engine" tab.
function ModelsAndGhostPanel({ modelsData, onSwitchModel, pinnedModel }) {
  return (
    <div>
      <PanelSection title="Installed Models" desc="Every AI model on your machine — click one to switch ILLIP's brain.">
        <ModelsPanel data={modelsData} onSwitch={onSwitchModel} />
      </PanelSection>
      <PanelSection title="Ghost Engine Plan" desc="Maps each model to an optimal GPU/CPU split for your hardware.">
        <GhostEnginePanel models={modelsData} activeModel={modelsData?.active || pinnedModel} />
      </PanelSection>
    </div>
  )
}

export default function SlidePanel({
  activePanel, onClose,
  systemStatus, hardwareStatus, hwLive, modelsData, skills,
  plugins, healthData, govPending, schedulerJobs, stats, pinnedModel,
  onSwitchModel, onGovApprove, onGovDeny, onSchedRun, onSchedToggle,
  onAddPlugin, onDeletePlugin, onInstallSkill, onShowMarketplace, onCreateJob,
  activeProject, projects, onSwitchProject, onDeleteProject, onNewChat,
}) {
  const panelProps = {
    chats:      { component: ChatHistoryPanel,     props: { projects, activeProject, onSwitchProject, onDeleteProject, onNewChat, onClose } },
    system:     { component: SystemAndHealthPanel, props: { systemStatus, hardwareStatus, hwLive, healthData, onSwitchModel } },
    models:     { component: ModelsAndGhostPanel,  props: { modelsData, onSwitchModel, pinnedModel } },
    skills:     { component: SkillsPanel,          props: { skills, onInstall: onInstallSkill } },
    governance: { component: GovernancePanel,      props: { pending: govPending, onApprove: onGovApprove, onDeny: onGovDeny } },
    scheduler:  { component: SchedulerPanel,       props: { jobs: schedulerJobs, onRun: onSchedRun, onToggle: onSchedToggle, onCreate: onCreateJob } },
    plugins:    { component: PluginsPanel,         props: { plugins, onAdd: onAddPlugin, onDelete: onDeletePlugin, onMarketplace: onShowMarketplace } },
    stats:      { component: StatsPanel,           props: { data: stats } },
    memory:     { component: MemoryPanel,          props: { projectId: activeProject || 'default' } },
    workspace:  { component: WorkspacePanel,       props: { projectId: activeProject || 'default' } },
  }

  const current = activePanel ? panelProps[activePanel] : null
  const PanelComponent = current?.component

  return (
    <div className={`slide-panel ${activePanel ? 'open' : ''}`}>
      <div className="slide-panel-header">
        <span className="slide-panel-title">{TITLES[activePanel] || ''}</span>
        <button className="slide-close-btn" onClick={onClose}>✕</button>
      </div>
      <div className="slide-panel-body">
        {PanelComponent && (
          <div className="tab-content">
            <PanelComponent {...(current.props || {})} />
          </div>
        )}
      </div>
    </div>
  )
}
