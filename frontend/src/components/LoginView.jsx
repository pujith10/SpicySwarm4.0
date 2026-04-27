import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Shield, Key, User, Activity, Lock, Eye, EyeOff, Network, Globe } from 'lucide-react'
import axios from 'axios'
import { useStore } from '../store/useStore'

const LoginView = () => {
  const [isLogin, setIsLogin] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [formData, setFormData] = useState({ username: '', password: '', secret: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  const { auth } = useStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    
    try {
      if (isLogin) {
        const res = await axios.post('http://localhost:8005/api/auth/login', {
          username: formData.username,
          password: formData.password
        })
        auth.login(formData.username, res.data.access_token)
      } else {
        await axios.post('http://localhost:8005/api/auth/register', {
          username: formData.username,
          password: formData.password,
          secret: formData.secret
        })
        setIsLogin(true)
        alert('Identity Registered. Proceed to Access.')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Handshake Denied: Invalid Credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#020617] overflow-hidden font-sans">
      {/* Background Decor */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-0 right-0 w-96 h-96 bg-terminal-blue rounded-full blur-[120px]" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-indigo-500 rounded-full blur-[120px]" />
      </div>

      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="w-full max-w-lg p-8 glass-extreme rounded-[32px] border border-white/10 relative z-10 shadow-2xl"
      >
        <header className="text-center mb-10">
          <div className="inline-flex p-4 rounded-2xl bg-terminal-blue/10 border border-terminal-blue/20 mb-6">
            <Shield className="text-terminal-blue" size={32} />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white uppercase italic">
            Spicy Swarm <span className="text-terminal-blue">3.0</span>
          </h1>
          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em] mt-2">
            {isLogin ? 'Authorization Required' : 'New Identity Registration'}
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-3">
            <div className="relative">
              <User className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
              <input 
                type="text"
                placeholder="Username"
                className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white focus:border-terminal-blue/50 outline-none transition-all placeholder:text-slate-700 font-bold"
                value={formData.username}
                onChange={e => setFormData({...formData, username: e.target.value})}
                required
              />
            </div>

            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
              <input 
                type={showPassword ? 'text' : 'password'}
                placeholder="Secure Key"
                className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-12 text-white focus:border-terminal-blue/50 outline-none transition-all placeholder:text-slate-700 font-bold"
                value={formData.password}
                onChange={e => setFormData({...formData, password: e.target.value})}
                required
              />
              <button 
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-terminal-blue transition-colors"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>

            {!isLogin && (
              <div className="relative">
                <Globe className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                <input 
                  type="password"
                  placeholder="Master Signup Secret"
                  className="w-full bg-emerald-500/5 border border-emerald-500/20 rounded-2xl py-4 pl-12 pr-4 text-emerald-400 focus:border-emerald-500/50 outline-none transition-all placeholder:text-emerald-900/40 font-bold"
                  value={formData.secret}
                  onChange={e => setFormData({...formData, secret: e.target.value})}
                  required
                />
              </div>
            )}
          </div>

          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2">
              <Activity size={14} />
              {error}
            </motion.div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full py-4 bg-terminal-blue hover:bg-terminal-blue/90 text-[#020617] font-black uppercase tracking-widest rounded-xl transition-all disabled:opacity-50"
          >
            {loading ? 'Processing...' : (isLogin ? 'Access System' : 'Create Identity')}
          </button>
        </form>

        <footer className="mt-8 text-center">
          <button 
            onClick={() => setIsLogin(!isLogin)}
            className="text-slate-500 text-[10px] font-black uppercase tracking-widest hover:text-terminal-blue transition-colors"
          >
            {isLogin ? "Need Authorization? Click Here" : "Verified Identity? Access Portal"}
          </button>
        </footer>
      </motion.div>
    </div>
  )
}

export default LoginView

const RefreshCw = ({ className }) => (
  <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.85.83 6.72 2.73L21 8"/><path d="M21 3v5h-5"/></svg>
)


