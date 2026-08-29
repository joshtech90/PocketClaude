"""
Build Complete Suite of PocketClot Logo Variants & App Icons.
Generates 6 distinct, mathematically refined logo options fixing the bottom-right cutout defect.
"""
import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ANIMATION_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(ANIMATION_DIR, "icons")
os.makedirs(ICONS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Smooth minimum function for SDF metaball blending
# -----------------------------------------------------------------------------
def smin(a, b, k=0.16):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)

# -----------------------------------------------------------------------------
# Dark Midnight Navy Background for Launcher Icons
# -----------------------------------------------------------------------------
def make_launcher_bg(size=512, shape="squircle"):
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    y, x = np.ogrid[:size, :size]
    cx, cy = size / 2.0, size / 2.0
    dist = np.sqrt((x - cx)**2 + (y - cy)**2) / (size * 0.707)
    dist = np.clip(dist, 0.0, 1.0)
    
    # Gradient: #162447 in center -> #060914 at corners
    c_center = np.array([22, 36, 71, 255], dtype=np.float32)
    c_outer = np.array([6, 9, 20, 255], dtype=np.float32)
    
    canvas = np.zeros((size, size, 4), dtype=np.uint8)
    for ch in range(3):
        canvas[:, :, ch] = np.clip(c_center[ch] * (1.0 - dist) + c_outer[ch] * dist, 0, 255).astype(np.uint8)
    canvas[:, :, 3] = 255
    
    bg_img = Image.fromarray(canvas)
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    if shape == "squircle":
        radius = int(size * 0.225)
        mdraw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    elif shape == "round":
        mdraw.ellipse([0, 0, size - 1, size - 1], fill=255)
    else:
        mdraw.rectangle([0, 0, size - 1, size - 1], fill=255)
        
    bg_img.putalpha(mask)
    return bg_img

# -----------------------------------------------------------------------------
# Option 1: Original Restored (Clean inpainting of 96px original + supersampling)
# -----------------------------------------------------------------------------
def generate_opt1_original_restored():
    orig = Image.open(os.path.join(ANIMATION_DIR, "original_logo.png")).convert("RGBA")
    arr = np.array(orig).astype(np.float32)
    alpha = arr[:, :, 3]
    cx, cy = 47.04, 46.81
    
    # 720 angle raymarching
    angles = np.linspace(0, 2*np.pi, 720, endpoint=False)
    radii = np.zeros(720)
    for i, a in enumerate(angles):
        for r in np.linspace(0, 48, 500):
            x = int(cx + r * np.cos(a))
            y = int(cy + r * np.sin(a))
            if x < 0 or x >= 96 or y < 0 or y >= 96 or alpha[y, x] < 128:
                radii[i] = r
                break
        else:
            radii[i] = 48
            
    # Interpolate defect at angles 42° to 78°
    idx_start = int(720 * 42 / 360)
    idx_end = int(720 * 78 / 360)
    r_start = radii[idx_start]
    r_end = radii[idx_end]
    
    for i in range(idx_start, idx_end):
        t = (i - idx_start) / (idx_end - idx_start)
        h00 = 2*t**3 - 3*t**2 + 1
        h01 = -2*t**3 + 3*t**2
        radii[i] = h00 * r_start + h01 * r_end - 4.5 * np.sin(np.pi * t)
        
    W = 1024
    scale = W / 96.0
    cx_large = cx * scale
    cy_large = cy * scale
    
    y_grid, x_grid = np.ogrid[:W, :W]
    dx = x_grid - cx_large
    dy = y_grid - cy_large
    dist_grid = np.sqrt(dx**2 + dy**2)
    angle_grid = np.arctan2(dy, dx) % (2 * np.pi)
    
    angle_idx = (angle_grid / (2 * np.pi) * 720).astype(int) % 720
    target_r = radii[angle_idx] * scale
    
    sdf = dist_grid - target_r
    alpha_1024 = np.clip(0.5 - sdf / 2.0, 0.0, 1.0)
    
    color_large = orig.resize((W, W), Image.Resampling.BICUBIC)
    c_arr = np.array(color_large).astype(np.float32)
    old_alpha_large = np.array(orig.split()[3].resize((W, W), Image.Resampling.BICUBIC)).astype(np.float32) / 255.0
    
    defect_mask = (alpha_1024 > 0.05) & (old_alpha_large < 0.8) & (dx > 0) & (dy > 0)
    for y in range(W):
        for x in range(W):
            if defect_mask[y, x]:
                ang = angle_grid[y, x]
                r_sample = max(0, dist_grid[y, x] - 40)
                sx = int(np.clip(cx_large + r_sample * np.cos(ang), 0, W-1))
                sy = int(np.clip(cy_large + r_sample * np.sin(ang), 0, W-1))
                c_arr[y, x, :3] = c_arr[sy, sx, :3] * 0.96
                
    c_arr[:, :, 3] = alpha_1024 * 255.0
    
    # Smooth outer boundary feather
    res = Image.fromarray(c_arr.astype(np.uint8))
    return res

