"""
Generates the self-contained HTML decision document for PocketClot logo variants.
"""
import os
import base64

ANIMATION_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(ANIMATION_DIR)
HTML_DIR = os.path.join(PROJECT_DIR, "00 HTML")
os.makedirs(HTML_DIR, exist_ok=True)

def to_base64(filepath):
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        data = f.read()
    ext = os.path.splitext(filepath)[1].lower().replace(".", "")
    mime = "image/png" if ext == "png" else "image/svg+xml" if ext == "svg" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"

# Gather image base64s
orig_b64 = to_base64(os.path.join(ANIMATION_DIR, "original_logo.png"))

opts_data = [
    {
        "id": "opt2",
        "key": "opt2_harmonized_5lobe",
        "name": "Option 2: Harmonized Organic 5-Lobe Clay",
        "badge": "⭐ Empfehlung",
        "badge_class": "badge-rec",
        "tagline": "Ausbalancierter 3D-Knet-Klassiker mit weicher Kantenführung",
        "description": "Modelliert als samtiger Knetmassen-Körper mit C²-stetigen Bogenradien. Bewahrt die organische, leicht geneigte PocketClot-Silhouette, eliminiert alle Kanten und bietet perfekte 3D-Tiefe.",
        "pros": ["Makellos glatte Übergänge an allen 5 Bögen", "Warmer Goldgelb-Glanzpunkt (55%) oben links", "Optimale Silhouette für Launcher und Topbar"],
        "recommended": True
    },
    {
        "id": "opt1",
        "key": "opt1_original_restored",
        "name": "Option 1: Original Restored",
        "badge": "100% Original-Treue",
        "badge_class": "badge-neutral",
        "tagline": "Exakte Rekonstruktion des Original-Logos mit geschlossener Kerbe",
        "description": "Behält alle vertrauten Formen und Eigenheiten des bisherigen 96px-Logos 1:1 bei. Die ausgefranste Schnittkante bei 5:30 Uhr wurde mit stetiger Bézier-Interpolation repariert.",
        "pros": ["100% Wiedererkennungswert", "Beseitigt die störende Stufe an der rechten Flanke", "Supersampled für sauberes Anti-Aliasing"],
        "recommended": False
    },
    {
        "id": "opt3",
        "key": "opt3_thinking_6lobe",
        "name": "Option 3: Dynamic 6-Lobe Thinking Continuity",
        "badge": "Animations-Einheit",
        "badge_class": "badge-special",
        "tagline": "Volle visuelle Kontinuität mit der neuen Denkanimation",
        "description": "Exakt synchron zur neuen 6-Lobe-Thinking-Animation (PocketThinkingBlob.kt). Das statische Logo geht beim Beginn des Antwort-Streams nahtlos in die Waber-Bewegung über.",
        "pros": ["Kein Geometrie-Sprung beim Start des Antwort-Streams", "Moderne, harmonische 6-Lobe-Verteilung", "Plastische Clay-Beleuchtung"],
        "recommended": False
    },
    {
        "id": "opt4",
        "key": "opt4_vibrant_neoclay",
        "name": "Option 4: Vibrant Neo-Clay 3D",
        "badge": "Satter Kontrast",
        "badge_class": "badge-warm",
        "tagline": "Intensive Farbdynamik mit Sunset-Glow für OLED-Screens",
        "description": "Verstärkte Sättigung vom Champagnergold bis hin zu Karmesin-Terrakotta. Ausgeprägterer 3D-Volumenglanzpunkt und feiner Subsurface-Glow im Kern.",
        "pros": ["Leuchtstark auf dunklen Themes und OLED-Displays", "Besonders spürbare haptische 3D-Tiefe", "Hoher Kontrast im App Drawer"],
        "recommended": False
    },
    {
        "id": "opt5",
        "key": "opt5_symmetric_5lobe",
        "name": "Option 5: Symmetric 5-Lobe Flower-Blob",
        "badge": "Geometrisch Symmetrisch",
        "badge_class": "badge-neutral",
        "tagline": "Ruhige, gleichmäßige 72-Grad-Verteilung der Bögen",
        "description": "Klassisch-ruhige Symmetrie mit aufrechtem oberen Lobe. Keine Neigung, gleichmäßige Radien und sanfte Knet-Schattierung.",
        "pros": ["Sehr geordnete, ruhige Geometrie", "Gleichmäßige Radien", "Sanfter Farbverlauf"],
        "recommended": False
    },
    {
        "id": "opt6",
        "key": "opt6_modern_minimal",
        "name": "Option 6: Modern Crisp Minimalist",
        "badge": "UI & Small-Size Fokus",
        "badge_class": "badge-neutral",
        "tagline": "Kompakte Silhouette für maximale Schärfe in kleinen Größen",
        "description": "Reduzierte Tiefenkrümmung und kompaktere Bögen für maximale Lesbarkeit in 24dp Chat-Headern, Statusleisten und Benachrichtigungen.",
        "pros": ["Rasiermesserscharfe Kanten auf Low-DPI Screens", "Dezenter, moderner Farbverlauf", "Schlichte Eleganz"],
        "recommended": False
    }
]

