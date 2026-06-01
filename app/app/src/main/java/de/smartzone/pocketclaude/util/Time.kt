package de.smartzone.pocketclaude.util

import android.content.Context
import de.smartzone.pocketclaude.R
import java.time.Duration
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

// DateTimeFormatter is immutable + thread-safe. We read the current default
// locale per call (not at class-load) so a language switch via LocalePrefs
// takes effect without a process restart.
private fun timeFormatter(): DateTimeFormatter =
    DateTimeFormatter.ofPattern("HH:mm", Locale.getDefault())
private fun dateFormatter(): DateTimeFormatter =
    DateTimeFormatter.ofPattern("d. MMM", Locale.getDefault())

/**
 * Localized relative-time label ("just now", "5 min ago", "yesterday", a clock
 * time for today, or a short date). Needs a [Context] for the string resources
 * so the output honors the app's selected language (i18n convention).
 */
fun formatRelative(context: Context, isoUtc: String): String {
    return try {
        val instant = OffsetDateTime.parse(isoUtc).toInstant()
        val now = Instant.now()
        val diff = Duration.between(instant, now)
        val sys = ZoneId.systemDefault()
        val sameDay = instant.atZone(sys).toLocalDate() == now.atZone(sys).toLocalDate()
        when {
            diff.toMinutes() < 1 -> context.getString(R.string.time_just_now)
            diff.toMinutes() < 60 ->
                context.getString(R.string.time_minutes_ago, diff.toMinutes())
            sameDay -> instant.atZone(sys).format(timeFormatter())
            diff.toDays() < 2 -> context.getString(R.string.time_yesterday)
            diff.toDays() < 7 ->
                context.getString(R.string.time_days_ago, diff.toDays())
            else -> instant.atZone(ZoneId.systemDefault()).format(dateFormatter())
        }
    } catch (_: Exception) {
        ""
    }
}

fun formatTime(isoUtc: String): String {
    return try {
        OffsetDateTime.parse(isoUtc)
            .atZoneSameInstant(ZoneId.systemDefault())
            .format(timeFormatter())
    } catch (_: Exception) {
        ""
    }
}
