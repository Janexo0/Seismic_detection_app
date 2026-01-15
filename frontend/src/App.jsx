import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [waveformData, setWaveformData] = useState([]);
  const [detections, setDetections] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState({
    waveforms: 'disconnected',
    detections: 'disconnected'
  });

  const waveformWs = useRef(null);
  const detectionWs = useRef(null);

  useEffect(() => {
    // Connect to waveform WebSocket
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
    
    waveformWs.current = new WebSocket(`${wsUrl}/ws/waveforms`);
    
    waveformWs.current.onopen = () => {
      console.log('Connected to waveform stream');
      setConnectionStatus(prev => ({ ...prev, waveforms: 'connected' }));
    };
    
    waveformWs.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setWaveformData(prev => [...prev.slice(-100), data]);
    };
    
    waveformWs.current.onclose = () => {
      console.log('Disconnected from waveform stream');
      setConnectionStatus(prev => ({ ...prev, waveforms: 'disconnected' }));
    };

    // Connect to detection WebSocket
    detectionWs.current = new WebSocket(`${wsUrl}/ws/detections`);
    
    detectionWs.current.onopen = () => {
      console.log('Connected to detection stream');
      setConnectionStatus(prev => ({ ...prev, detections: 'connected' }));
    };
    
    detectionWs.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setDetections(prev => [data, ...prev.slice(0, 49)]);
    };
    
    detectionWs.current.onclose = () => {
      console.log('Disconnected from detection stream');
      setConnectionStatus(prev => ({ ...prev, detections: 'disconnected' }));
    };

    // Cleanup on unmount
    return () => {
      if (waveformWs.current) waveformWs.current.close();
      if (detectionWs.current) detectionWs.current.close();
    };
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>🌍 Earthquake Detection System</h1>
        <div className="connection-status">
          <span className={connectionStatus.waveforms === 'connected' ? 'status-connected' : 'status-disconnected'}>
            Waveforms: {connectionStatus.waveforms}
          </span>
          <span className={connectionStatus.detections === 'connected' ? 'status-connected' : 'status-disconnected'}>
            Detections: {connectionStatus.detections}
          </span>
        </div>
      </header>

      <div className="content">
        <div className="section waveform-section">
          <h2>Real-Time Seismic Waveforms</h2>
          <div className="waveform-display">
            {waveformData.length > 0 ? (
              <WaveformChart data={waveformData[waveformData.length - 1]} />
            ) : (
              <p>Waiting for waveform data...</p>
            )}
          </div>
        </div>

        <div className="section detection-section">
          <h2>Detection Feed</h2>
          <DetectionFeed detections={detections} />
        </div>
      </div>
    </div>
  );
}

function WaveformChart({ data }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!data || !data.data) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Draw waveform
    const waveformData = data.data.slice(0, 500); // Show first 500 points
    const step = width / waveformData.length;
    const maxAmplitude = Math.max(...waveformData.map(Math.abs));
    const scale = (height / 2) * 0.8 / (maxAmplitude || 1);

    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    waveformData.forEach((value, index) => {
      const x = index * step;
      const y = height / 2 - value * scale;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();

    // Draw center line
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

  }, [data]);

  return (
    <div className="waveform-container">
      <canvas ref={canvasRef} width={800} height={300} />
      {data && (
        <div className="waveform-info">
          <span>Station: {data.station?.network}.{data.station?.station}.{data.station?.channel}</span>
          <span>Sampling Rate: {data.sampling_rate} Hz</span>
          <span>Event ID: {data.event_id?.slice(0, 8)}...</span>
        </div>
      )}
    </div>
  );
}

function DetectionFeed({ detections }) {
  return (
    <div className="detection-feed">
      {detections.length === 0 ? (
        <p>Waiting for detections...</p>
      ) : (
        detections.map((detection, index) => (
          <DetectionCard key={index} detection={detection} />
        ))
      )}
    </div>
  );
}

function DetectionCard({ detection }) {
  const models = detection.models || {};
  const comparison = detection.comparison || {};
  const modelNames = Object.keys(models);

  return (
    <div className={`detection-card ${comparison.agreement ? 'agreement' : 'disagreement'}`}>
      <div className="detection-header">
        <span className="event-id">Event: {detection.event_id?.slice(0, 8)}...</span>
        <span className="timestamp">{new Date(detection.timestamp).toLocaleTimeString()}</span>
        <span className={`agreement-badge ${comparison.agreement ? 'agree' : 'disagree'}`}>
          {comparison.agreement ? '✓ Agreement' : '✗ Disagreement'}
        </span>
      </div>

      <div className="models-comparison">
        {modelNames.map(modelName => {
          const result = models[modelName];
          return (
            <div key={modelName} className="model-result">
              <h4>{modelName}</h4>
              <div className={`detection-status ${result.detected ? 'detected' : 'not-detected'}`}>
                {result.detected ? '🔴 DETECTED' : '🟢 No Detection'}
              </div>
              <div className="confidence">
                Confidence: {(result.confidence * 100).toFixed(1)}%
              </div>
              {result.picks && result.picks.length > 0 && (
                <div className="picks">
                  {result.picks.map((pick, i) => (
                    <span key={i} className="pick-badge">
                      {pick.phase}: {(pick.probability * 100).toFixed(0)}%
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {comparison.confidence_diff !== undefined && (
        <div className="comparison-stats">
          <span>Confidence Δ: {(comparison.confidence_diff * 100).toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}

export default App;