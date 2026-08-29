import os, base64

ANIMATION_DIR = os.path.dirname(os.path.abspath(__file__))
logo_b64 = "data:image/png;base64," + base64.b64encode(open(os.path.join(ANIMATION_DIR, "original_logo.png"), "rb").read()).decode("utf-8")

html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PocketClot · Organischer Jelly- & Waber-Übergang</title>
  <style>
    :root {{
      --bg-primary: #F8F6F0;
      --bg-surface: #FFFFFF;
      --bg-card: #FFFFFF;
      --text-main: #2D2319;
      --text-muted: #7A6F64;
      --border-color: #E8E2D8;
      --accent: #E65100;
      --accent-warm: #FF9800;
      --accent-glow: rgba(255, 152, 0, 0.35);
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      --radius: 16px;
      --shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    }}

    body.dark {{
      --bg-primary: #141210;
      --bg-surface: #1E1B18;
      --bg-card: #25221E;
      --text-main: #EDE7DF;
      --text-muted: #9E9387;
      --border-color: #38332D;
      --accent: #FF9800;
      --accent-warm: #FFA726;
      --accent-glow: rgba(255, 152, 0, 0.25);
      --shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: var(--font-family);
      background-color: var(--bg-primary);
      color: var(--text-main);
      line-height: 1.5;
      padding: 32px 20px 100px 20px;
      display: flex;
      justify-content: center;
      transition: background-color 0.3s, color 0.3s;
    }}

    .container {{
      max-width: 1100px;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
    }}

    .header-title h1 {{
      font-size: 24px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .header-title p {{
      font-size: 14px;
      color: var(--text-muted);
      margin-top: 4px;
    }}

    .theme-toggle {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 16px;
      border-radius: 20px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}

    .theme-toggle:hover {{ border-color: var(--accent-warm); }}

    .grid-2 {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 28px;
    }}

    @media (max-width: 860px) {{
      .grid-2 {{ grid-template-columns: 1fr; }}
    }}

    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 24px;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 20px;
    }}

    .card-title {{
      font-size: 16px;
      font-weight: 700;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .stage-container {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 280px;
      background: var(--bg-surface);
      border-radius: 12px;
      border: 1px dashed var(--border-color);
      position: relative;
      overflow: hidden;
    }}

    canvas.stage-canvas {{
      max-width: 260px;
      max-height: 260px;
      width: 100%;
      height: 100%;
    }}

    .transition-state-pill {{
      position: absolute;
      top: 14px;
      left: 14px;
      background: rgba(0, 0, 0, 0.7);
      color: #FFF;
      padding: 5px 12px;
      border-radius: 14px;
      font-size: 12px;
      font-weight: 600;
      backdrop-filter: blur(4px);
    }}

    .action-bar {{
      display: flex;
      gap: 12px;
    }}

    .btn-action {{
      flex: 1;
      background: var(--accent);
      color: #FFFFFF;
      border: none;
      padding: 14px 20px;
      border-radius: 12px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: background 0.2s, transform 0.1s;
    }}

    .btn-action:hover {{ background: #D84315; }}
    .btn-action:active {{ transform: scale(0.98); }}

    .btn-action.stop {{ background: #455A64; }}
    .btn-action.stop:hover {{ background: #37474F; }}

    .progress-track {{
      width: 100%;
      height: 8px;
      background: var(--border-color);
      border-radius: 4px;
      overflow: hidden;
      margin-top: 4px;
    }}

    .progress-fill {{
      height: 100%;
      width: 0%;
      background: var(--accent);
      transition: width 0.05s linear;
    }}

    .controls-grid {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    .control-row {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .control-header {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      font-weight: 600;
    }}

    input[type="range"] {{
      width: 100%;
      accent-color: var(--accent);
    }}

    /* Phone Mockup */
    .phone-mockup {{
      background: var(--bg-surface);
      border: 2px solid var(--border-color);
      border-radius: 28px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      box-shadow: var(--shadow);
    }}

    .chat-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 12px;
    }}

    .chat-messages {{
      display: flex;
      flex-direction: column;
      gap: 14px;
      min-height: 180px;
    }}

    .user-bubble {{
      align-self: flex-end;
      background: var(--accent-warm);
      color: #FFFFFF;
      padding: 10px 14px;
      border-radius: 16px 16px 4px 16px;
      font-size: 13px;
      max-width: 80%;
    }}

    .assistant-stream-block {{
      align-self: flex-start;
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      border-radius: 16px 16px 16px 4px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 88%;
    }}

    .assistant-header {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .app-brand-text {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: var(--accent);
    }}

    .typing-dots {{
      display: flex;
      gap: 4px;
      align-items: center;
      padding: 4px 0;
    }}

    .dot {{
      width: 6px;
      height: 6px;
      background: var(--accent-warm);
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out both;
    }}

    .dot:nth-child(1) {{ animation-delay: -0.32s; }}
    .dot:nth-child(2) {{ animation-delay: -0.16s; }}

    @keyframes bounce {{
      0%, 80%, 100% {{ transform: scale(0); }}
      40% {{ transform: scale(1); }}
    }}

    .explanation-box {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px;
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.6;
    }}

    .explanation-box strong {{
      color: var(--text-main);
    }}

    .compare-container {{
      display: flex;
      align-items: center;
      justify-content: space-around;
      padding: 20px;
      background: var(--bg-surface);
      border-radius: 12px;
      border: 1px solid var(--border-color);
    }}

    .compare-item {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
    }}

    .compare-label {{
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>

<div class="container">

  <header>
    <div class="header-title">
      <h1><span>🟠</span> PocketClot · Organische Jelly- & Thinking-Animation</h1>
      <p>100% das echte Logo mit physikalischem Squish, Atmen, Neigen und Ambient-Aura</p>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">
      <span>🌗</span> Theme umschalten
    </button>
  </header>

  <div class="grid-2">
    
    <!-- Linker Bereich: Physik-Labor -->
    <div class="card">
      <div class="card-title">
        <span>🧪 Interaktives Knetmassen-Labor</span>
      </div>

      <div class="stage-container">
        <div class="transition-state-pill" id="stageStatusPill">Ruhezustand (0% Morph)</div>
        <canvas id="stageCanvas" class="stage-canvas" width="400" height="400"></canvas>
      </div>

      <!-- Action Buttons -->
      <div class="action-bar">
        <button class="btn-action" onclick="triggerStart()">
          <span>▶️</span> Denken starten (Reinfließen)
        </button>
        <button class="btn-action stop" onclick="triggerStop()">
          <span>⏹️</span> Antwort fertig (Zurückfließen)
        </button>
      </div>

      <div>
        <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:600; color:var(--text-muted);">
          <span>Transitions-Fortschritt</span>
          <span id="transPctLabel">0%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" id="transProgressFill"></div>
        </div>
      </div>

      <!-- Settings -->
      <div class="controls-grid">
        <div class="control-row">
          <div class="control-header">
            <span>Transitions-Dauer (Ein- und Auslaufzeit)</span>
            <span id="durationVal">1.2s</span>
          </div>
          <input type="range" id="durationInput" min="0.4" max="3.0" step="0.1" value="1.2" oninput="updateDuration(this.value)">
        </div>

        <div class="control-row">
          <div class="control-header">
            <span>Wobble- & Squish-Intensität</span>
            <span id="intensityVal">100%</span>
          </div>
          <input type="range" id="intensityInput" min="0.3" max="2.0" step="0.1" value="1.0" oninput="updateIntensity(this.value)">
        </div>

        <div class="control-row">
          <div class="control-header">
            <span>Manuelle Morph-Steuerung (Scrubber)</span>
            <span id="manualVal">0%</span>
          </div>
          <input type="range" id="manualInput" min="0" max="1" step="0.005" value="0" oninput="onScrub(this.value)">
        </div>
      </div>

      <div class="explanation-box">
        <strong>Wie die organische Animation funktioniert:</strong>
        Im Ruhezustand (0%) ruht exakt das echte PocketClot-Logo mit 100% seiner originalen Bildschärfe und Glanzpunkten.
        Beim Starten wacht die Knetmasse elastisch auf: Sie beginnt in zwei überlagernden Achsen organisch zu quetschen (Squish/Stretch), sanft zu atmen ($0.95 \dots 1.05\times$), dynamisch zu neigen ($-3.5^\circ \dots +3.5^\circ$) und eine weiche Ambient-Aura hinter dem Logo aufzubauen.
        Beim Stoppen federn alle Bewegungen über $1.4$ Sekunden sanft ab und das Logo beruhigt sich exakt in seiner Ausgangsposition.
      </div>
    </div>

    <!-- Rechter Bereich: Live Chat Mockup -->
    <div class="card">
      <div class="card-title">
        <span>📱 Live-Test im Chat-Header</span>
      </div>

      <div class="phone-mockup">
        <div class="chat-header">
          <div style="font-weight:700; font-size:14px;">Chat mit Claude 3.7</div>
        </div>

        <div class="chat-messages">
          <div class="user-bubble">
            Plane mir bitte die Architektur für das PocketClot-Logo!
          </div>

          <div class="assistant-stream-block">
            <div class="assistant-header">
              <!-- Mini Canvas with exact jelly morph -->
              <canvas id="miniCanvas" width="60" height="60" style="width:26px; height:26px;"></canvas>
              <span class="app-brand-text">POCKETCLOT</span>
            </div>

            <div class="typing-dots" id="chatTypingDots" style="display:none;">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>

            <div id="chatAnswerText" style="display:block; font-size:13px; color:var(--text-main); line-height:1.45;">
              Hier ist die Antwort: Das echte Logo behält 100% seine vertraute Gestalt und wacht beim Denken organisch auf!
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Vergleichsbereich -->
  <div class="card">
    <div class="card-title">
      <span>🔍 3-Phasen-Übersicht</span>
    </div>
    <div class="compare-container">
      
      <div class="compare-item">
        <canvas id="compareStaticCanvas" width="160" height="160" style="width:80px; height:80px;"></canvas>
        <span class="compare-label">1. Ruhezustand (0% Morph)</span>
      </div>

      <div style="font-size:24px; color:var(--text-muted);">➔</div>

      <div class="compare-item">
        <canvas id="compareMidCanvas" width="160" height="160" style="width:80px; height:80px;"></canvas>
        <span class="compare-label">2. Reinfließen (50%)</span>
      </div>

      <div style="font-size:24px; color:var(--text-muted);">➔</div>

      <div class="compare-item">
        <canvas id="compareFullCanvas" width="160" height="160" style="width:80px; height:80px;"></canvas>
        <span class="compare-label">3. Volles Thinking-Pulsieren (100%)</span>
      </div>

    </div>
  </div>

</div>

<script>
  const logoImg = new Image();
  logoImg.src = "{logo_b64}";

  let transitionProgress = 0.0;
  let targetProgress = 0.0;
  let transitionDuration = 1.2;
  let intensityMul = 1.0;
  let isThinking = false;
  let lastTime = performance.now();

  function toggleTheme() {{
    document.body.classList.toggle('dark');
  }}

  function updateDuration(val) {{
    transitionDuration = parseFloat(val);
    document.getElementById('durationVal').innerText = transitionDuration.toFixed(1) + 's';
  }}

  function updateIntensity(val) {{
    intensityMul = parseFloat(val);
    document.getElementById('intensityVal').innerText = Math.round(intensityMul * 100) + '%';
  }}

  function triggerStart() {{
    isThinking = true;
    targetProgress = 1.0;
    document.getElementById('chatTypingDots').style.display = 'flex';
    document.getElementById('chatAnswerText').style.display = 'none';
    document.getElementById('stageStatusPill').innerText = 'Reinfließen (Denken startet)...';
  }}

  function triggerStop() {{
    isThinking = false;
    targetProgress = 0.0;
    document.getElementById('chatTypingDots').style.display = 'none';
    document.getElementById('chatAnswerText').style.display = 'block';
    document.getElementById('stageStatusPill').innerText = 'Zurückfließen (Beruhigen)...';
  }}

  function onScrub(val) {{
    targetProgress = parseFloat(val);
    transitionProgress = targetProgress;
    updateUI();
  }}

  function updateUI() {{
    const pct = Math.round(transitionProgress * 100);
    document.getElementById('transPctLabel').innerText = pct + '%';
    document.getElementById('transProgressFill').style.width = pct + '%';
    document.getElementById('manualInput').value = transitionProgress;
    document.getElementById('manualVal').innerText = pct + '%';

    if (transitionProgress === 0) {{
      document.getElementById('stageStatusPill').innerText = 'Ruhezustand (0% Morph)';
    }} else if (transitionProgress === 1) {{
      document.getElementById('stageStatusPill').innerText = 'Volles Thinking-Pulsieren (100%)';
    }} else if (targetProgress > transitionProgress) {{
      document.getElementById('stageStatusPill').innerText = 'Reinfließen (' + pct + '%)';
    }} else {{
      document.getElementById('stageStatusPill').innerText = 'Zurückfließen (' + pct + '%)';
    }}
  }}

  // Render Organic Physical Jelly / Knetmassen Deformation of the Genuine Logo
  function drawOrganicLogo(canvas, time, morphP) {{
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (!logoImg.complete || logoImg.naturalWidth === 0) return;

    const cx = w / 2;
    const cy = h / 2;
    const imgW = logoImg.naturalWidth;
    const imgH = logoImg.naturalHeight;
    const baseScale = (Math.min(w, h) * 0.72) / imgW;

    const t = time * 0.0015 * 0.8;
    const p = morphP * intensityMul;

    // Organic Physics Variables:
    // 1. Breathing Volume Scale (isotropic oscillation)
    const breath = 1.0 + (Math.sin(t * 1.8) * 0.05) * p;

    // 2. Rotating Elastic Squish (non-isotropic squish & stretch across shifting axes)
    const squishAngle = t * 1.2;
    const squishFactor = 0.065 * p;
    const scaleX = breath * (1.0 + Math.sin(t * 2.3) * squishFactor);
    const scaleY = breath * (1.0 - Math.sin(t * 2.3) * squishFactor);

    // 3. Pendulum Tilt
    const tilt = (Math.sin(t * 1.4) * 0.045 + Math.cos(t * 0.9) * 0.02) * p;

    ctx.save();
    ctx.translate(cx, cy);

    // Ambient Glow behind the genuine logo (only when active)
    if (morphP > 0.01) {{
      const glowR = (imgW * baseScale) * 0.55;
      const glowGrad = ctx.createRadialGradient(0, 0, glowR * 0.2, 0, 0, glowR * 1.55);
      glowGrad.addColorStop(0, `rgba(255, 152, 0, ${{0.40 * morphP}})`);
      glowGrad.addColorStop(0.65, `rgba(255, 87, 34, ${{0.16 * morphP}})`);
      glowGrad.addColorStop(1, 'rgba(255, 87, 34, 0)');
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(0, 0, glowR * 1.55, 0, Math.PI * 2);
      ctx.fill();
    }}

    // Apply fluid transforms to the authentic logo image
    ctx.rotate(tilt);
    ctx.rotate(squishAngle);
    ctx.scale(scaleX, scaleY);
    ctx.rotate(-squishAngle);

    // Draw the 100% genuine logo image with crisp pixel quality
    const dw = imgW * baseScale;
    const dh = imgH * baseScale;
    ctx.drawImage(logoImg, -dw / 2, -dh / 2, dw, dh);

    ctx.restore();
  }}

  function animate(now) {{
    const dt = (now - lastTime) / 1000;
    lastTime = now;

    if (Math.abs(targetProgress - transitionProgress) > 0.0005) {{
      const step = (1.0 / transitionDuration) * dt;
      if (targetProgress > transitionProgress) {{
        transitionProgress = Math.min(targetProgress, transitionProgress + step);
      }} else {{
        transitionProgress = Math.max(targetProgress, transitionProgress - step);
      }}
      updateUI();
    }} else {{
      transitionProgress = targetProgress;
    }}

    const smoothedP = transitionProgress * transitionProgress * (3 - 2 * transitionProgress);

    drawOrganicLogo(document.getElementById('stageCanvas'), now, smoothedP);
    drawOrganicLogo(document.getElementById('miniCanvas'), now, smoothedP);

    // Comparisons
    drawOrganicLogo(document.getElementById('compareStaticCanvas'), 0, 0.0);
    drawOrganicLogo(document.getElementById('compareMidCanvas'), now, 0.5);
    drawOrganicLogo(document.getElementById('compareFullCanvas'), now, 1.0);

    requestAnimationFrame(animate);
  }}

  logoImg.onload = () => {{
    requestAnimationFrame(animate);
  }};
  if (logoImg.complete) {{
    requestAnimationFrame(animate);
  }}
</script>

</body>
</html>
"""

with open(os.path.join(ANIMATION_DIR, "preview.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("Updated preview.html with clean organic squish animation!")
