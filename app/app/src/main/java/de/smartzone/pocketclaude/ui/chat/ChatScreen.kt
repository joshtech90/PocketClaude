package de.smartzone.pocketclaude.ui.chat

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.InsertDriveFile
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Loop
import androidx.compose.material.icons.filled.DriveFileRenameOutline
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.IosShare
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.TextButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationDrawerItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.Image
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.smartzone.pocketclaude.data.ConversationDto
import de.smartzone.pocketclaude.ui.components.AssistantBubble
import de.smartzone.pocketclaude.ui.components.CompactionNotice
import de.smartzone.pocketclaude.ui.components.TtsState
import de.smartzone.pocketclaude.ui.components.UserBubble
import de.smartzone.pocketclaude.util.formatTime
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    vm: ChatViewModel,
    onOpenSettings: () -> Unit,
    onOpenConversations: () -> Unit,
    onOpenImages: () -> Unit,
    onNewChat: () -> Unit,
    onSwitchChat: (String) -> Unit,
    onStartGemChat: (String) -> Unit = {},
) {
    val state by vm.state.collectAsState()
    val audioState by vm.audioState.collectAsState()
    val context = LocalContext.current
    val container = remember {
        (context.applicationContext as de.smartzone.pocketclaude.PocketClaudeApp).container
    }
    val appSettings by container.settingsRepository.settingsFlow
        .collectAsState(initial = de.smartzone.pocketclaude.data.AppSettings())
    // Welche gesperrten Chats sind in dieser Sitzung entsperrt (Re-Lock bei
    // App-Hintergrund via ChatLockManager).
    val unlockedChats by container.chatLock.unlocked.collectAsState()
    var input by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var effortMenuOpen by remember { mutableStateOf(false) }
    var moreMenuOpen by remember { mutableStateOf(false) }
    var renameOpen by remember { mutableStateOf(false) }
    var renameInput by remember { mutableStateOf("") }
    var confirmDeleteOpen by remember { mutableStateOf(false) }
    var skillsDialogOpen by remember { mutableStateOf(false) }
    var autoSpeakDialogOpen by remember { mutableStateOf(false) }

    // Drawer-State + Chat-Liste fürs Drawer (wird beim Öffnen aktualisiert)
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    var drawerChats by remember { mutableStateOf<List<ConversationDto>>(emptyList()) }
    var drawerGems by remember { mutableStateOf<List<de.smartzone.pocketclaude.data.GemDto>>(emptyList()) }
    LaunchedEffect(drawerState.currentValue, state.title) {
        if (drawerState.currentValue == DrawerValue.Open) {
            runCatching { container.chatRepository.list() }
                .onSuccess { drawerChats = it.take(40) }
            runCatching { container.chatRepository.listGems() }
                .onSuccess { drawerGems = it }
        }
    }

    val defaultImageName = stringResource(de.smartzone.pocketclaude.R.string.chat_default_filename_image)
    val defaultDocName = stringResource(de.smartzone.pocketclaude.R.string.chat_default_filename_doc)
    val photoPicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        if (uri != null) {
            val name = queryName(context, uri) ?: defaultImageName
            vm.addPending(uri, name)
        }
    }
    val documentPicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri: Uri? ->
        if (uri != null) {
            val name = queryName(context, uri) ?: defaultDocName
            vm.addPending(uri, name)
        }
    }
    // Chat als .md lokal speichern (Storage Access Framework). Inhalt wird beim
    // Antippen via exportMarkdown geholt und hier nach Ziel-Auswahl geschrieben.
    var pendingExportMd by remember { mutableStateOf<String?>(null) }
    val saveMarkdownLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("text/markdown"),
    ) { uri: Uri? ->
        val md = pendingExportMd
        pendingExportMd = null
        if (uri != null && md != null) {
            val ok = runCatching {
                context.contentResolver.openOutputStream(uri)?.use {
                    it.write(md.toByteArray(Charsets.UTF_8))
                }
            }.isSuccess
            android.widget.Toast.makeText(
                context,
                context.getString(
                    if (ok) de.smartzone.pocketclaude.R.string.chat_export_saved
                    else de.smartzone.pocketclaude.R.string.chat_export_save_failed
                ),
                android.widget.Toast.LENGTH_SHORT,
            ).show()
        }
    }

    // Share-to-PocketClaude: beim ersten Öffnen dieses Chats die per Intent
    // geteilten Datei(en)/Text aus dem Container abholen und als Anhänge/Text
    // übernehmen. Einmalig — pendingShare wird danach geleert.
    LaunchedEffect(Unit) {
        val container =
            (context.applicationContext as de.smartzone.pocketclaude.PocketClaudeApp).container
        val share = container.pendingShare ?: return@LaunchedEffect
        container.pendingShare = null
        for (uri in share.uris) {
            val name = queryName(context, uri) ?: defaultDocName
            vm.addPending(uri, name)
        }
        val sharedText = share.text
        if (!sharedText.isNullOrBlank()) {
            input = if (input.isBlank()) sharedText else "$input\n$sharedText"
        }
    }

    // --- Scroll-Logik ---
    var initialScrollDone by remember(state.conversationId) { mutableStateOf(false) }

    // Initial-Load: instant ans absolute Ende. Wir machen das in einer Retry-
    // Loop mit kleinen delays, damit LazyColumn zwischen den Versuchen Layout-
    // Passes durchführen kann — sonst clamped scrollBy gegen noch nicht
    // gemessene Items und wir landen nur halb unten.
    LaunchedEffect(state.isLoading, state.messages.size) {
        if (!state.isLoading && !initialScrollDone && state.messages.isNotEmpty()) {
            scrollToVeryBottom(listState)
            initialScrollDone = true
        }
    }

    // Echtes "Bottom" — letztes Item komplett sichtbar + bei viewportEnd.
    // Wird nur noch für die FAB-Sichtbarkeit verwendet (kein Auto-Scroll mehr).
    val isAtBottom by remember {
        derivedStateOf {
            val info = listState.layoutInfo
            val total = info.totalItemsCount
            if (total == 0) return@derivedStateOf true
            val last = info.visibleItemsInfo.lastOrNull() ?: return@derivedStateOf true
            last.index >= total - 1 && (last.offset + last.size) <= info.viewportEndOffset + 24
        }
    }

    // Process-Death-Restore: cid in DataStore halten, damit die App nach
    // einem Hintergrund-Kill wieder hier aufmacht statt frischen Chat.
    LaunchedEffect(state.conversationId) {
        val cid = state.conversationId
        if (cid.isNotBlank()) {
            container.settingsRepository.setLastChatCid(cid)
        }
    }

    // Beim Stream-Start einmalig ans Ende scrollen — damit die gerade
    // abgeschickte User-Frage und der Anfang der Antwort sichtbar werden.
    // Während des Streamings selbst gibt es KEIN Auto-Scroll mehr; der User
    // scrollt selbst mit. Die früheren Auto-Scroll-Sprünge entstanden, weil
    // LazyColumn mit wachsenden Items + Layout-Latenz kollidiert ist.
    LaunchedEffect(state.isStreaming) {
        if (initialScrollDone && state.isStreaming) {
            scrollToVeryBottom(listState)
        }
    }

    // FAB-Sichtbarkeit: wenn nicht unten UND Liste hat Inhalt
    val showScrollFab by remember {
        derivedStateOf {
            !isAtBottom && listState.layoutInfo.totalItemsCount > 0
        }
    }

    // Spring-to-Match: bei jeder Änderung des aktuellen Treffer-Index
    // (= User hat „Weiter"/„Zurück" gedrückt oder gerade neuen Begriff eingetippt)
    // scrollen wir den entsprechenden Message-Bubble ins Sichtfeld.
    LaunchedEffect(state.searchIndex, state.searchMatches) {
        val targetId = state.currentMatchMessageId ?: return@LaunchedEffect
        val msgIndex = state.messages.indexOfFirst { it.id == targetId }
        if (msgIndex < 0) return@LaunchedEffect
        // LazyColumn-Item-Offset: das CompactionNotice-Item (wenn da) ist
        // dem messages-Index um 1 vorgelagert.
        val offset = if (state.hasMidSummary || state.hasLongSummary) 1 else 0
        runCatching { listState.animateScrollToItem(offset + msgIndex) }
    }

    // Errors → Snackbar
    LaunchedEffect(state.errorMessage) {
        state.errorMessage?.let { msg ->
            snackbar.showSnackbar(msg)
            vm.dismissError()
        }
    }

    // Audio-Fehler ebenfalls in der Snackbar zeigen
    LaunchedEffect(audioState.error) {
        audioState.error?.let { err ->
            snackbar.showSnackbar(context.getString(de.smartzone.pocketclaude.R.string.chat_audio_prefix, err))
            vm.clearAudioError()
        }
    }

    // ───── Voice-Input: Mic-Permission, Transkript-Empfang, Fehler ─────
    var pendingMicAction by remember { mutableStateOf(false) }
    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted && pendingMicAction) {
            vm.toggleRecording()
        } else if (!granted) {
            scope.launch {
                snackbar.showSnackbar(
                    context.getString(de.smartzone.pocketclaude.R.string.voice_error_no_permission)
                )
            }
        }
        pendingMicAction = false
    }
    // Transkript aus dem VM ins Input-Feld einfügen (nur im manuellen Modus —
    // im Auto-Modus geht der Text direkt zu send(), nicht über input).
    LaunchedEffect(Unit) {
        vm.transcriptToInsert.collect { transcript ->
            input = if (input.isBlank()) transcript else "$input $transcript"
        }
    }
    LaunchedEffect(state.voiceError) {
        state.voiceError?.let { msg ->
            snackbar.showSnackbar(msg)
            vm.clearVoiceError()
        }
    }

    // Auto-Mode: Tastatur explizit ausblenden + Fokus weg vom TextField.
    // Das InputField bleibt vom Composition-Tree weg, solange autoMode an
    // ist; falls die IME vorher geöffnet war, würde sie sonst noch hängen.
    val keyboardCtrl = LocalSoftwareKeyboardController.current
    val focusManager = LocalFocusManager.current
    LaunchedEffect(state.autoMode) {
        if (state.autoMode) {
            focusManager.clearFocus(force = true)
            keyboardCtrl?.hide()
        }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ChatDrawerContent(
                currentCid = state.conversationId,
                chats = drawerChats,
                gems = drawerGems,
                onNewChat = {
                    scope.launch { drawerState.close() }
                    onNewChat()
                },
                onStartGem = { gemId ->
                    scope.launch { drawerState.close() }
                    onStartGemChat(gemId)
                },
                onGenerateImages = {
                    scope.launch { drawerState.close() }
                    onOpenImages()
                },
                onSwitch = { cid ->
                    scope.launch { drawerState.close() }
                    if (cid != state.conversationId) onSwitchChat(cid)
                },
                onAllChats = {
                    scope.launch { drawerState.close() }
                    onOpenConversations()
                },
                onSettings = {
                    scope.launch { drawerState.close() }
                    onOpenSettings()
                },
            )
        },
    ) {
    Box(Modifier.fillMaxSize()) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        // Wir kümmern uns ums Bottom-Inset selbst (im InputBar via union(ime, navBar)),
        // damit Tastatur und Navigation-Bar sich nicht aufsummieren.
        contentWindowInsets = WindowInsets(0),
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            TopAppBar(
                title = {
                    if (state.searchActive) {
                        // Such-Modus: TextField statt Titel + Match-Counter
                        SearchBarTitle(
                            query = state.searchQuery,
                            onQueryChange = vm::setSearchQuery,
                            matchCount = state.searchMatches.size,
                            currentIndex = state.searchIndex,
                        )
                    } else {
                        Column {
                            val appName = stringResource(de.smartzone.pocketclaude.R.string.app_name)
                            val baseTitle = state.title.ifBlank { appName }
                            Text(
                                if (state.gemEmoji.isNotBlank()) "${state.gemEmoji}  $baseTitle" else baseTitle,
                                style = MaterialTheme.typography.titleMedium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            val pct = (state.totalTokens.toFloat() / 200_000f * 100f).toInt().coerceIn(0, 999)
                            val warn = pct >= 85
                            val cachedLast = state.lastTurnCachedRead
                            val cacheInfo = if (cachedLast > 0)
                                stringResource(de.smartzone.pocketclaude.R.string.chat_cache_suffix, cachedLast / 1000)
                            else ""
                            Text(
                                stringResource(de.smartzone.pocketclaude.R.string.chat_context_status, pct, formatTokens(context, state.totalTokens), cacheInfo),
                                style = MaterialTheme.typography.labelSmall,
                                color = if (warn) MaterialTheme.colorScheme.error
                                        else MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                            )
                        }
                    }
                },
                navigationIcon = {
                    if (state.searchActive) {
                        IconButton(onClick = { vm.closeSearch() }) {
                            Icon(Icons.Filled.Close, contentDescription = stringResource(de.smartzone.pocketclaude.R.string.action_close))
                        }
                    } else {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Filled.Menu, contentDescription = stringResource(de.smartzone.pocketclaude.R.string.title_conversations))
                        }
                    }
                },
                actions = {
                  if (state.searchActive) {
                    val hasMatches = state.searchMatches.isNotEmpty()
                    IconButton(onClick = { vm.previousMatch() }, enabled = hasMatches) {
                        Icon(Icons.Filled.KeyboardArrowUp, contentDescription = null)
                    }
                    IconButton(onClick = { vm.nextMatch() }, enabled = hasMatches) {
                        Icon(Icons.Filled.KeyboardArrowDown, contentDescription = null)
                    }
                  } else {
                    // Quick-toggle for the effort level
                    Box {
                        IconButton(onClick = { effortMenuOpen = true }) {
                            Icon(
                                Icons.Filled.Psychology,
                                contentDescription = stringResource(de.smartzone.pocketclaude.R.string.effort_label),
                                tint = effortTint(appSettings.effort),
                            )
                        }
                        DropdownMenu(
                            expanded = effortMenuOpen,
                            onDismissRequest = { effortMenuOpen = false },
                        ) {
                            effortOptions().forEach { (value, label) ->
                                val selected = appSettings.effort == value
                                DropdownMenuItem(
                                    text = { Text(label) },
                                    leadingIcon = if (selected) {
                                        { Icon(Icons.Filled.Check, contentDescription = null) }
                                    } else null,
                                    onClick = {
                                        effortMenuOpen = false
                                        scope.launch {
                                            container.settingsRepository.setEffort(value)
                                        }
                                    },
                                )
                            }
                        }
                    }
                    // Three-dot overflow — rename / pin / share / delete
                    Box {
                        IconButton(onClick = { moreMenuOpen = true }) {
                            Icon(Icons.Filled.MoreVert, contentDescription = stringResource(de.smartzone.pocketclaude.R.string.action_more))
                        }
                        DropdownMenu(
                            expanded = moreMenuOpen,
                            onDismissRequest = { moreMenuOpen = false },
                        ) {
                            DropdownMenuItem(
                                text = { Text(stringResource(de.smartzone.pocketclaude.R.string.action_rename)) },
                                leadingIcon = {
                                    Icon(Icons.Filled.DriveFileRenameOutline, contentDescription = null)
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    renameInput = state.title
                                    renameOpen = true
                                },
                            )
                            DropdownMenuItem(
                                text = {
                                    Text(stringResource(if (state.pinned) de.smartzone.pocketclaude.R.string.conversation_unpin else de.smartzone.pocketclaude.R.string.conversation_pin))
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.PushPin,
                                        contentDescription = null,
                                        tint = if (state.pinned) MaterialTheme.colorScheme.primary
                                               else MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    vm.togglePin()
                                },
                            )
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        if (state.skillsIsOverride) stringResource(de.smartzone.pocketclaude.R.string.skills_for_this_chat_done)
                                        else stringResource(de.smartzone.pocketclaude.R.string.skills_for_this_chat)
                                    )
                                },
                                leadingIcon = {
                                    Icon(Icons.Filled.AutoAwesome, contentDescription = null)
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    skillsDialogOpen = true
                                },
                            )
                            DropdownMenuItem(
                                text = {
                                    val markOn = stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_marker_on)
                                    val markOff = stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_marker_off)
                                    val mark = state.autoSpeakOverride?.let { if (it) markOn else markOff }.orEmpty()
                                    Text(stringResource(de.smartzone.pocketclaude.R.string.auto_speak_for_this_chat, mark))
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.AutoMirrored.Filled.VolumeUp,
                                        contentDescription = null,
                                    )
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    autoSpeakDialogOpen = true
                                },
                            )
                            // Auto-Mode: Voice-Loop (Recording → Senden →
                            // TTS-Vorlesen → wieder Recording).
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        if (state.autoMode)
                                            stringResource(de.smartzone.pocketclaude.R.string.chat_auto_mode_stop)
                                        else
                                            stringResource(de.smartzone.pocketclaude.R.string.chat_auto_mode_start)
                                    )
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.Loop,
                                        contentDescription = null,
                                        tint = if (state.autoMode) MaterialTheme.colorScheme.primary
                                               else MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    val turnOn = !state.autoMode
                                    if (turnOn) {
                                        // Permission vorher klären — sonst landet
                                        // der Loop im Error-Branch.
                                        if (container.voiceRecorder.hasPermission()) {
                                            vm.setAutoMode(true)
                                        } else {
                                            pendingMicAction = true
                                            micPermissionLauncher.launch(
                                                android.Manifest.permission.RECORD_AUDIO
                                            )
                                            // Permission-Result-Handler ruft
                                            // toggleRecording() — wir starten
                                            // den Auto-Mode hier separat, wenn
                                            // sich der Grant einstellt:
                                            // einfacher Trick: Auto-Mode flag
                                            // gleich setzen, der Loop wartet
                                            // dann auf den Mic-Start.
                                            vm.setAutoMode(true)
                                        }
                                    } else {
                                        vm.setAutoMode(false)
                                    }
                                },
                            )
                            DropdownMenuItem(
                                text = { Text(stringResource(de.smartzone.pocketclaude.R.string.search_in_chat)) },
                                leadingIcon = {
                                    Icon(Icons.Filled.Search, contentDescription = null)
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    vm.openSearch()
                                },
                            )
                            DropdownMenuItem(
                                text = { Text(stringResource(de.smartzone.pocketclaude.R.string.share_as_markdown)) },
                                leadingIcon = {
                                    Icon(Icons.Filled.IosShare, contentDescription = null)
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    vm.exportMarkdown { title, md ->
                                        shareMarkdownIntent(context, title, md)
                                    }
                                },
                            )
                            DropdownMenuItem(
                                text = { Text(stringResource(de.smartzone.pocketclaude.R.string.save_as_markdown)) },
                                leadingIcon = {
                                    Icon(Icons.Filled.Download, contentDescription = null)
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    vm.exportMarkdown { title, md ->
                                        pendingExportMd = md
                                        val safe = title.replace(Regex("""[^\p{L}\p{N}\-_ ]"""), "_")
                                            .take(60).trim().ifBlank { "chat" }
                                        saveMarkdownLauncher.launch("$safe.md")
                                    }
                                },
                            )
                            DropdownMenuItem(
                                text = { Text(stringResource(de.smartzone.pocketclaude.R.string.action_delete), color = MaterialTheme.colorScheme.error) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.Delete,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.error,
                                    )
                                },
                                onClick = {
                                    moreMenuOpen = false
                                    confirmDeleteOpen = true
                                },
                            )
                        }
                    }
                  } // else (not searchActive)
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { pad ->
        Column(modifier = Modifier.fillMaxSize().padding(pad)) {

            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)

            // Message list
            Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                if (state.isLoading) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                } else {
                  // SelectionContainer wickelt die Liste, damit Long-Press auf
                  // einer Bubble den nativen Text-Selektion-Modus startet
                  // (statt direkt zu kopieren). User kann dann Text-Range
                  // markieren, Standard-Android-Toolbar gibt „Copy / Translate /
                  // Share" etc. Für Komplett-Kopie der Antwort gibt's das
                  // separate Copy-Icon in der AssistantBubble.
                  androidx.compose.foundation.text.selection.SelectionContainer {
                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(vertical = 8.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        if (state.hasMidSummary || state.hasLongSummary) {
                            item {
                                CompactionNotice(
                                    text = stringResource(de.smartzone.pocketclaude.R.string.chat_compaction_notice),
                                )
                            }
                        }
                        // Leerer Gem-Chat: Gem-Kopf + tappbare Gesprächs-Starter.
                        if (state.messages.isEmpty() && !state.isStreaming &&
                            (state.gemName.isNotBlank() || state.gemStarters.isNotEmpty())
                        ) {
                            item {
                                GemWelcome(
                                    emoji = state.gemEmoji,
                                    name = state.gemName,
                                    description = state.gemDescription,
                                    starters = state.gemStarters,
                                    onStarter = { vm.send(it) },
                                )
                            }
                        }
                        // Streaming-Bubble läuft als VIRTUELLES letztes Element
                        // im gleichen items()-Block. Slot bleibt index-basiert
                        // stabil über den gesamten Stream-Lebenszyklus (kein
                        // `key = { it.id }`, dann ist auch der UserSaved-Id-Swap
                        // slot-stabil).
                        //
                        // WICHTIG: Stream-Bubble und finale Bubble teilen sich
                        // EINEN AssistantBubble-Call-Site. Wenn sie an zwei
                        // verschiedenen Call-Sites hängen (z.B. `if (msg ==
                        // null) AssistantBubble(...) else AssistantBubble(...)`),
                        // sieht Compose das beim Done als Dispose + Re-Mount,
                        // nicht als Recompose — MarkdownText-Cache weg, Bubble
                        // wird frisch gemessen, sichtbarer Scroll-Sprung.
                        // Hier deshalb genau EIN Call-Site mit umgeschwenkten
                        // Parametern (text / isStreaming / onSpeakClick).
                        val msgs = state.messages
                        val displayCount = msgs.size + (if (state.isStreaming) 1 else 0)
                        items(count = displayCount) { i ->
                            val msg = msgs.getOrNull(i)
                            val isStreamingSlot = msg == null
                            if (msg?.role == "user") {
                                UserBubble(
                                    text = msg.content,
                                    attachments = msg.attachments,
                                    collapseLongMessages = appSettings.collapseLongUserMessages,
                                )
                            } else if (isStreamingSlot || msg?.role == "assistant") {
                                val bubbleText = msg?.content ?: state.streamingText
                                val bubbleThinking = if (isStreamingSlot) state.streamingThinking else ""
                                val ttsState = if (msg != null) when {
                                    audioState.loadingMessageId == msg.id -> TtsState.Loading
                                    audioState.playingMessageId == msg.id -> TtsState.Playing
                                    audioState.pausedMessageId == msg.id -> TtsState.Paused
                                    else -> TtsState.Idle
                                } else TtsState.Idle
                                val onSpeakClick: (() -> Unit)? = if (msg != null) {
                                    { vm.speak(msg.id) }
                                } else null
                                AssistantBubble(
                                    text = bubbleText,
                                    isStreaming = isStreamingSlot,
                                    thinkingText = bubbleThinking,
                                    ttsState = ttsState,
                                    onSpeakClick = onSpeakClick,
                                    onPauseClick = { vm.pauseSpeaking() },
                                    onResumeClick = { vm.resumeSpeaking() },
                                    onStopClick = { vm.stopSpeaking() },
                                )
                            }
                        }
                        item { Spacer(Modifier.height(8.dp)) }
                    }
                  } // SelectionContainer
                }

                if (state.isCompacting) {
                    AssistChip(
                        onClick = {},
                        label = { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_compacting_chip)) },
                        leadingIcon = {
                            CircularProgressIndicator(
                                strokeWidth = 2.dp,
                                modifier = Modifier.size(14.dp),
                            )
                        },
                        colors = AssistChipDefaults.assistChipColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                        ),
                        modifier = Modifier.align(Alignment.TopCenter).padding(top = 8.dp),
                    )
                }

                // Scroll-to-bottom FAB — erscheint wenn der User weit hochgescrollt ist
                if (showScrollFab) {
                    SmallFloatingActionButton(
                        onClick = {
                            scope.launch {
                                scrollToVeryBottom(listState)
                            }
                        },
                        containerColor = MaterialTheme.colorScheme.surface,
                        contentColor = MaterialTheme.colorScheme.onSurface,
                        elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 4.dp),
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .padding(end = 16.dp, bottom = 16.dp),
                    ) {
                        Icon(
                            Icons.Filled.KeyboardArrowDown,
                            contentDescription = stringResource(de.smartzone.pocketclaude.R.string.chat_scroll_to_bottom_cd),
                        )
                    }
                }
            }

            // Pending attachments strip
            AnimatedVisibility(visible = state.pending.isNotEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    state.pending.forEach { p ->
                        PendingChip(p, onRemove = { vm.removePending(p.uri) })
                    }
                }
            }

            // Input: Im Auto-Mode komplett ersetzt durch AutoModeBar (grosser
            // Mic + Status-Text + Exit-Button). Tastatur ist dort nutzlos,
            // wird beim Auto-Mode-Start aktiv ausgeblendet (siehe oben).
            // Image-Mode läuft eh über den eigenen Bilder-Screen (Drawer),
            // hier deshalb keine Mode-Unterscheidung mehr.
            val voiceEnabled = !state.isStreaming &&
                audioState.loadingMessageId == null &&
                audioState.playingMessageId == null
            val handleMicTap: () -> Unit = {
                if (container.voiceRecorder.hasPermission()) {
                    vm.toggleRecording()
                } else {
                    pendingMicAction = true
                    micPermissionLauncher.launch(android.Manifest.permission.RECORD_AUDIO)
                }
            }
            if (state.autoMode) {
                de.smartzone.pocketclaude.ui.components.AutoModeBar(
                    voiceState = state.voiceState,
                    isStreaming = state.isStreaming,
                    ttsLoading = audioState.loadingMessageId != null,
                    ttsPlaying = audioState.playingMessageId != null,
                    voiceEnabled = voiceEnabled,
                    autoSendEnabled = appSettings.autoSendEnabled,
                    autoSendSilenceMs = appSettings.autoSendSilenceMs,
                    silenceProgressMs = state.silenceProgressMs,
                    onMicTap = handleMicTap,
                    onMicCancel = { vm.cancelRecording() },
                    onExitAutoMode = { vm.setAutoMode(false) },
                    onAutoSendChange = { enabled ->
                        scope.launch { container.settingsRepository.setAutoSendEnabled(enabled) }
                    },
                )
            } else {
                InputBar(
                    value = input,
                    onChange = { input = it },
                    onSend = {
                        val text = input
                        input = ""
                        vm.send(text)
                    },
                    onStop = { vm.stop() },
                    onAttachImage = {
                        photoPicker.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                        )
                    },
                    onAttachDocument = {
                        // Liberal-Liste: Claude kann mit allem umgehen, was Text ist
                        // (Code, Configs, Logs, Markdown, JSON, YAML, …) oder als
                        // Bild/PDF erkannt werden kann. Wir lassen den OS-Picker
                        // alles anbieten (`*/*`) — der Server entscheidet via
                        // _looks_like_text, ob's inline eingebettet wird oder als
                        // Binär-Referenz behandelt. Size-Schutz: 20 MB Upload-Limit
                        // im Server (.env: MAX_UPLOAD_MB).
                        documentPicker.launch(arrayOf("*/*"))
                    },
                    sending = state.isStreaming,
                    hasContent = input.isNotBlank() || state.pending.any { it.uploaded != null },
                    voiceState = state.voiceState,
                    // Mic deaktivieren wenn LLM busy ist (Stream läuft oder TTS
                    // spielt) — sonst nimmt das Mic die TTS-Wiedergabe vom
                    // Lautsprecher mit auf.
                    voiceEnabled = voiceEnabled,
                    onMicTap = handleMicTap,
                    onMicCancel = { vm.cancelRecording() },
                )
            }
        }
    }
    // Sperr-Ansicht: liegt über dem ganzen Chat, solange dieser Chat gesperrt
    // und in dieser Sitzung noch nicht per PIN/Fingerabdruck entsperrt ist.
    if (state.locked && state.conversationId !in unlockedChats) {
        de.smartzone.pocketclaude.ui.lock.ChatLockGate(
            chatTitle = state.title,
            biometricEnabled = appSettings.chatLockBiometricEnabled,
            verifyPin = { pin -> vm.verifyChatLockPin(pin) },
            onUnlocked = { container.chatLock.unlock(state.conversationId) },
            onOpenMenu = { scope.launch { drawerState.open() } },
            menuContentDescription = stringResource(de.smartzone.pocketclaude.R.string.title_conversations),
            modifier = Modifier.fillMaxSize(),
        )
    }
    } // Box (Gate-Overlay)
    } // ModalNavigationDrawer

    // Rename dialog
    if (renameOpen) {
        AlertDialog(
            onDismissRequest = { renameOpen = false },
            title = { Text(stringResource(de.smartzone.pocketclaude.R.string.rename_dialog_title)) },
            text = {
                OutlinedTextField(
                    value = renameInput,
                    onValueChange = { renameInput = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    if (renameInput.isNotBlank()) vm.renameChat(renameInput)
                    renameOpen = false
                }) { Text(stringResource(de.smartzone.pocketclaude.R.string.action_save)) }
            },
            dismissButton = {
                TextButton(onClick = { renameOpen = false }) { Text(stringResource(de.smartzone.pocketclaude.R.string.action_cancel)) }
            },
        )
    }

    // Delete confirmation
    if (confirmDeleteOpen) {
        AlertDialog(
            onDismissRequest = { confirmDeleteOpen = false },
            title = { Text(stringResource(de.smartzone.pocketclaude.R.string.confirm_delete_title)) },
            text = { Text(stringResource(de.smartzone.pocketclaude.R.string.confirm_delete_message)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmDeleteOpen = false
                    vm.deleteChat { onNewChat() }
                }) {
                    Text(stringResource(de.smartzone.pocketclaude.R.string.action_delete), color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmDeleteOpen = false }) { Text(stringResource(de.smartzone.pocketclaude.R.string.action_cancel)) }
            },
        )
    }

    // Skills-Override-Dialog
    if (skillsDialogOpen) {
        ChatSkillsDialog(
            currentSkills = state.skills,
            isOverride = state.skillsIsOverride,
            onSave = { newSkills ->
                vm.setChatSkills(newSkills)
                skillsDialogOpen = false
            },
            onReset = {
                vm.resetChatSkills()
                skillsDialogOpen = false
            },
            onDismiss = { skillsDialogOpen = false },
        )
    }

    // Auto-Speak-Override-Dialog
    if (autoSpeakDialogOpen) {
        ChatAutoSpeakDialog(
            globalDefault = appSettings.ttsAutoSpeak,
            override = state.autoSpeakOverride,
            onSave = { newOverride ->
                vm.setAutoSpeakOverride(newOverride)
                autoSpeakDialogOpen = false
            },
            onDismiss = { autoSpeakDialogOpen = false },
        )
    }
}