# -----------------------------------------------------------------------------
# Generic SDF Clay Blob Renderer
# -----------------------------------------------------------------------------
def render_metaball_clay(
    size=1024,
    lobes_def=None,
    core_radius=0.48,
    blend_k=0.15,
    color_stops=None,
    specular_pos=(-0.22, -0.25),
    specular_size=0.35,
    specular_shine=0.55,
    ambient_occlusion=0.25,
    subsurface_glow=0.16,
    light_dir=(-0.42, -0.62, 0.66)
):
    W = size
    y_grid, x_grid = np.ogrid[:W, :W]
    cx, cy = W / 2.0, W / 2.0
    nx = (x_grid - cx) / (W * 0.40)
    ny = (y_grid - cy) / (W * 0.40)
    
    # Central core
    d = np.sqrt(nx**2 + ny**2) - core_radius
    
    # Blend outer lobes
    for deg, dist, r_lobe in lobes_def:
        rad = math.radians(deg)
        lx = dist * math.cos(rad)
        ly = dist * math.sin(rad)
        dl = np.sqrt((nx - lx)**2 + (ny - ly)**2) - r_lobe
        d = smin(d, dl, k=blend_k)
        
    pixel_scale = 1.0 / (W * 0.40)
    alpha = np.clip(0.5 - d / (pixel_scale * 1.5), 0.0, 1.0)
    
    inside = np.maximum(0.0, -d)
    z = np.power(np.clip(inside / 0.50, 0.0, 1.0), 0.54)
    
    # Gradient coords
    t_grad = np.clip((nx * 0.45 + ny * 0.55 + 0.50) / 1.15, 0.0, 1.0)
    
    # Interpolate colors
    c_top, c_hl, c_mid, c_deep, c_shd = color_stops
    rgb = np.zeros((W, W, 3), dtype=np.float32)
    
    for c in range(3):
        m1 = t_grad < 0.25
        t1 = t_grad / 0.25
        rgb[m1, c] = c_top[c] * (1.0 - t1[m1]) + c_hl[c] * t1[m1]
        
        m2 = (t_grad >= 0.25) & (t_grad < 0.65)
        t2 = (t_grad - 0.25) / 0.40
        rgb[m2, c] = c_hl[c] * (1.0 - t2[m2]) + c_mid[c] * t2[m2]
        
        m3 = (t_grad >= 0.65) & (t_grad < 0.88)
        t3 = (t_grad - 0.65) / 0.23
        rgb[m3, c] = c_mid[c] * (1.0 - t3[m3]) + c_deep[c] * t3[m3]
        
        m4 = t_grad >= 0.88
        t4 = (t_grad - 0.88) / 0.12
        rgb[m4, c] = c_deep[c] * (1.0 - t4[m4]) + c_shd[c] * t4[m4]
        
    # Specular shine
    sp_x, sp_y = specular_pos
    dist_spec = np.sqrt((nx - sp_x)**2 + (ny - sp_y)**2)
    shine = np.exp(-(dist_spec**2) / (specular_size**2)) * z * specular_shine
    for c in range(3):
        rgb[:, :, c] = rgb[:, :, c] * (1.0 - shine) + 255.0 * shine
        
    # Ambient occlusion
    rim_ao = np.power(np.clip(inside / 0.22, 0.0, 1.0), 0.38)
    for c in range(3):
        rgb[:, :, c] *= (1.0 - ambient_occlusion + ambient_occlusion * rim_ao)
        
    # Subsurface scattering
    if subsurface_glow > 0:
        r_core = np.sqrt(nx**2 + ny**2)
        glow = np.exp(-(r_core**2) / 0.40) * subsurface_glow
        rgb[:, :, 0] = np.clip(rgb[:, :, 0] + glow * 40.0, 0, 255)
        rgb[:, :, 1] = np.clip(rgb[:, :, 1] + glow * 20.0, 0, 255)
        
    out_arr = np.zeros((W, W, 4), dtype=np.uint8)
    for c in range(3):
        out_arr[:, :, c] = np.clip(rgb[:, :, c], 0, 255).astype(np.uint8)
    out_arr[:, :, 3] = (alpha * 255.0).astype(np.uint8)
    
    return Image.fromarray(out_arr)

