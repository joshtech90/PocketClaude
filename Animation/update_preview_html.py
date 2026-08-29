import os, base64

ANIMATION_DIR = os.path.dirname(os.path.abspath(__file__))
logo_b64 = "data:image/png;base64," + base64.b64encode(open(os.path.join(ANIMATION_DIR, "original_logo.png"), "rb").read()).decode("utf-8")

html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PocketClot · Echtes Logo & Thinking Blob Animation</title>
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
      padding: 32px 20px;
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
      min-height: 260px;
      background: var(--bg-surface);
      border-radius: 12px;
      border: 1px dashed var(--border-color);
      position: relative;
      overflow: hidden;
    }}

    .stage-view {{
      width: 180px;
      height: 180px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .stage-logo-static {{
      position: absolute;
      width: 140px;
      height: 140px;
      object-fit: contain;
      transition: opacity 0.4s ease-in-out;
      filter: drop-shadow(0 8px 16px rgba(0,0,0,0.12));
    }}

    canvas.stage-canvas {{
      position: absolute;
      width: 180px;
      height: 180px;
      transition: opacity 0.4s ease-in-out;
    }}

    .transition-state-pill {{
      position: absolute;
      top: 12px;
      left: 12px;
      background: rgba(0, 0, 0, 0.6);
      color: #FFF;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 11px;
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
      padding: 12px 18px;
      border-radius: 12px;
      font-size: 14px;
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

    .mini-logo-holder {{
      width: 25px;
      height: 25px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .mini-static-img {{
      position: absolute;
      width: 25px;
      height: 25px;
      object-fit: contain;
      transition: opacity 0.3s ease-in-out;
    }}

    canvas.mini-canvas {{
      position: absolute;
      width: 25px;
      height: 25px;
      transition: opacity 0.3s ease-in-out;
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
      <h1><span>🟠</span> PocketClot · Authentisches Logo & Thinking Animation</h1>
      <p>Original-Logo im Ruhezustand (Kerbe repariert) mit fließendem Übergang beim Denkvorgang</p>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">
      <span>🌗</span> Theme umschalten
    </button>
  </header>

  <div class="grid-2">
    
    <!-- Linker Bereich: Physik-Labor -->
    <div class="card">
      <div class="card-title">
        <span>🧪 Interaktives Labor: Reinfließen & Zurückfließen</span>
      </div>

      <div class="stage-container">
        <div class="transition-state-pill" id="stageStatusPill">Ruhezustand (Echtes App-Logo)</div>
        <div class="stage-view">
          <img src="{logo_b64}" id="stageStaticImg" class="stage-logo-static" alt="PocketClot Original Logo">
          <canvas id="stageCanvas" class="stage-canvas" width="400" height="400" style="opacity:0;"></canvas>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn-action" onclick="startThinking()">
          <span>▶️</span> Denken starten (Reinfließen)
        </button>
        <button class="btn-action stop" onclick="stopThinking()">
          <span>⏹️</span> Antwort fertig (Zurückfließen)
        </button>
      </div>

      <p style="font-size:13px; color:var(--text-muted); line-height:1.5;">
        <strong>Exakte Logik:</strong> Im Ruhezustand wird 1:1 das echte, unveränderte PocketClot-App-Logo angezeigt (mit reparierter Ecke). Beim Starten des Antwort-Streams wacht die Masse elastisch auf und beginnt zu morphen. Am Ende fließt sie sanft und stoßfrei wieder in das echte Original-Logo zurück.
      </p>
    </div>

    <!-- Rechter Bereich: Live Chat Mockup -->
    <div class="card">
      <div class="card-title">
        <span>📱 Live-Test in der Chat-Ansicht</span>
      </div>

      <div class="phone-mockup">
        <div class="chat-header">
          <div style="font-weight:700; font-size:14px;">Chat mit Claude 3.7</div>
        </div>

        <div class="chat-messages">
          <div class="user-bubble">
            Erstelle mir bitte die PocketClot-Animation!
          </div>

          <div class="assistant-stream-block">
            <div class="assistant-header">
              <div class="mini-logo-holder">
                <img src="{logo_b64}" id="miniStaticImg" class="mini-static-img" alt="Mini Static">
                <canvas id="miniCanvas" class="mini-canvas" width="60" height="60" style="opacity:0;"></canvas>
              </div>
              <span class="app-brand-text">POCKETCLOT</span>
            </div>

            <div class="typing-dots" id="chatTypingDots" style="display:none;">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>

            <div id="chatAnswerText" style="display:block; font-size:13px; color:var(--text-main); line-height:1.45;">
              Hier ist die Antwort: Im Ruhezustand siehst du oben links exakt das echte PocketClot-Logo. Sobald ich denke, wacht es auf und morpht fließend!
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Vergleichsbereich -->
  <div class="card">
    <div class="card-title">
      <span>🔍 Direkter Vergleich</span>
    </div>
    <div class="compare-container">
      
      <div class="compare-item">
        <img src="{logo_b64}" alt="Authentisches Logo" style="width:72px; height:72px; object-fit:contain;">
        <span class="compare-label">1. Echtes App-Logo (Ruhezustand)</span>
      </div>

      <div style="font-size:24px; color:var(--text-muted);">➔</div>

      <div class="compare-item">
        <canvas id="compareFullCanvas" width="160" height="160" style="width:80px; height:80px;"></canvas>
        <span class="compare-label">2. Lebendige Waber-Masse (Denkvorgang)</span>
      </div>

    </div>
  </div>

</div>

<script>
  let isThinking = false;
  let transitionProgress = 0.0;
  let targetProgress = 0.0;
  let lastTime = performance.now();

  function toggleTheme() {{
    document.body.classList.toggle('dark');
  }}

  function startThinking() {{
    isThinking = true;
    targetProgress = 1.0;
    document.getElementById('chatTypingDots').style.display = 'flex';
    document.getElementById('chatAnswerText').style.display = 'none';
    document.getElementById('stageStatusPill').innerText = 'Denkvorgang aktiv (Morpht)';
  }}

  function stopThinking() {{
    isThinking = false;
    targetProgress = 0.0;
    document.getElementById('chatTypingDots').style.display = 'none';
    document.getElementById('chatAnswerText').style.display = 'block';
    document.getElementById('stageStatusPill').innerText = 'Ruhezustand (Echtes App-Logo)';
  }}

  function drawBlob(canvas, time) {{
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2;
    const cy = h / 2;
    const r0 = Math.min(w, h) * 0.38;
    const t = time * 0.0015 * 0.8;

    const breath = 1.0 + Math.sin(t * 1.6) * 0.05;
    const tilt = Math.sin(t * 1.2) * 0.06;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(tilt);
    ctx.scale(breath, breath);

    // Glow
    const glowGrad = ctx.createRadialGradient(0, 0, r0 * 0.3, 0, 0, r0 * 1.5);
    glowGrad.addColorStop(0, 'rgba(255, 152, 0, 0.40)');
    glowGrad.addColorStop(0.7, 'rgba(255, 87, 34, 0.18)');
    glowGrad.addColorStop(1, 'rgba(255, 87, 34, 0)');
    ctx.fillStyle = glowGrad;
    ctx.beginPath();
    ctx.arc(0, 0, r0 * 1.5, 0, Math.PI * 2);
    ctx.fill();

    // 5 Lobes
    const numLobes = 5;
    const baseAngles = [-76, -2, 68, 138, 208].map(d => d * Math.PI / 180);
    const points = [];

    for (let i = 0; i < numLobes * 2; i++) {{
      const lobeIdx = Math.floor(i / 2);
      const isPeak = (i % 2 === 0);
      let angle = baseAngles[lobeIdx];
      if (!isPeak) {{
        const nextIdx = (lobeIdx + 1) % numLobes;
        let a1 = baseAngles[lobeIdx];
        let a2 = baseAngles[nextIdx];
        if (a2 <= a1) a2 += Math.PI * 2;
        angle = (a1 + a2) / 2;
      }}
      const baseR = isPeak ? (r0 * 1.15) : (r0 * 0.88);
      const dyn = 1.0 + 0.20 * (
        0.15 * Math.sin(2 * angle + t * 2.2) +
        0.10 * Math.cos(3 * angle - t * 1.5) +
        0.06 * Math.sin(5 * angle + t * 2.8)
      );
      const r = baseR * dyn;
      points.push({{ x: r * Math.cos(angle), y: r * Math.sin(angle) }});
    }}

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    const n = points.length;
    for (let i = 0; i < n; i++) {{
      const pPrev = points[(i - 1 + n) % n];
      const pCurr = points[i];
      const pNext = points[(i + 1) % n];
      const pNext2 = points[(i + 2) % n];
      const c1x = pCurr.x + (pNext.x - pPrev.x) / 6;
      const c1y = pCurr.y + (pNext.y - pPrev.y) / 6;
      const c2x = pNext.x - (pNext2.x - pCurr.x) / 6;
      const c2y = pNext.y - (pNext2.y - pCurr.y) / 6;
      ctx.bezierCurveTo(c1x, c1y, c2x, c2y, pNext.x, pNext.y);
    }}
    ctx.closePath();

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

    const hx = lx + Math.cos(t * 1.5) * (r0 * 0.06);
    const hy = ly + Math.sin(t * 1.2) * (r0 * 0.06);
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

    if (Math.abs(targetProgress - transitionProgress) > 0.001) {{
      const speed = isThinking ? 4.0 : 3.2;
      transitionProgress += (targetProgress - transitionProgress) * Math.min(1.0, dt * speed);
    }} else {{
      transitionProgress = targetProgress;
    }}

    // Crossfade between static genuine logo and animated canvas
    const staticOpacity = 1.0 - transitionProgress;
    const canvasOpacity = transitionProgress;

    document.getElementById('stageStaticImg').style.opacity = staticOpacity;
    document.getElementById('stageCanvas').style.opacity = canvasOpacity;
    document.getElementById('miniStaticImg').style.opacity = staticOpacity;
    document.getElementById('miniCanvas').style.opacity = canvasOpacity;

    if (transitionProgress > 0.01) {{
      drawBlob(document.getElementById('stageCanvas'), now);
      drawBlob(document.getElementById('miniCanvas'), now);
    }}
    drawBlob(document.getElementById('compareFullCanvas'), now);

    requestAnimationFrame(animate);
  }}

  requestAnimationFrame(animate);
</script>

</body>
</html>
"""

with open(os.path.join(ANIMATION_DIR, "preview.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("Updated preview.html with genuine logo resting state!")
