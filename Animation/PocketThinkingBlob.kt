package de.smartzone.pocketclaude.ui.components

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
 * PocketThinkingBlob: 3D-Knetmassen Thinking-Animation mit exakten PocketClot-Original-Proportionen.
 *
 * - Ruhezustand (isThinking = false): Exakt die 5 Boegen und Taeler der echten PocketClot-Silhouette.
 * - Reinfließen (isThinking -> true): Die 5 Boegen schwellen ueber 1200ms in organische 3D-Waber-Wellen an,
 *   die Glanzpunkte wandern dynamisch ueber die Knetmasse und die Ambient-Aura blueht weich auf.
 * - Zurueckfließen (isThinking -> false): Die 3D-Wellen klingen ueber 1400ms ab und die Masse fließt
 *   nahtlos zurueck in die exakte Original-Silhouette.
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
    val transitionProgress by animateFloatAsState(
        targetValue = if (isThinking) 1f else 0f,
        animationSpec = tween(
            durationMillis = if (isThinking) 1200 else 1400,
            easing = FastOutSlowInEasing,
        ),
        label = "PocketThinkingBlob3DProgress",
    )

    // Falls komplett im Ruhezustand und Transition beendet: Statische Marken-Komponente
    if (transitionProgress == 0f && !isThinking) {
        PocketBrandMark(modifier = modifier, size = size)
        return
    }

    val transition = rememberInfiniteTransition(label = "PocketThinkingBlob3DInfinite")

    val phase1 by transition.animateFloat(
        initialValue = 0f,
        targetValue = (2 * PI).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (2800 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "Phase1",
    )

    val phase2 by transition.animateFloat(
        initialValue = 0f,
        targetValue = (2 * PI).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (3900 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "Phase2",
    )

    val rawBreathingScale by transition.animateFloat(
        initialValue = 0.95f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (1800 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "BreathingScale",
    )

    val rawWobbleAngle by transition.animateFloat(
        initialValue = -3.5f,
        targetValue = 3.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = (2400 / speedMultiplier).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "WobbleAngle",
    )

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
            val baseRadius = minOf(this.size.width, this.size.height) * 0.36f

            rotate(degrees = currentWobbleAngle, pivot = center) {
                scale(scale = currentBreathingScale, pivot = center) {
                    // 1. Ambient Aura
                    if (glowEnabled && currentGlowAlpha > 0.01f) {
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    Color(0xFFFF9800).copy(alpha = currentGlowAlpha * 0.42f),
                                    Color(0xFFFF5722).copy(alpha = currentGlowAlpha * 0.18f),
                                    Color.Transparent,
                                ),
                                center = center,
                                radius = baseRadius * 1.60f,
                            ),
                            radius = baseRadius * 1.60f,
                            center = center,
                        )
                    }

                    // 2. 3D Knetmassen-Path mit PocketClot-Proportionen
                    val blobPath = create3DClayBlobPath(
                        center = center,
                        baseRadius = baseRadius,
                        phase1 = phase1,
                        phase2 = phase2,
                        morphProgress = transitionProgress,
                        morphIntensity = morphIntensity,
                    )

                    // 3. 3D-Knetmassen Gradient
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

                    // 4. Glanzpunkt (Specular Clay Highlight)
                    if (specularShine > 0f) {
                        val highlightCenter = Offset(
                            center.x - baseRadius * 0.32f + (cos(phase1.toDouble()) * baseRadius * 0.06f * transitionProgress).toFloat(),
                            center.y - baseRadius * 0.32f + (sin(phase2.toDouble()) * baseRadius * 0.06f * transitionProgress).toFloat(),
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

// 10 Kontrollpunkte: 5 Boegen + 5 Taeler exakt kalibriert aus dem PocketClot-Original
private val CONTROL_ANGLES = floatArrayOf(
    (25.0 * PI / 180.0).toFloat(),  // Bogen 1 (Oben-Rechts)
    (60.0 * PI / 180.0).toFloat(),  // Tal 1 (Reparierte Kante)
    (92.0 * PI / 180.0).toFloat(),  // Bogen 2 (Unten-Rechts)
    (112.0 * PI / 180.0).toFloat(), // Tal 2
    (140.0 * PI / 180.0).toFloat(), // Bogen 3 (Unten)
    (172.0 * PI / 180.0).toFloat(), // Tal 3
    (205.0 * PI / 180.0).toFloat(), // Bogen 4 (Links)
    (240.0 * PI / 180.0).toFloat(), // Tal 4
    (280.0 * PI / 180.0).toFloat(), // Bogen 5 (Oben-Links)
    (335.0 * PI / 180.0).toFloat(), // Tal 5
)

private val CONTROL_RADII = floatArrayOf(
    1.233f, 0.944f, 1.134f, 1.078f, 1.230f, 0.990f, 1.157f, 0.944f, 1.177f, 1.033f
)

private fun create3DClayBlobPath(
    center: Offset,
    baseRadius: Float,
    phase1: Float,
    phase2: Float,
    morphProgress: Float,
    morphIntensity: Float = 0.20f,
): Path {
    val n = CONTROL_ANGLES.size
    val points = ArrayList<Offset>(n)

    for (i in 0 until n) {
        val angle = CONTROL_ANGLES[i]
        val baseR = baseRadius * CONTROL_RADII[i]

        val wave = 1.0f + (morphProgress * morphIntensity) * (
            0.16f * sin((2 * angle + phase1).toDouble()).toFloat() +
            0.11f * cos((3 * angle - phase2).toDouble()).toFloat() +
            0.06f * sin((5 * angle + phase1 * 0.7f).toDouble()).toFloat()
        )

        val r = baseR * wave
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
