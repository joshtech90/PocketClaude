package de.smartzone.pocketclaude.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val Sans = FontFamily.SansSerif
private val Editorial = FontFamily.Serif

val PocketTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = Editorial, fontWeight = FontWeight.Bold, fontSize = 48.sp,
        lineHeight = 52.sp, letterSpacing = (-1.1).sp,
    ),
    displayMedium = TextStyle(
        fontFamily = Editorial, fontWeight = FontWeight.Bold, fontSize = 38.sp,
        lineHeight = 43.sp, letterSpacing = (-0.7).sp,
    ),
    displaySmall = TextStyle(
        fontFamily = Editorial, fontWeight = FontWeight.Bold, fontSize = 30.sp,
        lineHeight = 36.sp, letterSpacing = (-0.35).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = Editorial, fontWeight = FontWeight.Bold, fontSize = 30.sp,
        lineHeight = 36.sp, letterSpacing = (-0.3).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = Editorial, fontWeight = FontWeight.Bold, fontSize = 25.sp,
        lineHeight = 31.sp, letterSpacing = (-0.2).sp,
    ),
    headlineSmall = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Bold, fontSize = 20.sp,
        lineHeight = 27.sp, letterSpacing = (-0.15).sp,
    ),
    titleLarge = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Bold, fontSize = 20.sp,
        lineHeight = 26.sp, letterSpacing = (-0.2).sp,
    ),
    titleMedium = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold, fontSize = 15.sp,
        lineHeight = 22.sp, letterSpacing = 0.sp,
    ),
    titleSmall = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold, fontSize = 13.sp,
        lineHeight = 19.sp, letterSpacing = 0.1.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Normal, fontSize = 16.sp,
        lineHeight = 25.sp, letterSpacing = 0.05.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Normal, fontSize = 14.sp,
        lineHeight = 22.sp, letterSpacing = 0.05.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Normal, fontSize = 12.sp,
        lineHeight = 18.sp, letterSpacing = 0.1.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
        lineHeight = 20.sp, letterSpacing = 0.1.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold, fontSize = 12.sp,
        lineHeight = 17.sp, letterSpacing = 0.3.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold, fontSize = 11.sp,
        lineHeight = 15.sp, letterSpacing = 0.35.sp,
    ),
)