# -----------------------------------------------------------------------------
# Color Palettes
# -----------------------------------------------------------------------------
PALETTE_CLASSIC = [
    np.array([255, 228, 140], dtype=np.float32), # Top #FFE48C
    np.array([255, 202, 40], dtype=np.float32),  # Gold #FFCA28
    np.array([255, 122, 0], dtype=np.float32),   # Amber Orange #FF7A00
    np.array([244, 81, 30], dtype=np.float32),   # Deep Orange #F4511E
    np.array([191, 54, 12], dtype=np.float32),   # Terracotta #BF360C
]

PALETTE_VIBRANT = [
    np.array([255, 245, 180], dtype=np.float32), # Solar highlight
    np.array([255, 193, 7], dtype=np.float32),   # Radiant Amber
    np.array([255, 95, 0], dtype=np.float32),    # Vivid Tangerine
    np.array([221, 44, 0], dtype=np.float32),    # Warm Flame
    np.array([168, 20, 10], dtype=np.float32),   # Rich Crimson Core
]

PALETTE_MINIMAL = [
    np.array([255, 235, 160], dtype=np.float32),
    np.array([255, 210, 60], dtype=np.float32),
    np.array([255, 138, 20], dtype=np.float32),
    np.array([238, 90, 20], dtype=np.float32),
    np.array([200, 60, 10], dtype=np.float32),
]

