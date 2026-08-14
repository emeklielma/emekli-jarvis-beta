import { useState, useEffect, useRef } from 'react'
import './index.css'

const themes = [
  { name: 'Cyan', color: '#00e5ff', rgb: '0, 229, 255' },
  { name: 'Red', color: '#ff2a2a', rgb: '255, 42, 42' },
  { name: 'Gold', color: '#ffaa00', rgb: '255, 170, 0' },
  { name: 'Green', color: '#00ff88', rgb: '0, 255, 136' },
  { name: 'Purple', color: '#b829ff', rgb: '184, 41, 255' },
];

function App() {
  const [currentTheme, setCurrentTheme] = useState(themes[0])
  const [messages, setMessages] = useState([{ sender: 'sys', text: 'SYS: JARVIS UI online.' }])
  const [status, setStatus] = useState('ONLINE') // ONLINE, LISTENING, THINKING
  const [inputText, setInputText] = useState('')
  const [cpuUsage, setCpuUsage] = useState(24)
  const [ramUsage, setRamUsage] = useState(48)
  const [netSpeed, setNetSpeed] = useState(13)
  const [isMicActive, setIsMicActive] = useState(true)
  const [wsInstance, setWsInstance] = useState(null)
  const messagesEndRef = useRef(null)
  const chatContainerRef = useRef(null)
  const currentAudioRef = useRef(null)

  useEffect(() => {
    document.documentElement.style.setProperty('--theme-color', currentTheme.color)
    document.documentElement.style.setProperty('--theme-color-rgb', currentTheme.rgb)
  }, [currentTheme])

  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      const isNearBottom = scrollHeight - scrollTop <= clientHeight + 100;
      if (isNearBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // F11 Fullscreen support for pywebview
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      if (e.key === 'F11') {
        if (window.pywebview) {
          window.pywebview.api.toggle_fullscreen();
        }
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // Fake system monitor jitter for the techy UI look!
  useEffect(() => {
    const interval = setInterval(() => {
      setCpuUsage(prev => Math.max(10, Math.min(90, prev + (Math.random() * 10 - 5))))
      setRamUsage(prev => Math.max(30, Math.min(80, prev + (Math.random() * 4 - 2))))
      setNetSpeed(prev => Math.max(1, Math.min(50, prev + (Math.random() * 20 - 10))))
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Lightning-fast Neural Voice playback!
  const speak = (text, audioUrl) => {
    // Stop any currently playing audio
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
    }
    window.speechSynthesis.cancel();

    if (audioUrl) {
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;
      audio.play();
    } else if ('speechSynthesis' in window) {
      // Fallback
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
        setMessages(prev => [...prev, { sender: 'sys', text: 'SYS: Python Brain Connected. Microphone active.' }])
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'action' && data.value === 'minimize') {
          try {
            if (window.pywebview) {
              window.pywebview.api.minimize();
            } else {
              const { ipcRenderer } = window.require('electron');
              ipcRenderer.send('minimize-window');
            }
          } catch (err) {}
        } else if (data.type === 'status') {
          setStatus(data.value);
        } else if (data.type === 'log') {
          setMessages(prev => [...prev, { sender: data.sender, text: data.text }]);
          if (data.speak && data.text.startsWith('JRV: ')) {
            // Strip the "JRV: " prefix before speaking
            speak(data.text.replace('JRV: ', ''), data.audioUrl);
          }
        }
      };

      ws.onclose = () => {
        setMessages(prev => [...prev, { sender: 'err', text: 'ERR: Brain Disconnected. Reconnecting...' }])
        reconnectInterval = setTimeout(connect, 3000);
      };
      
      // Store ws in state so buttons can use it!
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

  const interrupt = () => {
    window.speechSynthesis.cancel();
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
    }
    
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ action: "interrupt" }));
    }
  }

  const sendMessage = async (text) => {
    if (!text.trim()) return
    setStatus('THINKING')
    setMessages(prev => [...prev, { sender: 'user', text: `USR: ${text}` }])
    
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      })
      const data = await response.json()
      const reply = data.response || data.error
      setMessages(prev => [...prev, { sender: 'sys', text: `JRV: ${reply}` }])
      speak(reply, data.audioUrl)
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'err', text: "ERR: Connection to Brain failed." }])
    }
    setStatus('ONLINE')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      sendMessage(inputText)
      setInputText('')
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50)
    }
  }

  return (
    <div className="dashboard">
      <div className="top-bar">
        <div>JARVIS - MARK XLIX</div>
        <div className="top-right">
          <div className="theme-swatches" style={{ display: 'flex', gap: '8px', marginRight: '15px', alignItems: 'center' }}>
            {themes.map(t => (
              <div 
                key={t.name}
                onClick={() => setCurrentTheme(t)}
                style={{
                  width: '14px', height: '14px', borderRadius: '50%', 
                  backgroundColor: t.color, cursor: 'pointer',
                  border: currentTheme.name === t.name ? '2px solid white' : '1px solid transparent',
                  boxShadow: `0 0 8px ${t.color}`
                }}
                title={t.name}
              />
            ))}
          </div>
          <span>_</span>
          <span>□</span>
          <span>X</span>
          <div className="time">20:04:23<br/>Wed 12 Aug 2026</div>
        </div>
      </div>

      <div className="main-content">
        
        {/* LEFT PANEL */}
        <div className="panel left-panel">
          <div className="panel-title">▼ SYS MONITOR</div>
          
          <div className="stat-box">
            <div className="stat-label"><span>CPU</span> <span className="stat-value">{cpuUsage.toFixed(0)}%</span></div>
            <div className="progress-bar"><div className="progress cyan" style={{width: `${cpuUsage}%`}}></div></div>
          </div>

          <div className="stat-box">
            <div className="stat-label"><span>RAM</span> <span className="stat-value" style={{color: '#ffcc00'}}>{ramUsage.toFixed(0)}%</span></div>
            <div className="progress-bar"><div className="progress yellow" style={{width: `${ramUsage}%`}}></div></div>
          </div>

          <div className="stat-box">
            <div className="stat-label"><span>NET</span> <span className="stat-value">{netSpeed.toFixed(0)}KB/s</span></div>
            <div className="progress-bar"><div className="progress cyan" style={{width: `${netSpeed * 2}%`}}></div></div>
          </div>

          <div className="stat-box">
            <div className="stat-label"><span>GPU</span> <span className="stat-value" style={{color: '#ff3366'}}>9%</span></div>
            <div className="progress-bar"><div className="progress red" style={{width: '9%'}}></div></div>
          </div>
          
          <div className="stat-box">
            <div className="stat-label"><span>TMP</span> <span className="stat-value">N/A</span></div>
          </div>

          <div className="sys-info">
            UP 00:21<br/>
            PROC 280<br/>
            OS WIN
          </div>

          <div className="status-badges">
            <div className="badge active">AI CORE<br/>ACTIVE</div>
            <div className="badge active">SEC<br/>CLEARED</div>
            <div className="badge outline">PROTOCOL<br/>XLIX</div>
          </div>
        </div>

        {/* CENTER PANEL */}
        <div className="panel center-panel hud-box">
          <div className="hud-corner top-left"></div>
          <div className="hud-corner top-right"></div>
          <div className="hud-corner bottom-left"></div>
          <div className="hud-corner bottom-right"></div>
          
          <div className="hud-coordinates">
            SYS.LOC: 34.0522° N, 118.2437° W <br/>
            ALT: 1,234 FT | V: 0.00 Mach <br/>
            TARGET: ACQUIRED
          </div>

          <h1 className="jarvis-title">JARVIS</h1>
          <h3 className="jarvis-subtitle">Just A Rather Very Intelligent System</h3>
          
          <div className={`arc-reactor ${status}`}>
            <div className="arc-core"></div>
            <div className="arc-ring ring-outer"></div>
            <div className="arc-ring ring-mid"></div>
            <div className="arc-ring ring-inner"></div>
            <div className="arc-ring ring-ultra-inner"></div>
            
            <div className="radar-status">
              <span className="blink">●</span> {status}
            </div>
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="panel right-panel">
          <div className="panel-title">▼ ACTIVITY LOG</div>
          
          <div className="activity-log" ref={chatContainerRef}>
            {messages.map((msg, i) => (
              <div key={i} className={`log-entry ${msg.sender}`}>
                {msg.text}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="panel-title" style={{marginTop: '20px'}}>▼ FILE UPLOAD</div>
          <div className="file-upload">
            <div className="upload-icon">↑</div>
            Drop file here or Click to Browse<br/>
            <span>Images · Video · Audio · PDF · Docs · Code · Data</span>
          </div>

          <div className="panel-title" style={{marginTop: '20px'}}>▼ COMMAND INPUT</div>
          <div className="input-group">
            <input 
              type="text" 
              placeholder="Type a command or question..." 
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button className="btn-send" onClick={() => {sendMessage(inputText); setInputText('')}}>▶</button>
          </div>
          
          <div className="action-buttons">
            <button className="btn btn-red" onClick={interrupt}>✋ INTERRUPT (ESC)</button>
            <button className={`btn ${isMicActive ? 'btn-green' : 'btn-red'} active`} onClick={toggleMic}>
              {isMicActive ? '🎤 PYTHON MICROPHONE ACTIVE' : '🔇 MICROPHONE MUTED'}
            </button>
          </div>
        </div>

      </div>
      
      <div className="footer">
        <div>[F4] Menu · [F11] Fullscreen</div>
        <div style={{color: 'var(--text-dim)'}}>By FatihMakes (Remastered)</div>
      </div>
    </div>
  )
}

export default App