/**
 * Per-Chat-Skills-Override-Dialog. Zeigt die drei Toggle-Switches; "Speichern"
 * setzt einen Override für DIESEN Chat, "Auf Standard zurücksetzen" löscht
 * den Override und der User-Default greift wieder.
 */
@Composable
private fun ChatSkillsDialog(
    currentSkills: de.smartzone.pocketclaude.data.SkillsDto?,
    isOverride: Boolean,
    onSave: (de.smartzone.pocketclaude.data.SkillsDto) -> Unit,
    onReset: () -> Unit,
    onDismiss: () -> Unit,
) {
    val initial = currentSkills ?: de.smartzone.pocketclaude.data.SkillsDto()
    var webSearch by remember(initial) { mutableStateOf(initial.webSearch) }
    var webFetch by remember(initial) { mutableStateOf(initial.webFetch) }
    var codeExecution by remember(initial) { mutableStateOf(initial.codeExecution) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_skills_dialog_title)) },
        text = {
            Column {
                Text(
                    if (isOverride)
                        stringResource(de.smartzone.pocketclaude.R.string.chat_skills_dialog_body_override)
                    else
                        stringResource(de.smartzone.pocketclaude.R.string.chat_skills_dialog_body_default),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                de.smartzone.pocketclaude.ui.settings.SkillToggleRow(
                    label = stringResource(de.smartzone.pocketclaude.R.string.chat_skill_web_search_label),
                    description = stringResource(de.smartzone.pocketclaude.R.string.chat_skill_web_search_desc),
                    checked = webSearch,
                    onCheckedChange = { webSearch = it },
                )
                de.smartzone.pocketclaude.ui.settings.SkillToggleRow(
                    label = stringResource(de.smartzone.pocketclaude.R.string.chat_skill_web_fetch_label),
                    description = stringResource(de.smartzone.pocketclaude.R.string.chat_skill_web_fetch_desc),
                    checked = webFetch,
                    onCheckedChange = { webFetch = it },
                )
                de.smartzone.pocketclaude.ui.settings.SkillToggleRow(
                    label = stringResource(de.smartzone.pocketclaude.R.string.chat_skill_code_label),
                    description = stringResource(de.smartzone.pocketclaude.R.string.chat_skill_code_desc),
                    checked = codeExecution,
                    onCheckedChange = { codeExecution = it },
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                onSave(
                    de.smartzone.pocketclaude.data.SkillsDto(
                        webSearch = webSearch,
                        webFetch = webFetch,
                        codeExecution = codeExecution,
                    )
                )
            }) { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_skills_save_for_chat)) }
        },
        dismissButton = {
            Row {
                if (isOverride) {
                    TextButton(onClick = onReset) { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_skills_reset_default)) }
                    Spacer(Modifier.width(4.dp))
                }
                TextButton(onClick = onDismiss) { Text(stringResource(de.smartzone.pocketclaude.R.string.action_cancel)) }
            }
        },
    )
}