# -----------------------------------------------------------------------------
# Generate All 6 Curated Options
# -----------------------------------------------------------------------------
def build_all_options():
    options = {}
    
    # 1. Option 1: Original Restored
    print("Building Option 1: Original Restored...")
    opt1_img = generate_opt1_original_restored()
    options["opt1_original_restored"] = {
        "id": "opt1",
        "title": "Option 1: Original Restored (Original-Treue Reparatur)",
        "badge": "100% Original-Form",
        "summary": "Exakte 1:1 Beibehaltung des bisherigen Logos, jedoch mit mathematisch glatt rekonstruierter Bogenführung an der defekten Ecke (5:30 Uhr).",
        "details": [
            "Beseitigt die ausgefranste Kerbe unten rechts vollständig",
            "Behält alle vertrauten Asymmetrien und Eigenheiten des Originals bei",
            "Supersampled auf 1024x1024 mit sauberem Anti-Aliasing"
        ],
        "image": opt1_img,
        "lobes": 5,
        "recommended": False
    }
    
    # 2. Option 2: Harmonized Organic 5-Lobe Clay (RECOMMENDED)
    print("Building Option 2: Harmonized Organic 5-Lobe Clay (Recommended)...")
    lobes_v2 = [
        (-76.0, 0.44, 0.37), # Top lobe
        (-2.0,  0.43, 0.38), # Top-right lobe
        (68.0,  0.42, 0.38), # Bottom-right lobe (clean & smooth)
        (138.0, 0.43, 0.39), # Bottom-left lobe
        (208.0, 0.41, 0.37), # Top-left lobe
    ]
    opt2_img = render_metaball_clay(
        size=1024,
        lobes_def=lobes_v2,
        core_radius=0.48,
        blend_k=0.15,
        color_stops=PALETTE_CLASSIC,
        specular_pos=(-0.22, -0.25),
        specular_size=0.36,
        specular_shine=0.55,
        ambient_occlusion=0.26,
        subsurface_glow=0.16
    )
    options["opt2_harmonized_5lobe"] = {
        "id": "opt2",
        "title": "Option 2: Harmonized Organic 5-Lobe Clay (Harmonischer Knet-Klassiker)",
        "badge": "⭐ Empfehlung",
        "summary": "Das Beste aus beiden Welten: Bewahrt die organische, leicht geneigte 5-Lappen-PocketClot-Silhouette, modelliert sie aber als makellosen, plastischen 3D-Knet-Körper.",
        "details": [
            "Perfekt glatte, C²-stetige Übergänge an allen 5 Bögen (keine Kanten mehr)",
            "Samtiges 3D-Claymorphism-Volumen mit 55% Glanzpunkt oben links",
            "Harmonischer warmer Farbverlauf von Sonnengold bis Terrakotta",
            "Optimal abgestimmt für App-Icon, Launcher und Chat-Header"
        ],
        "image": opt2_img,
        "lobes": 5,
        "recommended": True
    }
    
    # 3. Option 3: Dynamic 6-Lobe Thinking Continuity
    print("Building Option 3: Dynamic 6-Lobe Thinking Continuity...")
    lobes_v3 = [
        (-90.0, 0.43, 0.36), # Top
        (-30.0, 0.43, 0.36), # Top-right
        (30.0,  0.43, 0.36), # Bottom-right
        (90.0,  0.43, 0.36), # Bottom
        (150.0, 0.43, 0.36), # Bottom-left
        (210.0, 0.43, 0.36), # Top-left
    ]
    opt3_img = render_metaball_clay(
        size=1024,
        lobes_def=lobes_v3,
        core_radius=0.47,
        blend_k=0.14,
        color_stops=PALETTE_CLASSIC,
        specular_pos=(-0.22, -0.25),
        specular_size=0.35,
        specular_shine=0.55,
        ambient_occlusion=0.25,
        subsurface_glow=0.18
    )
    options["opt3_thinking_6lobe"] = {
        "id": "opt3",
        "title": "Option 3: Dynamic 6-Lobe Thinking Continuity (Einheit mit Denkanimation)",
        "badge": "Animations-Konsistenz",
        "summary": "Exakt auf die 6-Lobe Thinking-Animation (PocketThinkingBlob.kt) abgestimmt. Statisches Logo und Streaming-Animation teilen dieselbe Geometrie.",
        "details": [
            "100% visuelle Kontinuität beim Übergang vom Ruhezustand ins Denken",
            "6 harmonisch verteilte Lobes mit samtiger Knet-Beleuchtung",
            "Kein Form- oder Zackensprung beim Start des Live-Streams"
        ],
        "image": opt3_img,
        "lobes": 6,
        "recommended": False
    }
    
    # 4. Option 4: Vibrant Neo-Clay 3D / Sunset Glow
    print("Building Option 4: Vibrant Neo-Clay 3D...")
    opt4_img = render_metaball_clay(
        size=1024,
        lobes_def=lobes_v2,
        core_radius=0.48,
        blend_k=0.15,
        color_stops=PALETTE_VIBRANT,
        specular_pos=(-0.24, -0.26),
        specular_size=0.32,
        specular_shine=0.62,
        ambient_occlusion=0.32,
        subsurface_glow=0.26
    )
    options["opt4_vibrant_neoclay"] = {
        "id": "opt4",
        "title": "Option 4: Vibrant Neo-Clay 3D (Satter Kontrast & Tiefen-Glow)",
        "badge": "Plastische Tiefe",
        "summary": "Gesteigerte Farbsättigung mit ausgeprägterem 3D-Glanzpunkt und Subsurface-Scattering-Lichtdurchlässigkeit für hohe Kontraste auf OLED-Displays.",
        "details": [
            "Intensiver Farbverlauf (Champagnergold bis Karmesin)",
            "Betonter Glanzpunkt und tiefe Randschattierung für maximale Plastizität",
            "Sticht auf dunklen Homescreens besonders leuchtend hervor"
        ],
        "image": opt4_img,
        "lobes": 5,
        "recommended": False
    }
    
    # 5. Option 5: Symmetric 5-Lobe Flower-Blob
    print("Building Option 5: Symmetric 5-Lobe...")
    lobes_v5 = [
        (-90.0, 0.42, 0.38),
        (-18.0, 0.42, 0.38),
        (54.0,  0.42, 0.38),
        (126.0, 0.42, 0.38),
        (198.0, 0.42, 0.38),
    ]
    opt5_img = render_metaball_clay(
        size=1024,
        lobes_def=lobes_v5,
        core_radius=0.48,
        blend_k=0.16,
        color_stops=PALETTE_CLASSIC,
        specular_pos=(-0.20, -0.24),
        specular_size=0.36,
        specular_shine=0.52,
        ambient_occlusion=0.24,
        subsurface_glow=0.15
    )
    options["opt5_symmetric_5lobe"] = {
        "id": "opt5",
        "title": "Option 5: Symmetric 5-Lobe Flower-Blob (Ausgewogene Symmetrie)",
        "badge": "Geometrisch Symmetrisch",
        "summary": "Vollständig symmetrische 5-Lappen-Geometrie mit aufrechtem oberen Bogen. Sehr geordnet, spielerisch und ruhig.",
        "details": [
            "Exakte 72-Grad-Winkelverteilung aller 5 Bögen",
            "Gleichmäßige Knetmassen-Radien ohne Neigungswinkel",
            "Klassisch-ruhiges Erscheinungsbild"
        ],
        "image": opt5_img,
        "lobes": 5,
        "recommended": False
    }
    
    # 6. Option 6: Modern Crisp Minimalist
    print("Building Option 6: Modern Crisp Minimalist...")
    opt6_img = render_metaball_clay(
        size=1024,
        lobes_def=lobes_v2,
        core_radius=0.50,
        blend_k=0.17,
        color_stops=PALETTE_MINIMAL,
        specular_pos=(-0.18, -0.20),
        specular_size=0.42,
        specular_shine=0.40,
        ambient_occlusion=0.16,
        subsurface_glow=0.10
    )
    options["opt6_modern_minimal"] = {
        "id": "opt6",
        "title": "Option 6: Modern Crisp Minimalist (Kompakt & Rasiermesserscharf)",
        "badge": "UI & Small-Size Fokus",
        "summary": "Dezent flachere Modellierung mit sanfterem Schattengradienten für maximale Lesbarkeit in sehr kleinen Größen (z.B. 24dp Statusleiste, Benachrichtigungen).",
        "details": [
            "Kompaktere Bögen für hohe Randschärfe auf Low-DPI Screens",
            "Sehr weicher, moderner Farbverlauf",
            "Subtiler Glanzpunkt für dezente Eleganz"
        ],
        "image": opt6_img,
        "lobes": 5,
        "recommended": False
    }
    
    # Export full asset bundles
    print("\nExporting icon files and launcher variations...")
    bg_squircle = make_launcher_bg(512, "squircle")
    bg_round = make_launcher_bg(512, "round")
    
    for key, data in options.items():
        var_dir = os.path.join(ICONS_DIR, key)
        os.makedirs(var_dir, exist_ok=True)
        
        img = data["image"]
        
        # 1. Master PNG 1024x1024
        img.save(os.path.join(var_dir, "brand_mark_1024.png"), "PNG")
        
        # 2. Web / Preview 512x512
        img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
        img_512.save(os.path.join(var_dir, "brand_mark_512.png"), "PNG")
        
        # 3. Android Brand Mark 192x192 & 96x96
        img_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
        img_192.save(os.path.join(var_dir, "brand_mark_192.png"), "PNG")
        img_96 = img.resize((96, 96), Image.Resampling.LANCZOS)
        img_96.save(os.path.join(var_dir, "brand_mark_96.png"), "PNG")
        
        # 4. App Launcher Squircle 512x512
        launcher_sq = bg_squircle.copy()
        fg_size = int(512 * 0.68)
        fg_scaled = img.resize((fg_size, fg_size), Image.Resampling.LANCZOS)
        pos = ((512 - fg_size) // 2, (512 - fg_size) // 2)
        launcher_sq.paste(fg_scaled, pos, fg_scaled)
        launcher_sq.save(os.path.join(var_dir, "app_launcher_squircle_512.png"), "PNG")
        
        # 5. App Launcher Round 512x512
        launcher_rd = bg_round.copy()
        launcher_rd.paste(fg_scaled, pos, fg_scaled)
        launcher_rd.save(os.path.join(var_dir, "app_launcher_round_512.png"), "PNG")
        
        # 6. Monochrome Silhouette 512x512
        mono_arr = np.array(img_512)
        mono_alpha = mono_arr[:, :, 3]
        mono_out = np.zeros((512, 512, 4), dtype=np.uint8)
        mono_out[:, :, :3] = 255
        mono_out[:, :, 3] = mono_alpha
        Image.fromarray(mono_out).save(os.path.join(var_dir, "ic_launcher_monochrome.png"), "PNG")
        
        print(f"  ✓ Exported {key} to {var_dir}")

    print("\nSuite built successfully!")
    return options

if __name__ == "__main__":
    build_all_options()
