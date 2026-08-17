import { useState, useEffect, useRef } from 'react'
import './index.css'

function App() {
  const [messages, setMessages] = useState([{ sender: 'sys', text: 'System Initialized. JARVIS Online.' }])
  const [status, setStatus] = useState('ONLINE') // ONLINE, LISTENING, THINKING
  const [inputText, setInputText] = useState('')
  const [cpuUsage, setCpuUsage] = useState(24)
  const [ramUsage, setRamUsage] = useState(48)
  const [netSpeed, setNetSpeed] = useState(13)
  const [isMicActive, setIsMicActive] = useState(true)
  const [wsInstance, setWsInstance] = useState(null)
  // Onay bekleyen komutlar id bazlı bir kuyrukta tutulur — tek bir "aktif"
  // onay state'i, aynı anda birden fazla confirm_request geldiğinde birini
  // sessizce ezerdi (bkz. Faz 2 tasarım notları).
  const [pendingConfirms, setPendingConfirms] = useState([])
  const [currentTime, setCurrentTime] = useState('')
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Clock Update
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleString('en-US', { 
        weekday: 'short', month: 'short', day: 'numeric', 
        hour: '2-digit', minute:'2-digit', second:'2-digit'
      }));
    }
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fake system monitor jitter for dynamic feel
  useEffect(() => {
    const interval = setInterval(() => {
      setCpuUsage(prev => Math.max(10, Math.min(95, prev + (Math.random() * 14 - 7))))
      setRamUsage(prev => Math.max(30, Math.min(85, prev + (Math.random() * 6 - 3))))
      setNetSpeed(prev => Math.max(1, Math.min(100, prev + (Math.random() * 40 - 20))))
    }, 1500)
    return () => clearInterval(interval)
  }, [])

  // Audio Playback
  const speak = (text, audioUrl) => {
    if (audioUrl) {
      const audio = new Audio(audioUrl);
      audio.play();
    } else if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(utterance);
    }
  }

  // Connect to Python Brain via WebSocket
  useEffect(() => {
    let ws;
    let reconnectInterval;

    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onopen = () => {
        setMessages(prev => [...prev, { sender: 'sys', text: 'Neural Link Established. Microphone active.' }])
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'status') {
          setStatus(data.value);
        } else if (data.type === 'log') {
          let text = data.text;
          if (text.startsWith('JRV: ')) text = text.replace('JRV: ', '');
          setMessages(prev => [...prev, { sender: data.sender, text: text }]);
          if (data.speak) {
            speak(text, data.audioUrl);
          }
        } else if (data.type === 'confirm_request') {
          setPendingConfirms(prev => [...prev, { id: data.id, command: data.command }]);
        }
      };

      ws.onclose = () => {
        setMessages(prev => [...prev, { sender: 'err', text: 'Connection Lost. Attempting to reconnect...' }])
        reconnectInterval = setTimeout(connect, 3000);
      };
      
      setWsInstance(ws);
    };

    connect();

    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectInterval);
    }
  }, []);

  const toggleMic = () => {
    const newState = !isMicActive;
    setIsMicActive(newState);
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ action: "toggle_mic", state: newState }));
    }
  }

  const resolveConfirm = (id, approved) => {
    setPendingConfirms(prev => prev.filter(c => c.id !== id));
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ action: approved ? "approve_command" : "deny_command", id }));
    }
  }

  const interrupt = () => {
    window.speechSynthesis.cancel();
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ action: "interrupt" }));
    }
  }

  const sendMessage = async (text) => {
    if (!text.trim()) return
    setStatus('THINKING')
    setMessages(prev => [...prev, { sender: 'user', text: text }])
    
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      })
      const data = await response.json()
      const reply = data.response || data.error
      setMessages(prev => [...prev, { sender: 'sys', text: reply }])
      speak(reply, data.audioUrl)
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'err', text: "Failed to reach intelligence core." }])
    }
    setStatus('ONLINE')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      sendMessage(inputText)
      setInputText('')
    }
  }

  return (
    <>
      {/* CONFIRM QUEUE - onay bekleyen komutlar, id bazlı, birden fazla aynı anda görünebilir.
          .dashboard'un dışında render edilir çünkü .dashboard'un overflow:hidden'i
          içerideki position:absolute/fixed elemanları kırpar. */}
      {pendingConfirms.length > 0 && (
        <div className="confirm-queue">
          {pendingConfirms.map(c => (
            <div key={c.id} className="confirm-card">
              <div className="confirm-header">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                Onay Gerekli
              </div>
              <code className="confirm-command">{c.command}</code>
              <div className="confirm-actions">
                <button className="btn-confirm approve" onClick={() => resolveConfirm(c.id, true)}>Onayla</button>
                <button className="btn-confirm deny" onClick={() => resolveConfirm(c.id, false)}>Reddet</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="dashboard">
      {/* TOP BAR */}
      <div className="top-bar">
        <div className="brand">JARVIS // NEXUS CORE</div>
        <div className="time-widget">{currentTime}</div>
      </div>

      <div className="main-content">
        
        {/* LEFT PANEL - STATS */}
        <div className="panel left-panel">
          <div className="panel-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            System Telemetry
          </div>
          
          <div className="stat-card">
            <div className="stat-header">
              <span style={{color: 'var(--text-muted)'}}>Neural CPU</span>
              <span className="stat-value" style={{color: 'var(--accent-primary)'}}>{cpuUsage.toFixed(1)}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{width: `${cpuUsage}%`, backgroundColor: 'var(--accent-primary)'}}></div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-header">
              <span style={{color: 'var(--text-muted)'}}>Memory Core</span>
              <span className="stat-value" style={{color: 'var(--accent-secondary)'}}>{ramUsage.toFixed(1)}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{width: `${ramUsage}%`, backgroundColor: 'var(--accent-secondary)'}}></div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-header">
              <span style={{color: 'var(--text-muted)'}}>Network I/O</span>
              <span className="stat-value" style={{color: 'var(--success)'}}>{netSpeed.toFixed(0)} MB/s</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{width: `${Math.min(100, netSpeed * 2)}%`, backgroundColor: 'var(--success)'}}></div>
            </div>
          </div>
          
          <div style={{marginTop: 'auto'}}>
            <div className="panel-header" style={{marginTop: '30px'}}>Active Modules</div>
            <div style={{display: 'flex', flexDirection: 'column', gap: '10px'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem'}}>
                <span style={{color: 'var(--text-muted)'}}>Speech Synthesis</span>
                <span style={{color: 'var(--success)'}}>ONLINE</span>
              </div>
              <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem'}}>
                <span style={{color: 'var(--text-muted)'}}>OpenJarvis Core</span>
                <span style={{color: 'var(--success)'}}>INTEGRATED</span>
              </div>
              <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem'}}>
                <span style={{color: 'var(--text-muted)'}}>Local Tools</span>
                <span style={{color: 'var(--success)'}}>READY</span>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER PANEL - ORB */}
        <div className="panel center-panel">
          <div className="ai-core-container">
            <div className="ring ring-1"></div>
            <div className="ring ring-2"></div>
            <div className="ring ring-3"></div>
            <div className={`orb ${status}`}></div>
          </div>
          <div className={`status-text ${status}`}>{status}</div>
        </div>

        {/* RIGHT PANEL - CHAT & INPUT */}
        <div className="panel right-panel">
          <div className="panel-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            Communication Log
          </div>
          
          <div className="chat-container">
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.sender}`}>
                {msg.text}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-wrapper">
            <input 
              type="text" 
              placeholder="Ask JARVIS a question or give a command..." 
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button className="btn-send" onClick={() => {sendMessage(inputText); setInputText('')}}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </div>
          
          <div className="controls">
            <button className={`btn-control ${isMicActive ? 'active-mic' : ''}`} onClick={toggleMic}>
              {isMicActive ? (
                 <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg> Mic Active</>
              ) : (
                <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="1" y1="1" x2="23" y2="23"></line><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg> Mic Muted</>
              )}
            </button>
            <button className="btn-control danger" onClick={interrupt}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg> Stop (ESC)
            </button>
          </div>
        </div>

      </div>
      </div>
    </>
  )
}

export default App