for opt in opts_data:
    var_dir = os.path.join(ANIMATION_DIR, "icons", opt["key"])
    opt["brand_b64"] = to_base64(os.path.join(var_dir, "brand_mark_512.png"))
    opt["launcher_sq_b64"] = to_base64(os.path.join(var_dir, "app_launcher_squircle_512.png"))
    opt["launcher_rd_b64"] = to_base64(os.path.join(var_dir, "app_launcher_round_512.png"))

html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PocketClot · Logo & App-Icon Optimierung (Entscheidung)</title>
  <style>
    :root {{
      --bg-body: #F4F1EA;
      --bg-surface: #FFFFFF;
      --bg-surface-elevated: #FAF8F5;
      --text-main: #231F1A;
      --text-muted: #6E665D;
      --border-color: #E2DBD0;
      --border-focus: #E65100;
      --accent: #E65100;
      --accent-warm: #FF9800;
      --accent-light: #FFF3E0;
      --accent-glow: rgba(230, 81, 0, 0.25);
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      --radius: 14px;
      --radius-lg: 20px;
      --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.04);
      --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.08);
      --shadow-lg: 0 16px 40px rgba(0, 0, 0, 0.12);
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg-body: #12100E;
        --bg-surface: #1C1916;
        --bg-surface-elevated: #24201C;
        --text-main: #EFE9E1;
        --text-muted: #9E9386;
        --border-color: #332D26;
        --border-focus: #FF9800;
        --accent: #FF9800;
        --accent-warm: #FFA726;
        --accent-light: #2A1F14;
        --accent-glow: rgba(255, 152, 0, 0.20);
        --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
        --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.4);
        --shadow-lg: 0 16px 40px rgba(0, 0, 0, 0.6);
      }}
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: var(--font-family);
      background-color: var(--bg-body);
      color: var(--text-main);
      line-height: 1.5;
      padding: 32px 16px 120px 16px;
      display: flex;
      justify-content: center;
    }}

    .container {{
      max-width: 1040px;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 32px;
    }}

    header {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 28px 32px;
      box-shadow: var(--shadow-sm);
    }}

    .eyebrow {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--accent);
      margin-bottom: 6px;
    }}

    h1 {{
      font-size: 26px;
      font-weight: 800;
      color: var(--text-main);
      line-height: 1.25;
      margin-bottom: 12px;
    }}

    p.lead {{
      font-size: 15px;
      color: var(--text-muted);
      line-height: 1.6;
    }}

    /* Comparison Box */
    .defect-spotlight {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 24px 28px;
      box-shadow: var(--shadow-sm);
    }}

    .defect-spotlight h2 {{
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .spotlight-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}

    @media (max-width: 680px) {{
      .spotlight-grid {{ grid-template-columns: 1fr; }}
    }}

    .spotlight-card {{
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 12px;
    }}

    .spotlight-card.defect {{
      border-color: #E57373;
    }}

    .spotlight-card.fixed {{
      border-color: #81C784;
    }}

    .spotlight-preview {{
      width: 140px;
      height: 140px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }}

    .spotlight-preview img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      filter: drop-shadow(0 8px 16px rgba(0,0,0,0.12));
    }}

    .spotlight-badge {{
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 20px;
    }}

    .spotlight-badge.bad {{ background: #FFEBEE; color: #C62828; }}
    .spotlight-badge.good {{ background: #E8F5E9; color: #2E7D32; }}

    /* Options Section */
    .section-title {{
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 4px;
    }}

    .section-subtitle {{
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 18px;
    }}

    .options-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
      gap: 20px;
    }}

    .option-card {{
      background: var(--bg-surface);
      border: 2px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      box-shadow: var(--shadow-sm);
      transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
      cursor: pointer;
      position: relative;
    }}

    .option-card:hover {{
      transform: translateY(-3px);
      box-shadow: var(--shadow-md);
      border-color: var(--accent-warm);
    }}

    .option-card.selected {{
      border-color: var(--accent);
      background: var(--bg-surface-elevated);
      box-shadow: var(--shadow-md), 0 0 0 1px var(--accent);
    }}

    .option-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
    }}

    .option-title {{
      font-size: 16px;
      font-weight: 700;
      color: var(--text-main);
    }}

    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 12px;
      white-space: nowrap;
    }}

    .badge-rec {{ background: var(--accent); color: #FFFFFF; }}
    .badge-special {{ background: #7C4DFF; color: #FFFFFF; }}
    .badge-warm {{ background: #FF6D00; color: #FFFFFF; }}
    .badge-neutral {{ background: var(--border-color); color: var(--text-muted); }}

    .option-preview-box {{
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 20px;
    }}

    .option-preview-item {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }}

    .option-preview-item img {{
      width: 88px;
      height: 88px;
      object-fit: contain;
      filter: drop-shadow(0 6px 14px rgba(0,0,0,0.15));
    }}

    .option-preview-item .launcher-img {{
      border-radius: 19px;
      filter: drop-shadow(0 6px 14px rgba(0,0,0,0.25));
    }}

    .preview-label {{
      font-size: 11px;
      color: var(--text-muted);
      font-weight: 600;
    }}

    .option-desc {{
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.5;
    }}

    .option-bullets {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 5px;
      font-size: 12px;
      color: var(--text-main);
    }}

    .option-bullets li {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .option-bullets li::before {{
      content: "•";
      color: var(--accent);
      font-weight: bold;
    }}

    .radio-select-wrapper {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: auto;
      padding-top: 10px;
      border-top: 1px solid var(--border-color);
      font-size: 13px;
      font-weight: 600;
      color: var(--text-main);
    }}

    input[type="radio"], input[type="checkbox"] {{
      accent-color: var(--accent);
      width: 18px;
      height: 18px;
      cursor: pointer;
    }}

    /* Interactive Context Mockup */
    .context-preview-section {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 24px 28px;
      box-shadow: var(--shadow-sm);
    }}

    .mockup-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-top: 16px;
    }}

    @media (max-width: 768px) {{
      .mockup-grid {{ grid-template-columns: 1fr; }}
    }}

    .mockup-card {{
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    .mockup-header {{
      font-size: 13px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .mockup-chat-bubble {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .mockup-chat-header {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .mockup-chat-header img {{
      width: 25px;
      height: 25px;
    }}

    .mockup-chat-title {{
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: var(--accent);
    }}

    .mockup-chat-text {{
      font-size: 14px;
      color: var(--text-main);
      line-height: 1.45;
    }}

    .mockup-homescreen {{
      background: #0B0E14;
      border-radius: 24px;
      padding: 24px 16px;
      display: flex;
      justify-content: space-around;
      align-items: center;
    }}

    .homescreen-app {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
    }}

    .homescreen-app img {{
      width: 58px;
      height: 58px;
      border-radius: 14px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }}

    .homescreen-app span {{
      font-size: 11px;
      color: #E2E8F0;
      font-weight: 500;
    }}

    /* Decision Form */
    .decision-section {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 28px 32px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    .decision-point {{
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border-color);
    }}

    .decision-point:last-child {{
      border-bottom: none;
      padding-bottom: 0;
    }}

    .decision-label {{
      font-size: 15px;
      font-weight: 700;
      color: var(--text-main);
    }}

    .decision-options {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .decision-radio-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      cursor: pointer;
    }}

    textarea.comment-box {{
      width: 100%;
      min-height: 64px;
      padding: 10px 14px;
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      background: var(--bg-surface-elevated);
      color: var(--text-main);
      font-family: inherit;
      font-size: 13px;
      resize: vertical;
    }}

    textarea.comment-box:focus {{
      outline: none;
      border-color: var(--border-focus);
    }}

    /* Return Channel Sticky Bar */
    .return-channel {{
      position: sticky;
      bottom: 20px;
      background: var(--bg-surface);
      border: 2px solid var(--accent);
      border-radius: var(--radius-lg);
      padding: 16px 24px;
      box-shadow: var(--shadow-lg);
      display: flex;
      flex-direction: column;
      gap: 12px;
      z-index: 100;
    }}

    .copy-btn {{
      background: var(--accent);
      color: #FFFFFF;
      border: none;
      padding: 14px 24px;
      font-size: 16px;
      font-weight: 700;
      border-radius: var(--radius);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: background 0.2s, transform 0.1s;
    }}

    .copy-btn:hover {{
      background: #D84315;
    }}

    .copy-btn:active {{
      transform: scale(0.98);
    }}

    textarea.return-textarea {{
      width: 100%;
      height: 70px;
      padding: 8px 12px;
      font-family: monospace;
      font-size: 11px;
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      color: var(--text-muted);
      resize: none;
    }}
  </style>
</head>
<body>

<div class="container">

  <!-- Header -->
  <header>
    <div class="eyebrow">PocketClot · Design-Entscheidung</div>
    <h1>Statisches Logo & App-Icon Optimierung</h1>
    <p class="lead">
      Präzise Beseitigung des Schnittkanten-Defekts an der unteren rechten Ecke (5:30 Uhr)
      sowie 6 kuratierte, hochauflösende Vektor- und 3D-Knet-Varianten für das PocketClot-Markenzeichen.
    </p>
  </header>

  <!-- Defect Spotlight & Comparison -->
  <section class="defect-spotlight">
    <h2>🔍 Analyse des Defekts & Glättung</h2>
    <div class="spotlight-grid">
      <div class="spotlight-card defect">
        <span class="spotlight-badge bad">Bisheriger Zustand (Defekt)</span>
        <div class="spotlight-preview">
          <img src="{orig_b64}" alt="Original Logo Defekt" style="width: 120px; height: 120px;">
        </div>
        <p style="font-size: 13px; color: var(--text-muted);">
          <strong>Ausgefranste Stufe bei 5:30 Uhr:</strong> Zwischen dem unteren und dem rechten Bogen
          ist die Rundung abrupt unterbrochen (Maskierungs-Artefakt).
        </p>
      </div>

      <div class="spotlight-card fixed">
        <span class="spotlight-badge good">Repariert & Harmonisiert (Option 2)</span>
        <div class="spotlight-preview">
          <img id="spotlightTarget" src="{opts_data[0]['brand_b64']}" alt="Repariertes Logo" style="width: 120px; height: 120px;">
        </div>
        <p style="font-size: 13px; color: var(--text-muted);">
          <strong>C²-stetig gerundeter Übergang:</strong> Die Kerbe ist vollständig geschlossen,
          alle 5 Bögen gehen organisch ineinander über.
        </p>
      </div>
    </div>
  </section>

  <!-- Logo Variants Overview -->
  <section>
    <div class="section-title">🎨 Die 6 kuratierten Logo-Varianten</div>
    <div class="section-subtitle">Klicke eine Variante an, um sie auszuwählen und im Mockup zu sehen.</div>

    <div class="options-grid">
"""

for opt in opts_data:
    is_rec = opt["recommended"]
    sel_class = "selected" if is_rec else ""
    checked_attr = "checked" if is_rec else ""
    
    html_content += f"""
      <div class="option-card {sel_class}" id="card_{opt['id']}" onclick="selectOption('{opt['id']}', '{opt['brand_b64']}', '{opt['launcher_sq_b64']}')">
        <div class="option-header">
          <div class="option-title">{opt['name']}</div>
          <span class="badge {opt['badge_class']}">{opt['badge']}</span>
        </div>

        <div class="option-preview-box">
          <div class="option-preview-item">
            <img src="{opt['brand_b64']}" alt="{opt['name']} Brand Mark">
            <span class="preview-label">Brand Mark</span>
          </div>
          <div class="option-preview-item">
            <img src="{opt['launcher_sq_b64']}" class="launcher-img" alt="{opt['name']} Launcher">
            <span class="preview-label">Launcher Icon</span>
          </div>
        </div>

        <p class="option-desc">{opt['description']}</p>

        <ul class="option-bullets">
          {''.join([f'<li>{p}</li>' for p in opt['pros']])}
        </ul>

        <div class="radio-select-wrapper">
          <input type="radio" name="logo_variant" id="radio_{opt['id']}" value="{opt['name']}" {checked_attr} onchange="onRadioChange('{opt['id']}')">
          <label for="radio_{opt['id']}">Diese Variante wählen</label>
        </div>
      </div>
    """

html_content += f"""
    </div>
  </section>

  <!-- Interactive Context Mockups -->
  <section class="context-preview-section">
    <div class="section-title">📱 Live-Vorschau im System-Kontext</div>
    <div class="section-subtitle">So wirkt deine ausgewählte Variante direkt in der App und auf dem Android-Homescreen:</div>

    <div class="mockup-grid">
      <!-- Chat Bubble Mockup -->
      <div class="mockup-card">
        <div class="mockup-header">App Chat-Header (Ruhezustand)</div>
        <div class="mockup-chat-bubble">
          <div class="mockup-chat-header">
            <img id="mockupChatLogo" src="{opts_data[0]['brand_b64']}" alt="Chat Brand Mark">
            <span class="mockup-chat-title">POCKETCLOT</span>
          </div>
          <div class="mockup-chat-text">
            Hallo Joscha, ich bin bereit für die nächste Aufgabe. Wie gefällt dir das optimierte Markenzeichen?
          </div>
        </div>
      </div>

      <!-- Homescreen Launcher Mockup -->
      <div class="mockup-card">
        <div class="mockup-header">Android Homescreen / App Drawer</div>
        <div class="mockup-homescreen">
          <div class="homescreen-app">
            <img id="mockupHomescreenLogo" src="{opts_data[0]['launcher_sq_b64']}" alt="Launcher Icon">
            <span>PocketClot</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Decision Form Section -->
  <section class="decision-section">
    <div class="section-title">📋 Deine Entscheidung</div>

    <!-- Punkt 1 -->
    <div class="decision-point">
      <div class="decision-label">1. Bevorzugte Logo-Variante</div>
      <div class="decision-options">
        <label class="decision-radio-row">
          <input type="radio" name="dec_variant" value="Option 2 (Harmonized 5-Lobe Clay - Empfehlung)" checked onchange="syncDecisionRadio('opt2')">
          <span><strong>Option 2: Harmonized Organic 5-Lobe Clay</strong> (Empfehlung: Perfekt glatte Bogenradien & weicher 3D-Knet-Look)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_variant" value="Option 1 (Original Restored)" onchange="syncDecisionRadio('opt1')">
          <span><strong>Option 1: Original Restored</strong> (100% Original-Treue mit C²-glatter Reparatur)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_variant" value="Option 3 (Dynamic 6-Lobe Thinking Continuity)" onchange="syncDecisionRadio('opt3')">
          <span><strong>Option 3: Dynamic 6-Lobe Thinking Continuity</strong> (Volle Einheit mit Denkanimation)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_variant" value="Option 4 (Vibrant Neo-Clay 3D)" onchange="syncDecisionRadio('opt4')">
          <span><strong>Option 4: Vibrant Neo-Clay 3D</strong> (Satter Kontrast & Sunset-Glow)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_variant" value="Option 5 (Symmetric 5-Lobe Flower-Blob)" onchange="syncDecisionRadio('opt5')">
          <span><strong>Option 5: Symmetric 5-Lobe Flower-Blob</strong> (Geometrisch streng symmetrisch)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_variant" value="Option 6 (Modern Crisp Minimalist)" onchange="syncDecisionRadio('opt6')">
          <span><strong>Option 6: Modern Crisp Minimalist</strong> (Kompakt & rasiermesserscharf)</span>
        </label>
      </div>
      <textarea class="comment-box" id="comment_variant" placeholder="Notiz oder Detailwunsch zur gewählten Variante..." oninput="updateSerializedMarkdown()"></textarea>
    </div>

    <!-- Punkt 2 -->
    <div class="decision-point">
      <div class="decision-label">2. Homescreen Launcher-Icon Stil</div>
      <div class="decision-options">
        <label class="decision-radio-row">
          <input type="radio" name="dec_launcher_style" value="Squircle (Abgerundetes Quadrat - Empfehlung)" checked onchange="updateSerializedMarkdown()">
          <span><strong>Squircle</strong> (Standard Android / OneUI / iOS Formfaktor mit sanftem Mitternachtsblau-Verlauf)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_launcher_style" value="Round (Reiner Kreis)" onchange="updateSerializedMarkdown()">
          <span><strong>Round</strong> (Pixel Launcher Kreis-Maske)</span>
        </label>
      </div>
      <textarea class="comment-box" id="comment_launcher" placeholder="Notiz zum Launcher-Icon..." oninput="updateSerializedMarkdown()"></textarea>
    </div>

    <!-- Punkt 3 -->
    <div class="decision-point">
      <div class="decision-label">3. Nächster Umsetzungsschritt</div>
      <div class="decision-options">
        <label class="decision-radio-row">
          <input type="radio" name="dec_action" value="Assets direkt in Android-App integrieren (Empfehlung)" checked onchange="updateSerializedMarkdown()">
          <span><strong>Direkt in Android-App integrieren</strong> (Ressourcen in res/drawable und res/mipmap austauschen)</span>
        </label>
        <label class="decision-radio-row">
          <input type="radio" name="dec_action" value="Noch weitere Feinjustierung am Modell vornehmen" onchange="updateSerializedMarkdown()">
          <span><strong>Noch weitere Feinjustierung vornehmen</strong> (z.B. Farben, Glanzpunkt oder Lobe-Tiefe anpassen)</span>
        </label>
      </div>
      <textarea class="comment-box" id="comment_action" placeholder="Notiz zu weiteren Schritten..." oninput="updateSerializedMarkdown()"></textarea>
    </div>

    <!-- Global Feedback -->
    <div class="decision-point">
      <div class="decision-label">💬 Globales Feedback & Anmerkungen</div>
      <textarea class="comment-box" id="comment_global" style="min-height: 80px;" placeholder="Möchtest du noch etwas anpassen oder hast du weitere Ideen?" oninput="updateSerializedMarkdown()"></textarea>
    </div>
  </section>

  <!-- Sticky Return Channel -->
  <div class="return-channel">
    <button class="copy-btn" id="copyBtn" onclick="copyResult()">
      <span>✅</span> Ergebnis kopieren
    </button>
    <textarea class="return-textarea" id="returnTextarea" readonly></textarea>
  </div>

</div>

<script>
  let currentSelectedId = 'opt2';

  function selectOption(optId, brandB64, launcherB64) {{
    currentSelectedId = optId;

    // Update cards
    document.querySelectorAll('.option-card').forEach(card => card.classList.remove('selected'));
    const card = document.getElementById('card_' + optId);
    if (card) card.classList.add('selected');

    // Update inner radio
    const radio = document.getElementById('radio_' + optId);
    if (radio) radio.checked = true;

    // Update decision form radio
    const decRadios = document.getElementsByName('dec_variant');
    for (let r of decRadios) {{
      if (r.value.toLowerCase().includes(optId.replace('opt', 'option '))) {{
        r.checked = true;
      }}
    }}

    // Update mockups & spotlight
    if (brandB64) {{
      document.getElementById('spotlightTarget').src = brandB64;
      document.getElementById('mockupChatLogo').src = brandB64;
    }}
    if (launcherB64) {{
      document.getElementById('mockupHomescreenLogo').src = launcherB64;
    }}

    updateSerializedMarkdown();
  }}

  function onRadioChange(optId) {{
    const card = document.getElementById('card_' + optId);
    if (card) card.click();
  }}

  function syncDecisionRadio(optId) {{
    const card = document.getElementById('card_' + optId);
    if (card) card.click();
  }}

  function getSelectedRadio(name) {{
    const radios = document.getElementsByName(name);
    for (let r of radios) {{
      if (r.checked) return r.value;
    }}
    return "";
  }}

  function updateSerializedMarkdown() {{
    const variant = getSelectedRadio('dec_variant');
    const commVariant = document.getElementById('comment_variant').value.trim();
    const launcher = getSelectedRadio('dec_launcher_style');
    const commLauncher = document.getElementById('comment_launcher').value.trim();
    const action = getSelectedRadio('dec_action');
    const commAction = document.getElementById('comment_action').value.trim();
    const commGlobal = document.getElementById('comment_global').value.trim();

    let md = "### PocketClot Logo & App-Icon Entscheidung\\n\\n";
    md += "1. **Logo-Variante:** " + variant + "\\n";
    if (commVariant) md += "   *Kommentar:* " + commVariant + "\\n";
    
    md += "2. **Launcher-Icon Stil:** " + launcher + "\\n";
    if (commLauncher) md += "   *Kommentar:* " + commLauncher + "\\n";
    
    md += "3. **Umsetzungsschritt:** " + action + "\\n";
    if (commAction) md += "   *Kommentar:* " + commAction + "\\n";

    if (commGlobal) {{
      md += "\\n**Globales Feedback:**\\n" + commGlobal + "\\n";
    }}

    document.getElementById('returnTextarea').value = md;
  }}

  function copyResult() {{
    updateSerializedMarkdown();
    const textarea = document.getElementById('returnTextarea');
    textarea.select();
    navigator.clipboard.writeText(textarea.value).then(() => {{
      const btn = document.getElementById('copyBtn');
      const oldHtml = btn.innerHTML;
      btn.innerHTML = "<span>🎉</span> Kopiert!";
      btn.style.background = "#2E7D32";
      setTimeout(() => {{
        btn.innerHTML = oldHtml;
        btn.style.background = "var(--accent)";
      }}, 2000);
    }}).catch(() => {{
      document.execCommand('copy');
    }});
  }}

  // Initialize
  window.addEventListener('DOMContentLoaded', () => {{
    updateSerializedMarkdown();
  }});
</script>

</body>
</html>
"""

target_html = os.path.join(HTML_DIR, "2026-08-24_1825_pocketclot_logo_varianten.html")
with open(target_html, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML decision file created at: {target_html}")
