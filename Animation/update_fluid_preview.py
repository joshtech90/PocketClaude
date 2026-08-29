import os, json

ANIMATION_DIR = os.path.dirname(os.path.abspath(__file__))

# 72 exact polar radii from repaired original logo
radii_72 = [0.873, 0.8976, 0.9507, 0.9702, 0.9967, 1.007, 0.9835, 0.9651, 0.9446, 0.9027, 0.8342, 0.78, 0.7616, 0.7555, 0.8097, 0.8373, 0.8863, 0.8976, 0.915, 0.919, 0.9078, 0.9037, 0.871, 0.8925, 0.9344, 0.962, 0.9722, 0.9937, 0.9937, 0.9651, 0.9589, 0.916, 0.8833, 0.8373, 0.7994, 0.7913, 0.8301, 0.8761, 0.9078, 0.9252, 0.9334, 0.9395, 0.9344, 0.9098, 0.8618, 0.8434, 0.778, 0.7534, 0.7616, 0.7984, 0.8383, 0.8598, 0.9078, 0.919, 0.9364, 0.962, 0.9507, 0.9477, 0.9293, 0.869, 0.8362, 0.8056, 0.8342, 0.873, 0.9272, 0.962, 0.9589, 0.963, 0.9518, 0.9252, 0.8863, 0.8546]

html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PocketClot · Echte Geometrische Fluid-Transition</title>
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
      max-width: 240px;
      max-height: 240px;
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

    /* Progress bar */
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

    /* Controls */
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
  </style>
</head>
<body>

<div class="container">

  <header>
    <div class="header-title">
      <h1><span>🟠</span> PocketClot · Geometrische Fluid-Transition</h1>
      <p>Organisches Reinfließen & Zurückfließen direkt aus der Silhouette des Original-Logos</p>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">
      <span>🌗</span> Theme umschalten
    </button>
  </header>

  <div class="grid-2">
    
    <!-- Linker Bereich: Physik-Labor -->
    <div class="card">
      <div class="card-title">
        <span>🧪 Morphing-Labor (Echte Geometrie-Deformation)</span>
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
            <span>Manuelle Morph-Steuerung (Scrubber)</span>
            <span id="manualVal">0%</span>
          </div>
          <input type="range" id="manualInput" min="0" max="1" step="0.005" value="0" oninput="onScrub(this.value)">
        </div>
      </div>

      <div class="explanation-box">
        <strong>So funktioniert der echte Geometrie-Übergang:</strong>
        Im Ruhezustand (0%) tastet die Canvas exakt die Original-Silhouette des reparierten PocketClot-Logos ab.
        Beim Starten schwellen die Wellen über 1.2 Sekunden sinusförmig an, die Knetmasse beginnt sichtbar zu atmen und zu neigen, und die Ambient-Aura blüht weich auf.
        Beim Stoppen klingen die Wellen gedämpft ab, und das Logo fließt elastisch in seine exakte Ruheform zurück.
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
            Erstelle mir bitte den fließenden Übergang für das PocketClot-Logo!
          </div>

          <div class="assistant-stream-block">
            <div class="assistant-header">
              <!-- Mini Canvas with exact same morph -->
              <canvas id="miniCanvas" width="60" height="60" style="width:26px; height:26px;"></canvas>
              <span class="app-brand-text">POCKETCLOT</span>
            </div>

            <div class="typing-dots" id="chatTypingDots" style="display:none;">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>

            <div id="chatAnswerText" style="display:block; font-size:13px; color:var(--text-main); line-height:1.45;">
              Hier ist die Antwort: Du siehst oben links, wie das echte Logo beim Klick auf "Denken starten" weich erwacht, während des Streams organisch wabert, und beim Klick auf "Antwort fertig" ganz geschmeidig in das ruhende Logo zurückfließt!
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>

</div>

