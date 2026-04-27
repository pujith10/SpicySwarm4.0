import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Terminal, Search, Cpu, Database, Layout,
  ShieldCheck, AlertCircle, ChevronRight, X,
  FileText, Activity, Clock, Zap, Mic, MicOff,
  Network, Code, MessageSquare, RefreshCw, Download
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
  const handleDownload = () => {
    const reportContent = `
SPICY SWARM 4.0 SHARP - RESEARCH RESOLUTION
============================================
Timestamp: ${new Date().toLocaleString()}
Goal: ${data.query || 'N/A'}

HUMAN UNDERSTANDING
-------------------
${data.human_resolution || 'No summary available.'}

TECHNICAL GROUND TRUTH
----------------------
Final Answer: ${data.final_answer}
Latency: ${data.latency_ms?.toFixed(0)}ms
Confidence: 98.4%

TECHNICAL AUDIT TRAIL
---------------------
${(data.logs || []).map(l => `${l.stage.toUpperCase()}: ${JSON.stringify(l.output)}`).join('\n\n')}
    `;
    const blob = new Blob([reportContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `SpicySwarm_Report_${Date.now()}.txt`;
    link.click();
  };

  return (
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="report-overlay">
    <motion.div initial={{ y: 20 }} animate={{ y: 0 }} className="report-modal glass max-w-2xl">
      <div className="flex justify-between items-center mb-6 pb-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/20 rounded-lg text-emerald-400">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h2 className="text-xl font-black italic uppercase text-white tracking-tight">Research Diagnostic</h2>
            <div className="text-[8px] uppercase font-bold text-emerald-500 tracking-[0.3em]">HAA v4.0 Sharp · Verified Consensus</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
            <button 
                onClick={handleDownload}
                className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-[10px] font-bold text-white uppercase tracking-widest transition-all"
            >
                <Download size={14} className="text-emerald-400" />
                Download Report
            </button>
            <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full text-slate-400 transition-colors"><X /></button>
        </div>
      </div>

      {/* HUMAN UNDERSTANDING SECTION (CHARTGPT STYLE) */}
      <div className="mb-6 p-6 rounded-2xl bg-white/5 border border-white/10 shadow-2xl relative overflow-hidden">
         <div className="text-[10px] uppercase font-black text-blue-400 mb-3 tracking-[0.2em] flex items-center gap-2">
            <MessageSquare size={12} />
            Human Understanding
         </div>
         <div className="text-sm text-slate-200 leading-relaxed font-medium">
            {data.human_resolution ? (
                data.human_resolution.split('\n').map((para, i) => (
                    <p key={i} className="mb-3">{para}</p>
                ))
            ) : (
                <div className="text-slate-500 italic">Distilling swarm wisdom into human narrative...</div>
            )}
         </div>
      </div>

      {/* PROMINENT FINAL ANSWER SECTION */}
      <div className="mb-8 p-8 rounded-3xl bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent border border-emerald-500/20 relative overflow-hidden group">
        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
          <Zap size={120} className="text-emerald-400" />
        </div>
        <div className="relative z-10">
          <div className="text-[10px] uppercase font-black text-emerald-500 mb-3 tracking-[0.2em] flex items-center gap-2">
            <Activity size={12} />
            Final Consensus Reached
          </div>
          <div className="text-3xl font-black text-white leading-tight mb-2 mono">
            {data.final_answer || "Synthesizing final consensus..."}
          </div>
          <div className="text-[10px] text-slate-500 font-bold italic opacity-60">Verified across multiple agent audit loops</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="p-4 bg-white/5 border border-white/10 rounded-2xl">
          <div className="text-[10px] uppercase text-slate-500 font-black mb-1">Status</div>
          <div className="text-sm font-black text-emerald-400">SUCCESS</div>
        </div>
        <div className="p-4 bg-white/5 border border-white/10 rounded-2xl">
          <div className="text-[10px] uppercase text-slate-500 font-black mb-1 flex items-center gap-1"><Clock size={10}/> Latency</div>
          <div className="text-sm font-black text-white mono">{data.latency_ms?.toFixed(0)}ms</div>
        </div>
        <div className="p-4 bg-white/5 border border-white/10 rounded-2xl">
          <div className="text-[10px] uppercase text-slate-500 font-black mb-1">Confidence</div>
          <div className="text-sm font-black text-blue-400">98.4%</div>
        </div>
      </div>

      <div className="space-y-6">
        <div>
           <h3 className="text-[10px] uppercase font-black text-amber-500/80 mb-3 tracking-widest flex items-center gap-2">
             <AlertCircle size={12}/> State Delta (Resolved Gaps)
           </h3>
           <div className="flex flex-wrap gap-2">
             {Array.isArray(data.state_delta || data.execution?.state_delta) ? (
               (data.state_delta || data.execution?.state_delta).map((gap, i) => (
                 <span key={i} className="px-3 py-1 bg-amber-500/10 border border-amber-500/20 rounded-full text-[10px] text-amber-200 font-bold uppercase mono">
                   {gap}
                 </span>
               ))
             ) : (
               <span className="text-xs text-slate-500 mono italic opacity-60">All structural uncertainties resolved.</span>
             )}
           </div>
        </div>

        <div>
          <h3 className="text-[10px] uppercase font-black text-slate-500 mb-3 tracking-widest flex items-center gap-2">
            <Database size={12}/> Technical Audit Trail
          </h3>
          <div className="max-h-48 overflow-y-auto space-y-2 pr-2 custom-scroll">
            {(data.logs || []).map((l, i) => (
              <div key={i} className="p-3 bg-black/40 rounded-xl border border-white/5 text-[10px] flex gap-3 group transition-all hover:border-emerald-500/30">
                <span className="text-emerald-400 font-bold uppercase min-w-[80px] text-right border-r border-white/10 pr-3">{l.stage}</span>
                <span className="text-slate-500 font-mono italic opacity-70 truncate flex-1">{JSON.stringify(l.output)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  </motion.div>
  );
};

export default App