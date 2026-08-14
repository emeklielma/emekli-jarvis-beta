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

  const [isBooting, setIsBooting] = useState(true)
  const [bootText, setBootText] = useState('')
  const [protocol, setProtocol] = useState('normal') // normal, lockdown, party, decryption, destruct, satellite
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [countdown, setCountdown] = useState(null)

  useEffect(() => {
    if (countdown === null) return;
    if (countdown <= 0) {
      // Trigger minimize at 0
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

  // Removed fake system monitor jitter - now using real data from python backend!

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
      setIsSpeaking(true);
      audio.onended = () => setIsSpeaking(false);
      audio.play();
    } else if ('speechSynthesis' in window) {
      // Fallback
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => setIsSpeaking(false);
      setIsSpeaking(true);
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
        } else if (data.type === 'action' && data.value === 'protocol') {
          setProtocol(data.protocol_name);
          if (data.protocol_name === 'lockdown') {
             setCurrentTheme(themes.find(t => t.name === 'Red') || themes[1]);
          } else if (data.protocol_name === 'normal') {
             setCurrentTheme(themes[0]);
             setCountdown(null);
          } else if (data.protocol_name === 'party') {
             setCurrentTheme(themes.find(t => t.name === 'Purple') || themes[4]);
          } else if (data.protocol_name === 'decryption') {
             setCurrentTheme(themes.find(t => t.name === 'Green') || themes[3]);
          } else if (data.protocol_name === 'destruct') {
             setCurrentTheme(themes.find(t => t.name === 'Red') || themes[1]);
             setCountdown(10);
          } else if (data.protocol_name === 'satellite') {
             setCurrentTheme(themes.find(t => t.name === 'Cyan') || themes[0]);
          }
        } else if (data.type === 'vitals') {
          setCpuUsage(data.cpu);
          setRamUsage(data.ram);
          setNetSpeed(data.net);
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
    setIsSpeaking(false);
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
    <div className={`dashboard ${protocol === 'lockdown' ? 'lockdown-mode' : ''} ${protocol === 'party' ? 'party-mode' : ''} ${protocol === 'decryption' ? 'matrix-mode' : ''}`}>
      
      {/* HUD CROSSHAIRS */}
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
            <div className={`badge ${protocol !== 'normal' ? 'active' : 'outline'}`} style={{color: protocol === 'lockdown' ? 'red' : ''}}>
              PROTOCOL<br/>{protocol.toUpperCase()}
            </div>
          </div>
          
          {/* Audio Visualizer */}
          {isSpeaking && (
            <div className="audio-visualizer" style={{marginTop: '20px', display: 'flex', gap: '5px', justifyContent: 'center'}}>
              <div className="bar bar1"></div>
              <div className="bar bar2"></div>
              <div className="bar bar3"></div>
              <div className="bar bar4"></div>
              <div className="bar bar5"></div>
            </div>
          )}
        </div>

        {/* CENTER PANEL */}
        <div className="panel center-panel hud-box">
          <div className="hud-corner top-left"></div>
          <div className="hud-corner top-right"></div>
          <div className="hud-corner bottom-left"></div>
          <div className="hud-corner bottom-right"></div>
          
          <h1 className="jarvis-title">J.A.R.V.I.S</h1>
          <div className="jarvis-subtitle">ARTIFICIAL INTELLIGENCE NETWORK</div>

          {protocol === 'satellite' ? (
            <div className="radar-container">
              <div className="radar-circle"></div>
              <div className="radar-line"></div>
              <div className="radar-target" style={{top: '30%', left: '40%'}}></div>
              <div className="radar-target" style={{top: '60%', left: '70%'}}></div>
              <div className="radar-text">SATELLITE UPLINK ESTABLISHED<br/>SCANNING...</div>
            </div>
          ) : (
            <div className="arc-reactor">
              <div className="core"></div>
              <div className="ring ring1"></div>
              <div className="ring ring2"></div>
              <div className="ring ring3"></div>
            </div>
          )}

          <div className="network-nodes" style={{marginTop: '40px', display: 'flex', gap: '20px', justifyContent: 'center'}}>
            <div className="node active"></div>
            <div className="node active"></div>
            <div className="node"></div>
          </div>
          
          <div className="radar-status" style={{marginTop: '20px', textAlign: 'center', color: 'var(--theme-color)'}}>
            <span className="blink">●</span> {status}
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
