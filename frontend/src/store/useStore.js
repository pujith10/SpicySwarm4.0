import { create } from 'zustand'

export const useStore = create((set) => ({
  query: '',
  setQuery: (query) => set({ query }),
  
  pipeline: {
    stages: [
      { id: 'librarian', name: 'Librarian (RAG)', status: 'idle', output: null },
      { id: 'architect', name: 'Architect (Plan)', status: 'idle', output: null },
      { id: 'analyst', name: 'Analyst (Tools)', status: 'idle', output: null },
      { id: 'critic', name: 'Critic (Review)', status: 'idle', output: null },
      { id: 'synthesizer', name: 'Synthesizer', status: 'idle', output: null }
    ],
    results: null,
    latency: 0,
    isProcessing: false
  },
  
  updateStage: (stageId, status, output) => set((state) => ({
    pipeline: {
      ...state.pipeline,
      stages: state.pipeline.stages.map(s => 
        s.id === stageId ? { ...s, status, output } : s
      )
    }
  })),
  
  resetPipeline: () => set((state) => ({
    pipeline: {
      ...state.pipeline,
      stages: state.pipeline.stages.map(s => ({ ...s, status: 'idle', output: null })),
      results: null,
      latency: 0,
      isProcessing: true
    }
  })),
  
  setProcessing: (isProcessing) => set((state) => ({
    pipeline: { ...state.pipeline, isProcessing }
  })),
  
  setComplete: (answer, latency) => set((state) => ({
    pipeline: { ...state.pipeline, isProcessing: false, finalAnswer: answer, latency }
  })),
  
  // Auth State
  auth: {
    user: null,
    token: localStorage.getItem('swarm_token'),
    isAuthenticated: !!localStorage.getItem('swarm_token'),
    setToken: (token) => {
      localStorage.setItem('swarm_token', token)
      set(state => ({ auth: { ...state.auth, token, isAuthenticated: !!token } }))
    },
    login: (user, token) => {
      localStorage.setItem('swarm_token', token)
      set(state => ({ auth: { ...state.auth, user, token, isAuthenticated: true } }))
    },
    logout: () => {
      localStorage.removeItem('swarm_token')
      set(state => ({ auth: { ...state.auth, user: null, token: null, isAuthenticated: false } }))
    }
  }
}))
