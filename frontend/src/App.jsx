import { useState, useEffect, useRef, useCallback } from 'react'
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
  const [activeStreamText, setActiveStreamText] = useState('')
  const [activeTool, setActiveTool] = useState(null)
  
  const [status, setStatus] = useState('ONLINE') // ONLINE, LISTENING, HEARING, THINKING
  const [inputText, setInputText] = useState('')
  const [cpuUsage, setCpuUsage] = useState(24)
  const [ramUsage, setRamUsage] = useState(48)
  const [netSpeed, setNetSpeed] = useState(13)
  const [isMicActive, setIsMicActive] = useState(true)
  const [wsInstance, setWsInstance] = useState(null)
  
  const messagesEndRef = useRef(null)
  const chatContainerRef = useRef(null)
  const isScrolledUpRef = useRef(false)
  const streamCompleteRef = useRef(false)

  const [isBooting, setIsBooting] = useState(true)
  const [bootText, setBootText] = useState('')
  const [protocol, setProtocol] = useState('normal')
  const [countdown, setCountdown] = useState(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  const handleMouseMove = useCallback((e) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 30
    const y = (e.clientY / window.innerHeight - 0.5) * -30
    setMousePos({ x, y })
  }, [])

  useEffect(() => {
    if (countdown === null) return;
    if (countdown <= 0) {
      setCountdown(null);
      setProtocol('normal');
      setCurrentTheme(themes[0]);
      try {
        if (window.pywebview) window.pywebview.api.minimize();
        else fetch('http://localhost:8000/api/minimize');
      } catch (err) {}
      return;
    }
    const timer = setTimeout(() => setCountdown(prev => prev - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  useEffect(() => {
    const bootSteps = [
      "INITIATING MARK L PROTOCOLS...",
      "LOADING AI CORE...",
      "CALIBRATING NEURAL NETWORKS...",
      "CONNECTING TO SATELLITE UPLINK...",
      "AUDIO DRIVERS ONLINE.",
      "WELCOME HOME, SIR."
    ];
    let step = 0;
    const interval = setInterval(() => {
      setBootText(prev => prev + "\n" + bootSteps[step]);
      step++;
      if (step >= bootSteps.length) {
        clearInterval(interval);
        setTimeout(() => setIsBooting(false), 1200);
      }
    }, 500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty('--theme-color', currentTheme.color)
    document.documentElement.style.setProperty('--theme-color-rgb', currentTheme.rgb)
  }, [currentTheme])

  const handleScroll = () => {
    if (chatContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      isScrolledUpRef.current = scrollHeight - scrollTop > clientHeight + 50;
    }
  };

  const scrollToBottom = useCallback(() => {
    if (!isScrolledUpRef.current) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      });
    }
  }, []);

  useEffect(() => {
    scrollToBottom()
  }, [messages, activeStreamText, activeTool, scrollToBottom])

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
        } else if (data.type === 'action' && data.value === 'protocol') {
          setProtocol(data.protocol_name);
          if (data.protocol_name === 'lockdown') setCurrentTheme(themes[1]);
          else if (data.protocol_name === 'normal') { setCurrentTheme(themes[0]); setCountdown(null); }
          else if (data.protocol_name === 'party') setCurrentTheme(themes[4]);
          else if (data.protocol_name === 'decryption') setCurrentTheme(themes[3]);
          else if (data.protocol_name === 'destruct') { setCurrentTheme(themes[1]); setCountdown(10); }
          else if (data.protocol_name === 'satellite') setCurrentTheme(themes[0]);
        } else if (data.type === 'vitals') {
          setCpuUsage(data.cpu);
          setRamUsage(data.ram);
          setNetSpeed(data.net);
        } else if (data.type === 'status') {
          setStatus(data.value);
          if (data.value === 'ONLINE') {
              streamCompleteRef.current = true;
          }
        } else if (data.type === 'log') {
          setMessages(prev => [...prev, { sender: data.sender, text: data.text }]);
        } else if (data.type === 'token') {
          setActiveStreamText(prev => prev + data.content);
        } else if (data.type === 'tool_start') {
          setActiveTool(`Running: ${data.name}...`);
        } else if (data.type === 'tool_end') {
          setActiveTool(null);
        } else if (data.type === 'error') {
          setMessages(prev => [...prev, { sender: 'err', text: `ERR: ${data.message}` }]);
        }
      };

      ws.onclose = () => {
        setMessages(prev => [...prev, { sender: 'err', text: 'ERR: Brain Disconnected. Reconnecting...' }])
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

  // Flush active stream to messages when status goes ONLINE
  useEffect(() => {
      if (streamCompleteRef.current && status === 'ONLINE') {
          if (activeStreamText.trim() !== '') {
              setMessages(prev => [...prev, { sender: 'sys', text: `JRV: ${activeStreamText}` }]);
              setActiveStreamText('');
          }
          setActiveTool(null);
          streamCompleteRef.current = false;
      }
  }, [status, activeStreamText]);


  const toggleMic = () => {
    const newState = !isMicActive;
    setIsMicActive(newState);
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ action: "toggle_mic", state: newState }));
    }
  }

  const interrupt = () => {
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ action: "interrupt" }));
    }
  }

  const sendMessage = async (text) => {
    if (!text.trim()) return
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
        wsInstance.send(JSON.stringify({ action: "chat", text: text }));
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      sendMessage(inputText)
      setInputText('')
      isScrolledUpRef.current = false; // force scroll down on user input
    }
  }

  if (isBooting) {
    return (
      <div className="boot-screen" style={{
        height: '100vh', width: '100vw', backgroundColor: '#000', 
        color: 'var(--theme-color)', fontFamily: 'monospace', padding: '50px', 
        fontSize: '1.2rem', whiteSpace: 'pre-line', textShadow: '0 0 10px var(--theme-color)'
      }}>
        {bootText}
      </div>
    )
  }

  return (
    <div 
      className={`dashboard ${protocol === 'lockdown' ? 'lockdown-mode' : ''} ${protocol === 'party' ? 'party-mode' : ''} ${protocol === 'decryption' ? 'matrix-mode' : ''}`}
      onMouseMove={handleMouseMove}
    >
      
      <div className="hud-crosshair top-left"></div>
      <div className="hud-crosshair top-right"></div>
      <div className="hud-crosshair bottom-left"></div>
      <div className="hud-crosshair bottom-right"></div>

      {countdown !== null && (
        <div className="destruct-overlay">
          <div className="destruct-text">SELF DESTRUCT IN</div>
          <div className="destruct-timer">{countdown}</div>
        </div>
      )}

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
            <div className="progress-bar"><div className="progress cyan" style={{width: `${Math.min(netSpeed * 2, 100)}%`}}></div></div>
          </div>
          
          <div className="sys-info" style={{marginTop: '20px'}}>
            UP 00:21<br/>
            PROC 280<br/>
            OS WIN
          </div>

          <div className="status-badges" style={{marginTop: '20px'}}>
            <div className="badge active">AI CORE<br/>ACTIVE</div>
            <div className="badge active">SEC<br/>CLEARED</div>
            <div className={`badge ${protocol !== 'normal' ? 'active' : 'outline'}`} style={{color: protocol === 'lockdown' ? 'red' : ''}}>
              PROTOCOL<br/>{protocol.toUpperCase()}
            </div>
          </div>

          <div className="env-module">
            <div className="panel-title">▼ ENVIRONMENT</div>
            <div className="env-grid">
              <div className="env-item">
                <div className="env-value">72°</div>
                <div className="env-label">TEMP (F)</div>
              </div>
              <div className="env-item">
                <div className="env-value">14.7</div>
                <div className="env-label">ATM (PSI)</div>
              </div>
              <div className="env-item">
                <div className="env-value">45%</div>
                <div className="env-label">HUMIDITY</div>
              </div>
              <div className="env-item">
                <div className="env-value">12</div>
                <div className="env-label">WIND (MPH)</div>
              </div>
            </div>
          </div>
        </div>

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

          {protocol === 'satellite' ? (
            <div className="radar-container">
              <div className="radar-circle"></div>
              <div className="radar-line"></div>
              <div className="radar-target" style={{top: '30%', left: '40%'}}></div>
              <div className="radar-target" style={{top: '60%', left: '70%'}}></div>
              <div className="radar-text">SATELLITE UPLINK ESTABLISHED<br/>SCANNING...</div>
            </div>
          ) : (
            <div className="arc-reactor-wrapper" style={{ transform: `rotateX(${mousePos.y}deg) rotateY(${mousePos.x}deg)` }}>
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
          )}

          {(status === 'LISTENING' || status === 'THINKING') && (
            <div className="audio-visualizer">
              <div className="bar bar1"></div>
              <div className="bar bar2"></div>
              <div className="bar bar3"></div>
              <div className="bar bar4"></div>
              <div className="bar bar5"></div>
              <div className="bar bar4"></div>
              <div className="bar bar3"></div>
              <div className="bar bar2"></div>
              <div className="bar bar1"></div>
            </div>
          )}
        </div>

        <div className="panel right-panel">
          <div className="directive-module">
            <div className="panel-title">▼ ACTIVE DIRECTIVES</div>
            <div className="directive-list">
              <div className="directive-item" style={{'--delay': 0}}>
                <span className="directive-icon">⟡</span>
                <span>MONITORING NETWORK TRAFFIC</span>
              </div>
              <div className="directive-item" style={{'--delay': 1}}>
                <span className="directive-icon">⟡</span>
                <span>MAINTAINING UPLINK SEC</span>
              </div>
              <div className="directive-item" style={{'--delay': 2}}>
                <span className="directive-icon">⟡</span>
                <span>AWAITING USER COMMAND</span>
              </div>
            </div>
          </div>

          <div className="panel-title">▼ ACTIVITY LOG</div>
          
          <div className="activity-log" ref={chatContainerRef} onScroll={handleScroll}>
            {messages.map((msg, i) => (
              <div key={i} className={`log-entry ${msg.sender}`}>
                {msg.text}
              </div>
            ))}
            
            {/* Active Stream Rendering */}
            {activeStreamText && (
               <div className="log-entry sys stream-active">
                  JRV: {activeStreamText} <span className="blink">|</span>
               </div>
            )}
            {activeTool && (
               <div className="log-entry sys tool-active" style={{color: 'var(--theme-color)', fontStyle: 'italic'}}>
                  [ {activeTool} ]
               </div>
            )}
            <div ref={messagesEndRef} />
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
            <button className="btn-send" onClick={() => {sendMessage(inputText); setInputText(''); isScrolledUpRef.current = false;}}>▶</button>
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