/**
 * Per-Chat-Auto-Speak-Dialog. Drei Optionen: an / aus / globalen Default
 * nutzen. Override lebt nur app-lokal (DataStore), nicht server-seitig.
 */
@Composable
private fun ChatAutoSpeakDialog(
    globalDefault: Boolean,
    override: Boolean?,
    onSave: (Boolean?) -> Unit,
    onDismiss: () -> Unit,
) {
    val onLbl = stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_on)
    val offLbl = stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_off)
    val defaultLabel = stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_default_label, if (globalDefault) onLbl else offLbl)
    val options = listOf<Pair<String, Boolean?>>(
        defaultLabel to null,
        stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_always_on) to true,
        stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_always_off) to false,
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_dialog_title)) },
        text = {
            Column {
                Text(
                    stringResource(de.smartzone.pocketclaude.R.string.chat_auto_speak_dialog_body),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                options.forEach { (label, value) ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSave(value) }
                            .padding(vertical = 8.dp),
                    ) {
                        val selected = override == value
                        Icon(
                            imageVector = if (selected) Icons.Filled.Check
                                          else Icons.Filled.KeyboardArrowDown,
                            contentDescription = null,
                            tint = if (selected) MaterialTheme.colorScheme.primary
                                   else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.width(12.dp))
                        Text(
                            label,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = if (selected) FontWeight.SemiBold
                                         else FontWeight.Normal,
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(de.smartzone.pocketclaude.R.string.action_close)) }
        },
    )
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun GemWelcome(
    emoji: String,
    name: String,
    description: String,
    starters: List<String>,
    onStarter: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(emoji.ifBlank { "🤖" }, style = MaterialTheme.typography.displaySmall)
        if (name.isNotBlank()) {
            Text(
                name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
        }
        if (description.isNotBlank()) {
            Text(
                description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
        }
        if (starters.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                starters.forEach { s ->
                    AssistChip(
                        onClick = { onStarter(s) },
                        label = { Text(s) },
                    )
                }
            }
        }
    }
}

