import os

ANIMATION_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(ANIMATION_DIR)

radii_72 = [0.873, 0.8976, 0.9507, 0.9702, 0.9967, 1.007, 0.9835, 0.9651, 0.9446, 0.9027, 0.8342, 0.78, 0.7616, 0.7555, 0.8097, 0.8373, 0.8863, 0.8976, 0.915, 0.919, 0.9078, 0.9037, 0.871, 0.8925, 0.9344, 0.962, 0.9722, 0.9937, 0.9937, 0.9651, 0.9589, 0.916, 0.8833, 0.8373, 0.7994, 0.7913, 0.8301, 0.8761, 0.9078, 0.9252, 0.9334, 0.9395, 0.9344, 0.9098, 0.8618, 0.8434, 0.778, 0.7534, 0.7616, 0.7984, 0.8383, 0.8598, 0.9078, 0.919, 0.9364, 0.962, 0.9507, 0.9477, 0.9293, 0.869, 0.8362, 0.8056, 0.8342, 0.873, 0.9272, 0.962, 0.9589, 0.963, 0.9518, 0.9252, 0.8863, 0.8546]

radii_kt_str = ", ".join([f"{r}f" for r in radii_72])

kt_template = """package de.smartzone.pocketclaude.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * PocketThinkingBlob: Echter geometrischer Fluid-Uebergang fuer das PocketClot-Logo.
 *
 * Reinfließen & Zurueckfließen:
 * - Ruhezustand (isThinking = false): Exakt die unverfaelschte Silhouette des echten reparierten PocketClot-Logos.
 * - Start (isThinking -> true): Ueber 1200ms schwellen die Waber-Wellen organisch an (FastOutSlowInEasing),
 *   die Masse erwacht sichtbar und fließt weich in den lebendigen Thinking-Zustand.
 * - Ende (isThinking -> false): Ueber 1400ms daempfen die Wellen kontinuierlich ab, die Neigung
 *   beruhigt sich und das Logo fließt geschmeidig zurueck in seine exakte Ruheform.
 *
 * Verifizierte Parameter:
 * - speedMultiplier = 0.8f (Wobble-Geschwindigkeit 0.8x)
 * - morphIntensity = 0.20f (Morph-Intensitaet 20%)
 * - specularShine = 0.55f (3D-Glanzpunkt 55%)
 * - glowEnabled = true (Ambient Aura waehrend des Denkens)
 */
@Composable
fun PocketThinkingBlob(
    modifier: Modifier = Modifier,
    size: Dp = 25.dp,
    isThinking: Boolean = true,
    speedMultiplier: Float = 0.8f,
    morphIntensity: Float = 0.20f,
    specularShine: Float = 0.55f,
    glowEnabled: Boolean = true,
) {
    // Weiche, filmreife Transition ueber 1200ms / 1400ms
    val transitionProgress by animateFloatAsState(
        targetValue = if (isThinking) 1f else 0f,
        animationSpec = tween(
            durationMillis = if (isThinking) 1200 else 1400,
            easing = FastOutSlowInEasing,
        ),
        label = "FluidMorphTransitionProgress",
    )

    // Falls komplett im Ruhezustand und Transition beendet: Statische Vektor/Bitmap ohne Loop
    if (transitionProgress == 0f && !isThinking) {
        PocketBrandMark(modifier = modifier, size = size)
        return
    }

    val transition = rememberInfiniteTransition(label = "PocketThinkingBlobFluidInfinite")

    // Hauptphase fuer organische Wellenbewegung (0 bis 2*PI)
    val phase1 by transition.animateFloat(
        initialValue = 0f,
        targetValue = (2 * PI).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (2800 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "Phase1",
    )

    // Zweite gegenlaeufige Phase fuer Tiefen-Dynamik
    val phase2 by transition.animateFloat(
        initialValue = 0f,
        targetValue = (2 * PI).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (3900 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "Phase2",
    )

    // Sanfte Atembewegung (Skalierung)
    val rawBreathingScale by transition.animateFloat(
        initialValue = 0.95f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (1800 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "BreathingScale",
    )

    // Minimales Pendeln / Neigen
    val rawWobbleAngle by transition.animateFloat(
        initialValue = -3.5f,
        targetValue = 3.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (2400 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "WobbleAngle",
    )

    // Pulsierendes Ambient-Leuchten
    val rawGlowAlpha by transition.animateFloat(
        initialValue = 0.20f,
        targetValue = 0.50f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (1500 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "GlowAlpha",
    )

    val currentBreathingScale = 1.0f + (rawBreathingScale - 1.0f) * transitionProgress
    val currentWobbleAngle = rawWobbleAngle * transitionProgress
    val currentGlowAlpha = rawGlowAlpha * transitionProgress

    Box(
        modifier = modifier.size(size),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.matchParentSize()) {
            val center = Offset(this.size.width / 2f, this.size.height / 2f)
            val baseRadius = minOf(this.size.width, this.size.height) * 0.38f

            rotate(degrees = currentWobbleAngle, pivot = center) {
                scale(scale = currentBreathingScale, pivot = center) {
                    // 1. Ambient Glow (blendet weich ein und aus)
                    if (glowEnabled && currentGlowAlpha > 0.01f) {
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    Color(0xFFFF9800).copy(alpha = currentGlowAlpha * 0.42f),
                                    Color(0xFFFF5722).copy(alpha = currentGlowAlpha * 0.18f),
                                    Color.Transparent,
                                ),
                                center = center,
                                radius = baseRadius * 1.55f,
                            ),
                            radius = baseRadius * 1.55f,
                            center = center,
                        )
                    }

                    // 2. Continuous Fluid-Blob Path aus den 72 Polarkoordinaten des Original-Logos
                    val blobPath = createAuthenticFluidBlobPath(
                        center = center,
                        baseRadius = baseRadius,
                        phase1 = phase1,
                        phase2 = phase2,
                        morphIntensity = morphIntensity * transitionProgress,
                    )

                    // 3. 3D-Knetmassen Gradient-Fuellung
                    val lightSource = Offset(center.x - baseRadius * 0.35f, center.y - baseRadius * 0.35f)
                    val blobBrush = Brush.radialGradient(
                        colors = listOf(
                            Color(0xFFFDD043),
                            Color(0xFFFFB300),
                            Color(0xFFFF6D00),
                            Color(0xFFD84315),
                            Color(0xFFBF360C),
                        ),
                        center = lightSource,
                        radius = baseRadius * 1.55f,
                    )
                    drawPath(path = blobPath, brush = blobBrush)

                    // 4. Glanzpunkt (Specular Highlight)
                    if (specularShine > 0f) {
                        val highlightCenter = Offset(
                            center.x - baseRadius * 0.32f + (cos(phase1.toDouble()) * baseRadius * 0.05f * transitionProgress).toFloat(),
                            center.y - baseRadius * 0.32f + (sin(phase2.toDouble()) * baseRadius * 0.05f * transitionProgress).toFloat(),
                        )
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    Color.White.copy(alpha = 0.65f * specularShine),
                                    Color.White.copy(alpha = 0.20f * specularShine),
                                    Color.Transparent,
                                ),
                                center = highlightCenter,
                                radius = baseRadius * 0.45f,
                            ),
                            radius = baseRadius * 0.45f,
                            center = highlightCenter,
                        )
                    }
                }
            }
        }
    }
}

// 72 Polarradien exakt aus dem authentischen, reparierten PocketClot-Original-Logo
private val AUTHENTIC_RADII = floatArrayOf(""" + radii_kt_str + """)

/**
 * Erzeugt einen kontinuierlichen organischen Spline direkt aus den Original-Polarkoordinaten.
 * Bei morphIntensity = 0f entsteht exakt die unverfaelschte Original-Silhouette.
 */
private fun createAuthenticFluidBlobPath(
    center: Offset,
    baseRadius: Float,
    phase1: Float,
    phase2: Float,
    morphIntensity: Float = 0.20f,
): Path {
    val n = AUTHENTIC_RADII.size
    val points = ArrayList<Offset>(n)
    val angleStep = (2 * PI / n).toFloat()

    for (i in 0 until n) {
        val angle = i * angleStep
        val baseR = baseRadius * AUTHENTIC_RADII[i]

        val waveMod = 1.0f + morphIntensity * (
            0.16f * sin((2 * angle + phase1).toDouble()).toFloat() +
            0.11f * cos((3 * angle - phase2).toDouble()).toFloat() +
            0.06f * sin((5 * angle + phase1 * 0.7f).toDouble()).toFloat()
        )

        val r = baseR * waveMod
        val x = center.x + r * cos(angle.toDouble()).toFloat()
        val y = center.y + r * sin(angle.toDouble()).toFloat()
        points.add(Offset(x, y))
    }

    val path = Path()
    if (points.isEmpty()) return path

    path.moveTo(points[0].x, points[0].y)

    for (i in 0 until n) {
        val pPrev = points[(i - 1 + n) % n]
        val pCurr = points[i]
        val pNext = points[(i + 1) % n]
        val pNext2 = points[(i + 2) % n]

        val c1x = pCurr.x + (pNext.x - pPrev.x) / 6.0f
        val c1y = pCurr.y + (pNext.y - pPrev.y) / 6.0f
        val c2x = pNext.x - (pNext2.x - pCurr.x) / 6.0f
        val c2y = pNext.y - (pNext2.y - pCurr.y) / 6.0f

        path.cubicTo(c1x, c1y, c2x, c2y, pNext.x, pNext.y)
    }
    path.close()
    return path
}

@Preview(showBackground = true, backgroundColor = 0xFFF7F4EF)
@Composable
fun PocketThinkingBlobPreviewLight() {
    PocketThinkingBlob(size = 48.dp, isThinking = true)
}

@Preview(showBackground = true, backgroundColor = 0xFF1C1B1F)
@Composable
fun PocketThinkingBlobPreviewDark() {
    PocketThinkingBlob(size = 48.dp, isThinking = true)
}
"""

with open(os.path.join(ANIMATION_DIR, "PocketThinkingBlob.kt"), "w", encoding="utf-8") as f:
    f.write(kt_template)

app_target = os.path.join(PROJECT_DIR, "app/app/src/main/java/de/smartzone/pocketclaude/ui/components/PocketThinkingBlob.kt")
with open(app_target, "w", encoding="utf-8") as f:
    f.write(kt_template)

print("Updated PocketThinkingBlob.kt in Animation and Android app successfully!")
