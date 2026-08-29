package de.smartzone.pocketclaude.ui.theme

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import de.smartzone.pocketclaude.data.ThemeMode

@Immutable
data class PocketColors(
    val bubbleUser: Color,
    val bubbleAssistant: Color,
    val onBubbleUser: Color,
    val onBubbleAssistant: Color,
    val accent: Color,
    val success: Color,
    val ambientPrimary: Color,
    val ambientSecondary: Color,
    val surfaceLow: Color,
    val outlineSoft: Color,
)

val LocalPocketColors = staticCompositionLocalOf {
    specFor(PocketPalette.MIDNIGHT_ATELIER).darkPocket
}

private val PocketShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(13.dp),
    medium = RoundedCornerShape(19.dp),
    large = RoundedCornerShape(27.dp),
    extraLarge = RoundedCornerShape(36.dp),
)

@Composable
fun PocketClaudeTheme(
    mode: ThemeMode = ThemeMode.SYSTEM,
    palette: PocketPalette = PocketPalette.MIDNIGHT_ATELIER,
    content: @Composable () -> Unit,
) {
    val systemDark = isSystemInDarkTheme()
    val dark = when (mode) {
        ThemeMode.SYSTEM -> systemDark
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }

    // Hell und dunkel sind zwei Saetze DERSELBEN Palette. Der Hell-Dunkel-Modus
    // bleibt also unabhaengig von der Farbwahl bedienbar.
    val spec = specFor(palette)
    val scheme = if (dark) spec.darkScheme else spec.lightScheme
    val pocket = if (dark) spec.darkPocket else spec.lightPocket

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = view.context.findActivity()?.window ?: return@SideEffect
            WindowCompat.setDecorFitsSystemWindows(window, false)
            val controller = WindowCompat.getInsetsController(window, view)
            controller.isAppearanceLightStatusBars = !dark
            controller.isAppearanceLightNavigationBars = !dark
        }
    }

    androidx.compose.runtime.CompositionLocalProvider(
        LocalPocketColors provides pocket,
    ) {
        MaterialTheme(
            colorScheme = scheme,
            typography = PocketTypography,
            shapes = PocketShapes,
            content = content,
        )
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

// Convenience accessor
object PocketTheme {
    val colors: PocketColors
        @Composable get() = LocalPocketColors.current
}