@Composable
private fun ChatDrawerContent(
    currentCid: String,
    chats: List<ConversationDto>,
    gems: List<de.smartzone.pocketclaude.data.GemDto>,
    onNewChat: () -> Unit,
    onStartGem: (String) -> Unit,
    onGenerateImages: () -> Unit,
    onSwitch: (String) -> Unit,
    onAllChats: () -> Unit,
    onSettings: () -> Unit,
) {
    // Image-Gen-Config asynchron prüfen — wir zeigen den Drawer-Eintrag nur,
    // wenn ein API-Key gesetzt ist (User-Wunsch: "soll überall aus sein wenn
    // kein API-Key"). Bei API-Errors / nicht eingerichtet: Eintrag bleibt aus.
    val context = androidx.compose.ui.platform.LocalContext.current
    val container = remember {
        (context.applicationContext as de.smartzone.pocketclaude.PocketClaudeApp).container
    }
    var imageGenAvailable by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        runCatching { container.chatRepository.imagesConfig() }
            .onSuccess { cfg -> imageGenAvailable = cfg.configured }
    }
    ModalDrawerSheet(
        drawerContainerColor = MaterialTheme.colorScheme.background,
        drawerContentColor = MaterialTheme.colorScheme.onBackground,
    ) {
        // Kopf: Logo + Titel + "Alle Chats"-Aufruf
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp)
                .clip(RoundedCornerShape(14.dp)),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Image(
                painter = painterResource(
                    id = de.smartzone.pocketclaude.R.drawable.pocket_claude_icon
                ),
                contentDescription = stringResource(de.smartzone.pocketclaude.R.string.app_name),
                modifier = Modifier
                    .size(40.dp)
                    .clickable { onAllChats() },
            )
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    stringResource(de.smartzone.pocketclaude.R.string.app_name),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    stringResource(de.smartzone.pocketclaude.R.string.all_conversations),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onSettings) {
                Icon(Icons.Filled.Settings, contentDescription = stringResource(de.smartzone.pocketclaude.R.string.title_settings))
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)

        Spacer(Modifier.height(8.dp))
        NavigationDrawerItem(
            icon = { Icon(Icons.Filled.Add, contentDescription = null) },
            label = { Text(stringResource(de.smartzone.pocketclaude.R.string.new_chat)) },
            selected = false,
            onClick = onNewChat,
            colors = NavigationDrawerItemDefaults.colors(
                unselectedContainerColor = MaterialTheme.colorScheme.background,
            ),
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        // Image generation — only visible if an API key is configured
        // (otherwise the entry would do nothing useful). Setup flow runs via Settings.
        if (imageGenAvailable) {
            NavigationDrawerItem(
                icon = { Icon(Icons.Filled.AutoAwesome, contentDescription = null) },
                label = { Text(stringResource(de.smartzone.pocketclaude.R.string.title_images)) },
                selected = false,
                onClick = onGenerateImages,
                colors = NavigationDrawerItemDefaults.colors(
                    unselectedContainerColor = MaterialTheme.colorScheme.background,
                ),
                modifier = Modifier.padding(horizontal = 12.dp),
            )
        }
        NavigationDrawerItem(
            icon = { Icon(Icons.Filled.Search, contentDescription = null) },
            label = { Text(stringResource(de.smartzone.pocketclaude.R.string.all_conversations)) },
            selected = false,
            onClick = onAllChats,
            colors = NavigationDrawerItemDefaults.colors(
                unselectedContainerColor = MaterialTheme.colorScheme.background,
            ),
            modifier = Modifier.padding(horizontal = 12.dp),
        )

        // Gems (Custom Agents) — Tippen startet einen frischen Chat mit dem Gem.
        if (gems.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Text(
                stringResource(de.smartzone.pocketclaude.R.string.section_gems),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 24.dp, top = 8.dp, bottom = 4.dp),
            )
            gems.forEach { gem ->
                NavigationDrawerItem(
                    icon = {
                        Text(
                            gem.emoji.ifBlank { "🤖" },
                            style = MaterialTheme.typography.titleMedium,
                        )
                    },
                    label = {
                        Text(gem.name, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    },
                    selected = false,
                    onClick = { onStartGem(gem.id) },
                    colors = NavigationDrawerItemDefaults.colors(
                        unselectedContainerColor = MaterialTheme.colorScheme.background,
                    ),
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
            }
        }

        Spacer(Modifier.height(8.dp))
        Text(
            stringResource(de.smartzone.pocketclaude.R.string.recent_chats),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 24.dp, top = 8.dp, bottom = 4.dp),
        )

        LazyColumn(
            modifier = Modifier.fillMaxWidth().weight(1f),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
        ) {
            items(chats, key = { it.id }) { conv ->
                NavigationDrawerItem(
                    icon = {
                        if (conv.pinned) {
                            Icon(
                                Icons.Filled.PushPin,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                            )
                        } else {
                            Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = null)
                        }
                    },
                    label = {
                        Text(
                            conv.title.ifBlank { stringResource(de.smartzone.pocketclaude.R.string.chat_untitled) },
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    selected = conv.id == currentCid,
                    onClick = { onSwitch(conv.id) },
                    colors = NavigationDrawerItemDefaults.colors(
                        unselectedContainerColor = MaterialTheme.colorScheme.background,
                    ),
                )
            }
        }
    }
}

