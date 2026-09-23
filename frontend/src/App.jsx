import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Terminal, Search, Cpu, Database, Layout,
  ShieldCheck, AlertCircle, ChevronRight, X,
  FileText, Activity, Clock, Zap, Mic, MicOff,
  Network, Code, MessageSquare, RefreshCw, Download,
  Copy, CheckCircle2
} from 'lucide-react'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useStore } from './store/useStore'
import './App.css'
import LoginView from './components/LoginView'
import ReportViewer from './components/ReportViewer'

// ─────────────────────────────────────────────
// Agent color config v4.0 Sharp
// ─────────────────────────────────────────────
const AGENT_CONFIG = {
  librarian: { accent: '#22c55e', iconBg: 'rgba(34,197,94,0.12)', iconColor: '#22c55e', roleColor: '#4ade80', description: 'Context Retrieval (RAG+KG)', step: '01' },
  architect: { accent: '#38bdf8', iconBg: 'rgba(56,189,248,0.12)', iconColor: '#38bdf8', roleColor: '#7dd3fc', description: 'Static Planning Fallacy Guard', step: '02' },
  analyst: { accent: '#a78bfa', iconBg: 'rgba(167,139,250,0.12)', iconColor: '#a78bfa', roleColor: '#c4b5fd', description: 'Execution + State Delta Log', step: '03' },
  critic: { accent: '#f87171', iconBg: 'rgba(248,113,113,0.12)', iconColor: '#f87171', roleColor: '#fca5a5', description: 'Independent Audit (PEV Triad)', step: '04' },
  synthesizer: { accent: '#34d399', iconBg: 'rgba(52,211,153,0.12)', iconColor: '#34d399', roleColor: '#6ee7b7', description: 'Final Consensus Output', step: '05' },
}

const STATUS_COLOR = { idle: '#475569', processing: '#38bdf8', complete: '#22c55e' }
const STATUS_LABEL = { idle: 'Idle', processing: 'Active', complete: 'Verified' }

const AgentNode = ({ data }) => {
  const cfg = AGENT_CONFIG[data.id] || AGENT_CONFIG.librarian
  const status = data.status || 'idle'
  const isProcessing = status === 'processing'
  const isComplete = status === 'complete'

  return (
    <div className={`agent-node ${isProcessing ? 'processing' : ''}`} style={{
      width: 300, background: 'rgba(15,23,42,0.95)', border: `1px solid ${isProcessing ? cfg.accent : 'rgba(51,65,85,0.6)'}`,
      borderLeft: `4px solid ${cfg.accent}`, borderRadius: 14, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 14,
      backdropFilter: 'blur(12px)', transition: 'all 0.3s ease'
    }}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="agent-icon" style={{ background: cfg.iconBg, color: cfg.iconColor, width: 44, height: 44, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {data.icon}
        {isProcessing && <motion.div className="pulse-ring" style={{ border: `2px solid ${cfg.accent}` }} animate={{ opacity: [0, 1, 0], scale: [0.9, 1.1, 0.9] }} transition={{ duration: 1.5, repeat: Infinity }} />}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 9, fontWeight: 800, color: cfg.roleColor, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{data.role}</div>
        <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>{data.label}</div>
        <div style={{ fontSize: 10, color: '#64748b' }}>{cfg.description}</div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLOR[status], boxShadow: isProcessing ? `0 0 10px ${STATUS_COLOR[status]}` : 'none' }} />
        <span style={{ fontSize: 8, color: STATUS_COLOR[status], fontWeight: 800, textTransform: 'uppercase' }}>{STATUS_LABEL[status]}</span>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  )
}

