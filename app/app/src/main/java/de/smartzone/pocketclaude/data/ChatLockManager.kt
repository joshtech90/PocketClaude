package de.smartzone.pocketclaude.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Prozess-globaler Merker, welche gesperrten Chats in DIESER App-Sitzung bereits
 * per PIN/Fingerabdruck entsperrt wurden. Bewusst nur im RAM: sobald der
 * Bildschirm ausgeht (PocketClaudeApp lauscht auf ACTION_SCREEN_OFF und ruft
 * [relockAll]) wird alles wieder gesperrt — genau das vom User gewählte
 * Re-Lock-Verhalten. Ein bloßer Wechsel in den Hintergrund sperrt NICHT mehr.
 *
 * Reiner UI-Riegel: die Nachrichten liegen weiterhin im Klartext auf dem Server.
 * Schützt gegen fremden Zugriff aufs entsperrte Gerät, nicht gegen jemanden mit
 * gültigem Login-Token.
 */
class ChatLockManager {
    private val _unlocked = MutableStateFlow<Set<String>>(emptySet())
    val unlocked: StateFlow<Set<String>> = _unlocked.asStateFlow()

    fun isUnlocked(cid: String): Boolean = cid in _unlocked.value

    fun unlock(cid: String) {
        if (cid.isNotBlank()) _unlocked.value = _unlocked.value + cid
    }

    fun relock(cid: String) {
        _unlocked.value = _unlocked.value - cid
    }

    /** Alle Entsperrungen zurücksetzen — beim Ausschalten des Displays. */
    fun relockAll() {
        if (_unlocked.value.isNotEmpty()) _unlocked.value = emptySet()
    }
}