@Composable
private fun PendingChip(p: PendingAttachment, onRemove: () -> Unit) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when {
            p.uploading -> CircularProgressIndicator(
                strokeWidth = 2.dp,
                modifier = Modifier.size(14.dp),
            )
            p.error != null -> Icon(
                Icons.Filled.Close,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.error,
                modifier = Modifier.size(16.dp),
            )
            else -> Icon(
                Icons.Filled.Image,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(16.dp),
            )
        }
        Spacer(Modifier.width(6.dp))
        Text(
            p.filename,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.widthIn(max = 140.dp),
        )
        Spacer(Modifier.width(4.dp))
        IconButton(onClick = onRemove, modifier = Modifier.size(20.dp)) {
            Icon(
                Icons.Filled.Close,
                contentDescription = stringResource(de.smartzone.pocketclaude.R.string.chat_remove),
                modifier = Modifier.size(14.dp),
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun InputBar(
    value: String,
    onChange: (String) -> Unit,
    onSend: () -> Unit,
    onStop: () -> Unit,
    onAttachImage: () -> Unit,
    onAttachDocument: () -> Unit,
    sending: Boolean,
    hasContent: Boolean,
    voiceState: VoiceState,
    voiceEnabled: Boolean,
    onMicTap: () -> Unit,
    onMicCancel: () -> Unit,
) {
    var attachMenu by remember { mutableStateOf(false) }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.background)
            // Max von IME und Navigation-Bar — kein Aufsummieren mehr.
            .windowInsetsPadding(WindowInsets.ime.union(WindowInsets.navigationBars))
            .padding(horizontal = 8.dp, vertical = 8.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        Box {
            IconButton(onClick = { attachMenu = true }) {
                Icon(Icons.Filled.AttachFile, contentDescription = stringResource(de.smartzone.pocketclaude.R.string.chat_attach))
            }
            DropdownMenu(
                expanded = attachMenu,
                onDismissRequest = { attachMenu = false },
            ) {
                DropdownMenuItem(
                    text = { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_attach_image_menu)) },
                    leadingIcon = { Icon(Icons.Filled.AddPhotoAlternate, contentDescription = null) },
                    onClick = { attachMenu = false; onAttachImage() },
                )
                DropdownMenuItem(
                    text = { Text(stringResource(de.smartzone.pocketclaude.R.string.chat_attach_file_menu)) },
                    leadingIcon = { Icon(Icons.AutoMirrored.Filled.InsertDriveFile, contentDescription = null) },
                    onClick = { attachMenu = false; onAttachDocument() },
                )
            }
        }

        // Mic-Button: idle / recording (pulsierend grün) / transcribing (Spinner).
        // Long-Press während Recording bricht ab statt zu transkribieren.
        de.smartzone.pocketclaude.ui.components.MicButton(
            state = when (voiceState) {
                VoiceState.Idle -> de.smartzone.pocketclaude.ui.components.MicState.Idle
                VoiceState.Recording -> de.smartzone.pocketclaude.ui.components.MicState.Recording
                VoiceState.Transcribing -> de.smartzone.pocketclaude.ui.components.MicState.Transcribing
            },
            onTap = onMicTap,
            onCancel = onMicCancel,
            // Erlaubt wenn der User wirklich was tun darf: nicht senden,
            // nicht transkribieren, LLM nicht busy (Stream/TTS). Während
            // einer aktiven Recording-Phase bleibt der Button enabled, damit
            // der User stoppen kann.
            enabled = voiceState == VoiceState.Recording ||
                (voiceEnabled && voiceState != VoiceState.Transcribing),
        )

        Box(modifier = Modifier.weight(1f)) {
            OutlinedTextField(
                value = value,
                onValueChange = onChange,
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text(stringResource(de.smartzone.pocketclaude.R.string.hint_message)) },
                maxLines = 6,
                shape = RoundedCornerShape(22.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primary,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant,
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        }

        Spacer(Modifier.width(6.dp))

        SendButton(
            sending = sending,
            enabled = hasContent || sending,
            onSend = onSend,
            onStop = onStop,
        )
    }
}


