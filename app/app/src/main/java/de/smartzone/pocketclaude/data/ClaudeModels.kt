package de.smartzone.pocketclaude.data

/**
 * Wählbare Claude-Modelle für den globalen Standard-Modell-Picker (Settings)
 * und den Modell-Override pro Gem. Die `id` ist der String, den der Server an
 * `ClaudeAgentOptions.model` reicht (Claude-CLI/Agent-SDK akzeptiert ihn direkt).
 *
 * Labels sind Produktnamen (nicht übersetzbar). Der „Automatisch"- bzw.
 * „Globaler Standard / Chat-Standard"-Eintrag wird in der UI per String-Resource
 * vorangestellt (Wert dort = "" bzw. null).
 */
object ClaudeModels {
    data class Option(val id: String, val label: String)

    val all: List<Option> = listOf(
        Option("claude-opus-4-8", "Opus 4.8"),
        Option("claude-opus-4-7", "Opus 4.7"),
        Option("claude-opus-4-6", "Opus 4.6"),
        Option("claude-sonnet-4-6", "Sonnet 4.6"),
        Option("claude-haiku-4-5", "Haiku 4.5"),
        Option("claude-fable-5", "Fable 5"),
    )

    /** Anzeige-Label für eine Modell-ID; unbekannte IDs werden 1:1 gezeigt. */
    fun labelFor(id: String?): String? =
        id?.takeIf { it.isNotBlank() }?.let { mid -> all.firstOrNull { it.id == mid }?.label ?: mid }
}

/** Effort-Stufen (CLAUDE_CODE_EFFORT_LEVEL). `off` = keine Steuerung. */
val EFFORT_LEVELS: List<String> = listOf("off", "low", "medium", "high", "xhigh", "max")