<script>
  // 72 exact polar radii from repaired original logo
  const originalRadii = {json.dumps(radii_72)};
  const N = originalRadii.length;

  let transitionProgress = 0.0;
  let targetProgress = 0.0;
  let transitionDuration = 1.2; // seconds
  let isThinking = false;
  let animStartTime = performance.now();
  let lastTime = performance.now();

  function toggleTheme() {{
    document.body.classList.toggle('dark');
  }}

  function updateDuration(val) {{
    transitionDuration = parseFloat(val);
    document.getElementById('durationVal').innerText = transitionDuration.toFixed(1) + 's';
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
      document.getElementById('stageStatusPill').innerText = 'Volles Waber-Morphen (100%)';
    }} else if (targetProgress > transitionProgress) {{
      document.getElementById('stageStatusPill').innerText = 'Reinfließen (' + pct + '%)';
    }} else {{
      document.getElementById('stageStatusPill').innerText = 'Zurückfließen (' + pct + '%)';
    }}
  }}

  // Render unified geometric fluid blob
  function drawUnifiedBlob(canvas, time, morphP) {{
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2;
    const cy = h / 2;
    const r0 = Math.min(w, h) * 0.38;
    const t = time * 0.0015 * 0.8;

    // Smooth breathing & rotation scaled by morph progress
    const breath = 1.0 + (Math.sin(t * 1.6) * 0.05) * morphP;
    const tilt = (Math.sin(t * 1.2) * 0.06) * morphP;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(tilt);
    ctx.scale(breath, breath);

    // 1. Ambient Glow (blends smoothly with morph progress)
    if (morphP > 0.01) {{
      const glowGrad = ctx.createRadialGradient(0, 0, r0 * 0.3, 0, 0, r0 * 1.55);
      glowGrad.addColorStop(0, `rgba(255, 152, 0, ${{0.42 * morphP}})`);
      glowGrad.addColorStop(0.7, `rgba(255, 87, 34, ${{0.18 * morphP}})`);
      glowGrad.addColorStop(1, 'rgba(255, 87, 34, 0)');
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(0, 0, r0 * 1.55, 0, Math.PI * 2);
      ctx.fill();
    }}

    // 2. Compute 72 deformed spline points
    // When morphP = 0: exactly matches originalRadii[i]
    // When morphP > 0: ripples and waves smoothly modulate the original radii
    const points = [];
    const angleStep = (Math.PI * 2) / N;

    for (let i = 0; i < N; i++) {{
      const angle = i * angleStep;
      const baseR = r0 * originalRadii[i];

      // Harmonic wave modulation
      const wave = 1.0 + (morphP * 0.20) * (
        0.16 * Math.sin(2 * angle + t * 2.2) +
        0.11 * Math.cos(3 * angle - t * 1.5) +
        0.06 * Math.sin(5 * angle + t * 2.8)
      );

      const r = baseR * wave;
      points.push({{
        x: r * Math.cos(angle),
        y: r * Math.sin(angle)
      }});
    }}

    // 3. Catmull-Rom to Cubic Bezier Path
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 0; i < N; i++) {{
      const pPrev = points[(i - 1 + N) % N];
      const pCurr = points[i];
      const pNext = points[(i + 1) % N];
      const pNext2 = points[(i + 2) % N];

      const c1x = pCurr.x + (pNext.x - pPrev.x) / 6;
      const c1y = pCurr.y + (pNext.y - pPrev.y) / 6;
      const c2x = pNext.x - (pNext2.x - pCurr.x) / 6;
      const c2y = pNext.y - (pNext2.y - pCurr.y) / 6;

      ctx.bezierCurveTo(c1x, c1y, c2x, c2y, pNext.x, pNext.y);
    }}
    ctx.closePath();

    // 4. 3D Clay Radial Gradient Fill (Matching Original PocketClot)
    const lx = -r0 * 0.35;
    const ly = -r0 * 0.35;
    const bodyGrad = ctx.createRadialGradient(lx, ly, r0 * 0.1, 0, 0, r0 * 1.55);
    bodyGrad.addColorStop(0, '#FDD043');
    bodyGrad.addColorStop(0.35, '#FFB300');
    bodyGrad.addColorStop(0.70, '#FF6D00');
    bodyGrad.addColorStop(0.90, '#D84315');
    bodyGrad.addColorStop(1, '#BF360C');

    ctx.fillStyle = bodyGrad;
    ctx.fill();

    // 5. Specular Highlight (wanders slightly with wave phase)
    const hx = lx + (Math.cos(t * 1.5) * (r0 * 0.06)) * morphP;
    const hy = ly + (Math.sin(t * 1.2) * (r0 * 0.06)) * morphP;
    const specGrad = ctx.createRadialGradient(hx, hy, 0, hx, hy, r0 * 0.45);
    specGrad.addColorStop(0, 'rgba(255, 255, 255, 0.65)');
    specGrad.addColorStop(0.4, 'rgba(255, 255, 255, 0.20)');
    specGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = specGrad;
    ctx.beginPath();
    ctx.arc(hx, hy, r0 * 0.45, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }}

  function animate(now) {{
    const dt = (now - lastTime) / 1000;
    lastTime = now;

    // Organic Ease-In-Out / Spring Transition Physics
    if (Math.abs(targetProgress - transitionProgress) > 0.0005) {{
      const step = (1.0 / transitionDuration) * dt;
      if (targetProgress > transitionProgress) {{
        // Reinfließen: Weiches Anschwellen
        transitionProgress = Math.min(targetProgress, transitionProgress + step);
      }} else {{
        // Zurückfließen: Sanftes Ausdämpfen
        transitionProgress = Math.max(targetProgress, transitionProgress - step);
      }}
      updateUI();
    }} else {{
      transitionProgress = targetProgress;
    }}

    // Apply Smooth S-Curve (Smoothstep) to the raw linear progress for natural fluid acceleration & deceleration
    const smoothedP = transitionProgress * transitionProgress * (3 - 2 * transitionProgress);

    drawUnifiedBlob(document.getElementById('stageCanvas'), now, smoothedP);
    drawUnifiedBlob(document.getElementById('miniCanvas'), now, smoothedP);

    requestAnimationFrame(animate);
  }}

  requestAnimationFrame(animate);
</script>

</body>
</html>
"""

with open(os.path.join(ANIMATION_DIR, "preview.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("Updated preview.html with continuous geometric fluid morph!")