@Composable
private fun SendButton(
    sending: Boolean,
    enabled: Boolean,
    onSend: () -> Unit,
    onStop: () -> Unit,
) {
    val containerColor = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant
    val contentColor = if (enabled) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(containerColor),
        contentAlignment = Alignment.Center,
    ) {
        IconButton(
            onClick = { if (sending) onStop() else onSend() },
            enabled = enabled,
        ) {
            Icon(
                imageVector = if (sending) Icons.Filled.Stop else Icons.Filled.Send,
                contentDescription = stringResource(if (sending) de.smartzone.pocketclaude.R.string.stop else de.smartzone.pocketclaude.R.string.send),
                tint = contentColor,
            )
        }
    }
}

private fun shareMarkdownIntent(context: android.content.Context, title: String, markdown: String) {
    // Markdown in temp-Datei, Share via FileProvider als .md
    try {
        val safe = title.replace(Regex("""[^\p{L}\p{N}\-_ ]"""), "_").take(60).trim().ifBlank { "chat" }
        val file = java.io.File(context.cacheDir, "exports").apply { mkdirs() }
            .let { java.io.File(it, "$safe.md") }
        file.writeText(markdown, Charsets.UTF_8)
        val uri = androidx.core.content.FileProvider.getUriForFile(
            context, "${context.packageName}.fileprovider", file,
        )
        val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
            type = "text/markdown"
            putExtra(android.content.Intent.EXTRA_STREAM, uri)
            putExtra(android.content.Intent.EXTRA_SUBJECT, title)
            putExtra(android.content.Intent.EXTRA_TEXT, markdown.take(4000))
            addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(android.content.Intent.createChooser(intent, context.getString(de.smartzone.pocketclaude.R.string.chat_share_chooser_title)))
    } catch (e: Exception) {
        android.widget.Toast.makeText(context, context.getString(de.smartzone.pocketclaude.R.string.chat_share_failed, e.message ?: ""), android.widget.Toast.LENGTH_LONG).show()
    }
}

