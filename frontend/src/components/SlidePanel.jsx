import React from 'react'
import SystemPanel from './panels/SystemPanel.jsx'
import HardwarePanel from './panels/HardwarePanel.jsx'
import ModelsPanel from './panels/ModelsPanel.jsx'
import GhostEnginePanel from './panels/GhostEnginePanel.jsx'
import SkillsPanel from './panels/SkillsPanel.jsx'
import AgentsPanel from './panels/AgentsPanel.jsx'
import HealthPanel from './panels/HealthPanel.jsx'
import GovernancePanel from './panels/GovernancePanel.jsx'
import WorkflowsPanel from './panels/WorkflowsPanel.jsx'
import SchedulerPanel from './panels/SchedulerPanel.jsx'
import PluginsPanel from './panels/PluginsPanel.jsx'
import StatsPanel from './panels/StatsPanel.jsx'

const TITLES = {
  system: 'System Status', hardware: 'Hardware', models: 'Models',
  ghost: '👻 Ghost Engine', skills: 'Skills', agents: 'Agents',
  health: 'Health Monitor', governance: 'Governance', workflows: 'Workflows',
  scheduler: 'Scheduler', plugins: 'Plugins', stats: 'Stats',
}

export default function SlidePanel({
  activePanel, onClose,
  systemStatus, hardwareStatus, hwLive, modelsData, skills, agents,
  plugins, healthData, govPending, schedulerJobs, stats, pinnedModel,
  onSwitchModel, onGovApprove, onGovDeny, onSchedRun, onSchedToggle,
  onAddPlugin, onDeletePlugin, onInstallSkill, onShowMarketplace, onCreateJob,
}) {
  const panelProps = {
    system:     { component: SystemPanel,       props: { data: systemStatus } },
    hardware:   { component: HardwarePanel,     props: { data: hardwareStatus, live: hwLive, onSwitchModel } },
    models:     { component: ModelsPanel,       props: { data: modelsData, onSwitch: onSwitchModel } },
    ghost:      { component: GhostEnginePanel,  props: { models: modelsData, activeModel: modelsData?.active || pinnedModel } },
    skills:     { component: SkillsPanel,       props: { skills, onInstall: onInstallSkill } },
    agents:     { component: AgentsPanel,     props: { agents } },
    health:     { component: HealthPanel,     props: { data: healthData } },
    governance: { component: GovernancePanel, props: { pending: govPending, onApprove: onGovApprove, onDeny: onGovDeny } },
    workflows:  { component: WorkflowsPanel,  props: { jobs: schedulerJobs, onRun: onSchedRun, onToggle: onSchedToggle, onCreate: onCreateJob } },
    scheduler:  { component: SchedulerPanel,  props: { jobs: schedulerJobs, onRun: onSchedRun, onToggle: onSchedToggle, onCreate: onCreateJob } },
    plugins:    { component: PluginsPanel,    props: { plugins, onAdd: onAddPlugin, onDelete: onDeletePlugin, onMarketplace: onShowMarketplace } },
    stats:      { component: StatsPanel,      props: { data: stats } },
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