const FlowEdge = ({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, style }) => {
  const [edgePath, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition })
  return (
    <>
      <BaseEdge id={id} path={edgePath} style={style} />
      {data?.label && (
        <EdgeLabelRenderer>
          <div style={{ position: 'absolute', transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`, background: 'rgba(15,23,42,0.9)', border: '1px solid rgba(51,65,85,0.4)', borderRadius: 20, padding: '2px 8px', fontSize: 9, color: '#94a3b8', backdropFilter: 'blur(4px)', pointerEvents: 'none' }}>
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { agent: AgentNode }
const edgeTypes = { flow: FlowEdge }

const initialNodes = [
  { id: 'librarian', type: 'agent', position: { x: 60, y: 0 }, data: { id: 'librarian', label: 'Librarian', role: 'Context Layer', icon: <Database size={18} /> } },
  { id: 'architect', type: 'agent', position: { x: 60, y: 150 }, data: { id: 'architect', label: 'Architect', role: 'Planner node', icon: <Layout size={18} /> } },
  { id: 'analyst', type: 'agent', position: { x: 60, y: 300 }, data: { id: 'analyst', label: 'Analyst', role: 'Execution node', icon: <Code size={18} /> } },
  { id: 'critic', type: 'agent', position: { x: 60, y: 450 }, data: { id: 'critic', label: 'Critic', role: 'Validator node', icon: <ShieldCheck size={18} /> } },
  { id: 'synthesizer', type: 'agent', position: { x: 60, y: 600 }, data: { id: 'synthesizer', label: 'Synthesizer', role: 'Consensus core', icon: <MessageSquare size={18} /> } },
]

const initialEdges = [
  { id: 'e1', source: 'librarian', target: 'architect', type: 'flow', animated: true, style: { stroke: '#334155' }, data: { label: 'context' } },
  { id: 'e2', source: 'architect', target: 'analyst', type: 'flow', animated: true, style: { stroke: '#334155' }, data: { label: 'plan' } },
  { id: 'e3', source: 'analyst', target: 'critic', type: 'flow', animated: true, style: { stroke: '#334155' }, data: { label: 'output' } },
  { id: 'e4', source: 'critic', target: 'synthesizer', type: 'flow', animated: true, style: { stroke: '#22c55e' }, data: { label: 'pass' } },
  { id: 'e5', source: 'critic', target: 'architect', type: 'flow', animated: true, style: { stroke: '#ef4444', strokeDasharray: '4' }, data: { label: 'refine' } },
]

function App() {
  const { query, setQuery, pipeline, updateStage, resetPipeline, setComplete, setProcessing, auth } = useStore()
  const [terminalLines, setTerminalLines] = useState([])
  const [showReport, setShowReport] = useState(false)
  const [finalReportData, setFinalReportData] = useState(null)
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef(null)
  const wsRef = useRef(null)
  const terminalEndRef = useRef(null)

  // 1. ADD LINE UTILITY (MOVED TO TOP TO PREVENT INITIALIZATION ERROR)
  const addLine = useCallback((content, type = 'system') => {
    setTerminalLines(prev => [...prev.slice(-40), { id: Math.random().toString(36), content, type, timestamp: Date.now() }])
  }, [])

  // 2. VOICE INITIALIZATION
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = false
      recognitionRef.current.interimResults = false
      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript
        setQuery(transcript)
        setIsListening(false)
        addLine(`Voice detected: "${transcript}"`, 'system')
      }
      recognitionRef.current.onend = () => setIsListening(false)
    }
  }, [setQuery, addLine])

  const toggleVoice = () => {
    if (isListening) {
      recognitionRef.current?.stop()
    } else {
      setIsListening(true)
      recognitionRef.current?.start()
    }
  }

  // 3. PIPELINE SYNC
  useEffect(() => {
    setNodes(nds => nds.map(node => ({
      ...node,
      data: { ...node.data, status: pipeline.stages.find(s => s.id === node.id)?.status || 'idle' }
    })))
  }, [pipeline.stages])

  // 4. SOCKET LOGIC
  const handleSocketMessage = useCallback((event) => {
    const data = JSON.parse(event.data)
    if (data.event === 'stage_start') {
      updateStage(data.stage, 'processing')
      addLine(`Node ${data.stage.toUpperCase()}: Initiating sequence...`)
    } else if (data.event === 'stage_complete') {
      updateStage(data.stage, 'complete')
      addLine(`Node ${data.stage.toUpperCase()}: Task verified.`)
    } else if (data.event === 'error') {
      addLine(`System Alert: ${data.error}`, 'error')
      if (data.error.includes('Session Expired')) {
        auth.logout()
      }
    } else if (data.event === 'system') {
      addLine(`Spicy Link: ${data.status}`, 'system')
    } else if (data.event === 'complete') {
      setComplete(data.final_answer, data.latency_ms)
      setFinalReportData(data)
      setShowReport(true)
      addLine("Swarm Consensus Achieved.")
    }
  }, [addLine, updateStage, setComplete])

  const handleSubmit = (e) => {
    if (e) e.preventDefault()
    if (!query || pipeline.isProcessing) return
    resetPipeline()
    setTerminalLines([])
    
    addLine("Establishing Spicy Link (Port 8005)...", "system")
    const socket = new WebSocket('ws://localhost:8005/ws/pipeline')
    wsRef.current = socket
    
    socket.onmessage = handleSocketMessage
    socket.onerror = (err) => {
      addLine("Socket Error: Backend unreachable. Check port 8005.", "error")
      setProcessing(false) 
    }
    
    socket.onopen = () => {
      socket.send(JSON.stringify({ token: auth.token }))
      socket.send(JSON.stringify({ query }))
    }
    
    socket.onclose = () => {
      setProcessing(false)
    }
  }

  if (!auth.isAuthenticated) return <LoginView />

  return (
    <div className="app-workspace v4-sharp">
      <header className="terminal-header glass">
        <div className="flex items-center gap-4">
          <Network className="text-emerald-400" size={28} />
          <div>
            <h1 className="text-xl font-black italic text-white">SPICY SWARM <span className="text-xs bg-emerald-500 text-black px-1 rounded ml-1">4.0 SHARP</span></h1>
            <div className="text-[9px] uppercase tracking-widest text-slate-500 font-bold">PEV Triad Architecture · Active Audit Loop</div>
          </div>
        </div>
        <div className="flex gap-6 items-center">
            <div className="text-right">
                <div className="text-[10px] text-slate-500 font-bold uppercase">System Latency</div>
                <div className="text-xl font-black text-emerald-400">{pipeline.latency.toFixed(0)}ms</div>
            </div>
            <button onClick={() => auth.logout()} className="p-2 hover:bg-red-500/20 rounded-lg text-slate-500 hover:text-red-500 transition-all"><Zap size={20} /></button>
        </div>
      </header>

      <main className="terminal-container">
        <div className="command-center">
          <div className="terminal-window glass mono text-[11px]">
            {terminalLines.map(l => (
              <div key={l.id} className="mb-1">
                <span className="opacity-30 mr-2">[{new Date(l.timestamp).toLocaleTimeString()}]</span>
                <span className={l.type === 'agent' ? 'text-emerald-400' : 'text-slate-300'}>{l.content}</span>
              </div>
            ))}
            <div ref={terminalEndRef} />
          </div>
          <form onSubmit={handleSubmit} className="query-dock glass">
            <button type="button" onClick={toggleVoice} className={`voice-btn ${isListening ? 'active' : ''} p-2 mr-2 rounded-xl hover:bg-white/10 transition-all text-slate-400`}>
              {isListening ? <MicOff size={20} className="text-red-500 animate-pulse" /> : <Mic size={20} />}
            </button>
            <input type="text" value={query} onChange={e => setQuery(e.target.value)} placeholder="Speak or type goal..." className="query-input mono flex-1" />
            <button type="submit" disabled={pipeline.isProcessing} className="launch-btn bg-emerald-500 text-black px-6 py-2 rounded-xl font-black disabled:opacity-50">LAUNCH</button>
          </form>
        </div>

        <div className="swarm-graph-container glass">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} fitView proOptions={{ hideAttribution: true }}>
            <Background color="#0f172a" gap={20} />
          </ReactFlow>
        </div>
      </main>

      <AnimatePresence>
        {showReport && finalReportData && <FinalReport data={finalReportData} onClose={() => setShowReport(false)} />}
      </AnimatePresence>
    </div>
  )
}

const FinalReport = ({ data, onClose }) => {
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [selectedStageFilter, setSelectedStageFilter] = useState('ALL');
  const [copiedIndex, setCopiedIndex] = useState(null);

  return (
    <>
      <ReportViewer
        data={data}
        onClose={onClose}
        onOpenAuditTrail={() => setShowAuditModal(true)}
      />

      {/* DEDICATED TECHNICAL AUDIT TRAIL WINDOW */}
      <AnimatePresence>
        {showAuditModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="report-overlay"
            style={{ zIndex: 120 }}
            onClick={() => setShowAuditModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 15 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 15 }}
              className="report-modal glass max-w-4xl w-full border border-blue-500/30 shadow-2xl shadow-blue-500/10"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex justify-between items-center mb-6 pb-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-blue-500/20 rounded-xl text-blue-400 border border-blue-500/30">
                    <Database size={22} />
                  </div>
                  <div>
                    <h2 className="text-xl font-black italic uppercase text-white tracking-tight flex items-center gap-2">
                      Technical Audit Trail
                      <span className="text-[10px] font-mono font-bold bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">
                        {(data.logs || []).length} STAGES
                      </span>
                    </h2>
                    <div className="text-[9px] uppercase font-bold text-slate-400 tracking-[0.25em]">
                      Multi-Agent System Telemetry & Execution Traces
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const text = JSON.stringify(data.logs || [], null, 2);
                      navigator.clipboard.writeText(text);
                      setCopiedIndex('all');
                      setTimeout(() => setCopiedIndex(null), 2000);
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-[10px] font-bold text-slate-300 hover:text-white uppercase tracking-wider transition-all cursor-pointer"
                  >
                    <CheckCircle2 size={12} className={copiedIndex === 'all' ? 'text-emerald-400' : 'text-slate-400'} />
                    {copiedIndex === 'all' ? 'Copied' : 'Copy All JSON'}
                  </button>
                  <button
                    onClick={() => setShowAuditModal(false)}
                    className="p-2 hover:bg-white/10 rounded-full text-slate-400 hover:text-white transition-colors cursor-pointer"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* Quick Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl">
                  <div className="text-[9px] uppercase text-slate-400 font-bold mb-0.5">Total Cycles</div>
                  <div className="text-sm font-black text-white mono">{data.cycle_count || 1} Loop(s)</div>
                </div>
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl">
                  <div className="text-[9px] uppercase text-slate-400 font-bold mb-0.5">Execution Latency</div>
                  <div className="text-sm font-black text-emerald-400 mono">{data.latency_ms?.toFixed(0) || 0}ms</div>
                </div>
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl">
                  <div className="text-[9px] uppercase text-slate-400 font-bold mb-0.5">Consensus Status</div>
                  <div className="text-sm font-black text-blue-400 mono">{data.status === 'complete' ? 'VERIFIED' : 'ACTIVE'}</div>
                </div>
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl">
                  <div className="text-[9px] uppercase text-slate-400 font-bold mb-0.5">Logged Entries</div>
                  <div className="text-sm font-black text-amber-400 mono">{(data.logs || []).length} Recorded</div>
                </div>
              </div>

              {/* Filter Tabs */}
              <div className="flex flex-wrap gap-2 mb-4">
                {['ALL', 'LIBRARIAN', 'ARCHITECT', 'ANALYST', 'CRITIC', 'SYNTHESIZER'].map(st => (
                  <button
                    key={st}
                    onClick={() => setSelectedStageFilter(st)}
                    className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase mono tracking-wider transition-all cursor-pointer ${
                      selectedStageFilter === st
                        ? 'bg-blue-500 text-white shadow-md shadow-blue-500/20'
                        : 'bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200 border border-white/5'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>

              {/* Logs Stream */}
              <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-2 custom-scroll">
                {(data.logs || [])
                  .filter(l => selectedStageFilter === 'ALL' || l.stage?.toUpperCase() === selectedStageFilter)
                  .map((logItem, idx) => {
                    const stageColor = {
                      librarian: 'border-purple-500/30 text-purple-400 bg-purple-500/10',
                      architect: 'border-amber-500/30 text-amber-400 bg-amber-500/10',
                      analyst: 'border-cyan-500/30 text-cyan-400 bg-cyan-500/10',
                      critic: 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10',
                      synthesizer: 'border-blue-500/30 text-blue-400 bg-blue-500/10'
                    }[logItem.stage?.toLowerCase()] || 'border-slate-500/30 text-slate-400 bg-slate-500/10';

                    return (
                      <div
                        key={idx}
                        className="p-4 rounded-xl bg-black/40 border border-white/10 hover:border-blue-500/30 transition-all"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border ${stageColor}`}>
                              {logItem.stage}
                            </span>
                            <span className="text-[10px] text-slate-500 mono">Entry #{idx + 1}</span>
                          </div>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(JSON.stringify(logItem.output, null, 2));
                              setCopiedIndex(idx);
                              setTimeout(() => setCopiedIndex(null), 2000);
                            }}
                            className="text-[10px] text-slate-400 hover:text-slate-200 flex items-center gap-1 cursor-pointer"
                          >
                            <Copy size={11} />
                            {copiedIndex === idx ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                        <pre className="p-3 bg-black/60 rounded-lg text-[11px] font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed border border-white/5 max-h-48 custom-scroll">
                          {typeof logItem.output === 'object'
                            ? JSON.stringify(logItem.output, null, 2)
                            : String(logItem.output)}
                        </pre>
                      </div>
                    );
                  })}

                {(data.logs || []).length === 0 && (
                  <div className="text-center py-12 text-slate-500 italic text-sm">
                    No audit logs recorded for this execution run.
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="mt-6 pt-4 border-t border-white/10 flex justify-end">
                <button
                  onClick={() => setShowAuditModal(false)}
                  className="px-5 py-2 bg-white/10 hover:bg-white/15 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                >
                  Close Audit Trail
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default App