private fun formatTokens(context: android.content.Context, n: Int): String = when {
    n >= 1_000_000 -> context.getString(de.smartzone.pocketclaude.R.string.tokens_label_millions, n / 1_000_000f)
    n >= 10_000 -> context.getString(de.smartzone.pocketclaude.R.string.tokens_label_thousands_k, n / 1000)
    n >= 1000 -> context.getString(de.smartzone.pocketclaude.R.string.tokens_label_thousands_dot, n / 1000f)
    else -> context.getString(de.smartzone.pocketclaude.R.string.tokens_label_raw, n)
}

@Composable
private fun effortOptions(): List<Pair<String, String>> = listOf(
    "off" to stringResource(de.smartzone.pocketclaude.R.string.effort_off_label),
    "low" to stringResource(de.smartzone.pocketclaude.R.string.effort_low_label),
    "medium" to stringResource(de.smartzone.pocketclaude.R.string.effort_medium_label),
    "high" to stringResource(de.smartzone.pocketclaude.R.string.effort_high_label),
    "xhigh" to stringResource(de.smartzone.pocketclaude.R.string.effort_xhigh_label),
    "max" to stringResource(de.smartzone.pocketclaude.R.string.effort_max_label),
)

@Composable
private fun effortTint(effort: String): Color = when (effort) {
    "off" -> MaterialTheme.colorScheme.onSurfaceVariant
    "low", "medium" -> MaterialTheme.colorScheme.onSurface
    else -> MaterialTheme.colorScheme.primary
}

@Composable
private fun SearchBarTitle(
    query: String,
    onQueryChange: (String) -> Unit,
    matchCount: Int,
    currentIndex: Int,
) {
    val focusRequester = remember { androidx.compose.ui.focus.FocusRequester() }
    LaunchedEffect(Unit) {
        // Beim Eintreten in den Suchmodus den Fokus aufs Feld setzen, damit
        // die Tastatur sofort aufgeht. Kleine Verzögerung damit das Layout fertig ist.
        kotlinx.coroutines.delay(50)
        runCatching { focusRequester.requestFocus() }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            placeholder = { Text(stringResource(de.smartzone.pocketclaude.R.string.search_in_chat)) },
            singleLine = true,
            modifier = Modifier
                .weight(1f)
                .focusRequester(focusRequester),
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent,
                focusedBorderColor = androidx.compose.ui.graphics.Color.Transparent,
                focusedContainerColor = androidx.compose.ui.graphics.Color.Transparent,
                unfocusedContainerColor = androidx.compose.ui.graphics.Color.Transparent,
            ),
        )
        if (query.isNotBlank()) {
            val label = if (matchCount == 0) "0"
            else "${currentIndex + 1}/${matchCount}"
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                color = if (matchCount == 0) MaterialTheme.colorScheme.error
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 8.dp),
            )
        }
    }
}

private fun queryName(context: android.content.Context, uri: Uri): String? {
    return try {
        context.contentResolver.query(uri, null, null, null, null)?.use { c ->
            val idx = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
            if (idx >= 0 && c.moveToFirst()) c.getString(idx) else null
        }
    } catch (_: Exception) {
        null
    }
}

/**
 * Scrollt eine LazyColumn zuverlässig ans **absolute Ende**, auch bei sehr
 * langen letzten Items (Markdown-Bubbles, Code-Blöcke, Bilder), deren wahre
 * Höhe progressive über mehrere Layout-Passes erst entsteht.
 *
 * Pattern: scrollToItem mit großem scrollOffset → LazyColumn clamped die
 * Position so, dass das Item-Bottom am Viewport-Bottom sitzt. Mehrfach mit
 * kurzen Pausen wiederholen, weil sich die Item-Höhe noch ändern kann
 * (Markdown-Rendering, Image-Loading). Bricht ab, sobald wirklich am Ende
 * oder nach ~600ms.
 */
private suspend fun scrollToVeryBottom(listState: androidx.compose.foundation.lazy.LazyListState) {
    val totalAtStart = listState.layoutInfo.totalItemsCount
    if (totalAtStart == 0) return

    var attempts = 0
    while (attempts < 12) {
        val total = listState.layoutInfo.totalItemsCount
        val lastIdx = (total - 1).coerceAtLeast(0)
        // Großer scrollOffset → das Item wird so weit "rausgeschoben", dass
        // LazyColumn auf "Item-Bottom am Viewport-Bottom" clamped. Anders als
        // scrollBy weiß scrollToItem, dass es das Item zuerst messen muss.
        listState.scrollToItem(lastIdx, scrollOffset = 1_000_000)
        kotlinx.coroutines.delay(50)

        val info = listState.layoutInfo
        val last = info.visibleItemsInfo.lastOrNull() ?: break
        val atBottom = last.index >= info.totalItemsCount - 1 &&
            (last.offset + last.size) <= info.viewportEndOffset + 4
        if (atBottom) return
        attempts++
    }
}

