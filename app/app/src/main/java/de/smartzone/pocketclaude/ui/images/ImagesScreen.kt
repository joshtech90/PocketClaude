package de.smartzone.pocketclaude.ui.images

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.provider.MediaStore
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.IosShare
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import coil3.compose.AsyncImage
import de.smartzone.pocketclaude.PocketClaudeApp
import de.smartzone.pocketclaude.R
import de.smartzone.pocketclaude.data.AppSettings
import de.smartzone.pocketclaude.data.ImageGenerateAttachment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ImagesScreen(
    vm: ImageGenViewModel,
    onBack: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val state by vm.state.collectAsState()
    val context = LocalContext.current
    val container = remember {
        (context.applicationContext as PocketClaudeApp).container
    }
    val appSettings by container.settingsRepository.settingsFlow
        .collectAsState(initial = AppSettings())

    // Fullscreen-Vorschau
    var fullscreenAttachment by remember { mutableStateOf<ImageGenerateAttachment?>(null) }
    // Lösch-Bestätigung
    var entryToDelete by remember { mutableStateOf<GeneratedImageEntry?>(null) }
    var clearAllOpen by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.image_screen_title), style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
                actions = {
                    if (state.history.isNotEmpty()) {
                        IconButton(onClick = { clearAllOpen = true }) {
                            Icon(Icons.Filled.Delete, contentDescription = stringResource(R.string.image_clear_history))
                        }
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Filled.Settings, contentDescription = stringResource(R.string.image_open_settings))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { pad ->
        val cfg = state.config
        when {
            state.configLoading -> {
                Box(Modifier.fillMaxSize().padding(pad), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            cfg == null -> {
                Box(Modifier.fillMaxSize().padding(pad).padding(24.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            stringResource(R.string.image_config_load_failed),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            state.configError.orEmpty(),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                        Spacer(Modifier.height(16.dp))
                        FilledTonalButton(onClick = { vm.refreshConfig() }) {
                            Text(stringResource(R.string.action_retry))
                        }
                    }
                }
            }
            !cfg.configured -> {
                // Setup-Hinweis falls kein API-Key
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(pad)
                        .padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(
                        Icons.Filled.AutoAwesome,
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        stringResource(R.string.image_disabled_title),
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        stringResource(R.string.image_disabled_body),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(20.dp))
                    FilledTonalButton(onClick = onOpenSettings) {
                        Text(stringResource(R.string.image_open_settings_button))
                    }
                }
            }
            else -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(pad),
                ) {
                    // Generator-Card (oben, fix)
                    GeneratorCard(state = state, vm = vm)

                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)

                    // History
                    if (state.history.isEmpty()) {
                        Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                            Text(
                                stringResource(R.string.image_history_empty),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            )
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(vertical = 12.dp),
                        ) {
                            items(state.history, key = { it.timestampMs }) { entry ->
                                HistoryRow(
                                    entry = entry,
                                    serverBaseUrl = appSettings.serverUrl,
                                    serverToken = appSettings.serverToken,
                                    onImageClick = { att -> fullscreenAttachment = att },
                                    onDelete = { entryToDelete = entry },
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    // Fullscreen-Vorschau
    fullscreenAttachment?.let { att ->
        ImageFullscreenDialog(
            attachment = att,
            serverBaseUrl = appSettings.serverUrl,
            serverToken = appSettings.serverToken,
            onDismiss = { fullscreenAttachment = null },
        )
    }

    // Lösch-Bestätigung
    entryToDelete?.let { entry ->
        AlertDialog(
            onDismissRequest = { entryToDelete = null },
            title = { Text(stringResource(R.string.image_delete_generation_title)) },
            text = { Text(stringResource(R.string.image_delete_generation_body)) },
            confirmButton = {
                TextButton(onClick = {
                    vm.deleteEntry(entry)
                    entryToDelete = null
                }) { Text(stringResource(R.string.action_delete), color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { entryToDelete = null }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }

    if (clearAllOpen) {
        AlertDialog(
            onDismissRequest = { clearAllOpen = false },
            title = { Text(stringResource(R.string.image_clear_all_title)) },
            text = { Text(stringResource(R.string.image_clear_all_body)) },
            confirmButton = {
                TextButton(onClick = {
                    vm.clearHistory()
                    clearAllOpen = false
                }) { Text(stringResource(R.string.image_clear_all_confirm), color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { clearAllOpen = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GeneratorCard(state: ImageGenUiState, vm: ImageGenViewModel) {
    val cfg = state.config ?: return
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            // Prompt-Eingabe
            OutlinedTextField(
                value = state.prompt,
                onValueChange = vm::setPrompt,
                placeholder = { Text(stringResource(R.string.image_prompt_placeholder)) },
                maxLines = 4,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                enabled = !state.isGenerating,
            )

            // Modell-Dropdown
            var modelMenu by remember { mutableStateOf(false) }
            val modelDefaultLabel = stringResource(R.string.image_model_label)
            val currentLabel = cfg.models.firstOrNull { it.id == state.selectedModel }?.label
                ?: state.selectedModel ?: modelDefaultLabel
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(modifier = Modifier.weight(1f)) {
                    AssistChip(
                        onClick = { modelMenu = true },
                        label = { Text(currentLabel, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        leadingIcon = {
                            Icon(Icons.Filled.AutoAwesome, contentDescription = null,
                                modifier = Modifier.size(16.dp))
                        },
                        enabled = !state.isGenerating,
                    )
                    DropdownMenu(expanded = modelMenu, onDismissRequest = { modelMenu = false }) {
                        cfg.models.forEach { m ->
                            DropdownMenuItem(
                                text = {
                                    Column {
                                        Text(m.label, style = MaterialTheme.typography.bodyMedium)
                                        if (m.description.isNotBlank()) Text(
                                            m.description,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                },
                                onClick = { vm.setModel(m.id); modelMenu = false },
                            )
                        }
                    }
                }
            }

            // Aspect-Ratio
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                cfg.aspectRatios.forEach { a ->
                    FilterChip(
                        selected = a.id == state.selectedAspect,
                        onClick = { vm.setAspect(a.id) },
                        label = { Text(a.id) },
                        enabled = !state.isGenerating,
                    )
                }
            }

            // Anzahl
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    stringResource(R.string.image_variants_label),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                for (n in 1..cfg.maxCandidates) {
                    FilterChip(
                        selected = n == state.count,
                        onClick = { vm.setCount(n) },
                        label = { Text(n.toString()) },
                        enabled = !state.isGenerating,
                        colors = FilterChipDefaults.filterChipColors(),
                    )
                }
            }

            // Generate-Button + Status
            FilledTonalButton(
                onClick = { vm.generate() },
                enabled = !state.isGenerating && state.prompt.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.isGenerating) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.image_generating))
                } else {
                    Icon(Icons.Filled.AutoAwesome, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.image_generate_button))
                }
            }

            state.generationError?.let { err ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        err,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(onClick = vm::clearError) { Text(stringResource(R.string.action_ok)) }
                }
            }
        }
    }
}

@Composable
private fun HistoryRow(
    entry: GeneratedImageEntry,
    serverBaseUrl: String,
    serverToken: String,
    onImageClick: (ImageGenerateAttachment) -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f),
        ),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // Header: Prompt-Snippet + Delete-Button
            Row(verticalAlignment = Alignment.Top) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        entry.prompt,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        stringResource(R.string.image_meta_line, entry.model, entry.aspectRatio, entry.attachments.size),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(onClick = onDelete, modifier = Modifier.size(28.dp)) {
                    Icon(
                        Icons.Filled.Close,
                        contentDescription = stringResource(R.string.image_remove_entry),
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
            // Bilder-Reihe (horizontal)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                entry.attachments.forEach { att ->
                    val url = remember(serverBaseUrl, serverToken, att.id) {
                        "$serverBaseUrl/attachments/${att.id}?token=${android.net.Uri.encode(serverToken)}"
                    }
                    AsyncImage(
                        model = url,
                        contentDescription = att.filename,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .size(width = 140.dp, height = 140.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(MaterialTheme.colorScheme.surface)
                            .clickable { onImageClick(att) },
                    )
                }
            }
        }
    }
}

@Composable
private fun ImageFullscreenDialog(
    attachment: ImageGenerateAttachment,
    serverBaseUrl: String,
    serverToken: String,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val url = remember(serverBaseUrl, serverToken, attachment.id) {
        "$serverBaseUrl/attachments/${attachment.id}?token=${android.net.Uri.encode(serverToken)}"
    }
    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.scrim.copy(alpha = 0.85f))
                .clickable(onClick = onDismiss),
            contentAlignment = Alignment.Center,
        ) {
            AsyncImage(
                model = url,
                contentDescription = attachment.filename,
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f),
            )
            Row(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                FilledTonalButton(onClick = {
                    scope.launch { shareImage(context, serverBaseUrl, serverToken, attachment) }
                }) {
                    Icon(Icons.Filled.IosShare, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(stringResource(R.string.image_share_btn))
                }
                FilledTonalButton(onClick = {
                    scope.launch { saveImageToGallery(context, serverBaseUrl, serverToken, attachment) }
                }) {
                    Icon(Icons.Filled.Download, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(stringResource(R.string.image_save_btn))
                }
            }
        }
    }
}

/**
 * Lädt das Bild via OkHttp (mit Bearer-Token im URL-Query), schreibt es in
 * den App-Cache und teilt es via ACTION_SEND. Download + Datei-Schreiben laufen
 * auf Dispatchers.IO (Netz auf dem Main-Thread wirft NetworkOnMainThreadException),
 * der Chooser-Intent + Toast werden auf dem Main-Thread gepostet.
 */
private suspend fun shareImage(
    context: Context,
    serverBaseUrl: String,
    serverToken: String,
    att: ImageGenerateAttachment,
) {
    try {
        val intent = withContext(Dispatchers.IO) {
            val bytes = downloadImageBytes(serverBaseUrl, serverToken, att.id)
            val dir = java.io.File(context.cacheDir, "shared-images").apply { mkdirs() }
            val safeName = att.filename.replace(Regex("[^A-Za-z0-9._-]"), "_")
            val file = java.io.File(dir, safeName).also { it.writeBytes(bytes) }
            val uri = androidx.core.content.FileProvider.getUriForFile(
                context, "${context.packageName}.fileprovider", file,
            )
            Intent(Intent.ACTION_SEND).apply {
                type = att.mimeType
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }
        withContext(Dispatchers.Main) {
            context.startActivity(Intent.createChooser(intent, context.getString(R.string.image_share_chooser_title)))
        }
    } catch (e: Exception) {
        withContext(Dispatchers.Main) {
            Toast.makeText(context, context.getString(R.string.image_share_failed, e.message ?: ""), Toast.LENGTH_LONG).show()
        }
    }
}

/**
 * Speichert das Bild via MediaStore in die Galerie (Pictures/PocketClaude/).
 * Auf Android 10+ ist MediaStore der saubere Weg — keine WRITE_EXTERNAL_STORAGE-
 * Permission nötig, Scoped-Storage-konform. Download + MediaStore-Write laufen
 * auf Dispatchers.IO, der Toast wird auf dem Main-Thread gepostet.
 */
private suspend fun saveImageToGallery(
    context: Context,
    serverBaseUrl: String,
    serverToken: String,
    att: ImageGenerateAttachment,
) {
    try {
        withContext(Dispatchers.IO) {
            val bytes = downloadImageBytes(serverBaseUrl, serverToken, att.id)
            val ts = java.text.SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(java.util.Date())
            val ext = when {
                att.mimeType.contains("png") -> "png"
                att.mimeType.contains("webp") -> "webp"
                else -> "jpg"
            }
            val filename = "PocketClaude-$ts.$ext"
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, filename)
                put(MediaStore.Images.Media.MIME_TYPE, att.mimeType)
                put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/PocketClaude")
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw java.io.IOException("MediaStore insert failed")
            resolver.openOutputStream(uri)?.use { it.write(bytes) }
                ?: throw java.io.IOException("OutputStream null")
        }
        withContext(Dispatchers.Main) {
            Toast.makeText(context, context.getString(R.string.image_save_success), Toast.LENGTH_SHORT).show()
        }
    } catch (e: Exception) {
        withContext(Dispatchers.Main) {
            Toast.makeText(context, context.getString(R.string.image_save_failed, e.message ?: ""), Toast.LENGTH_LONG).show()
        }
    }
}

private fun downloadImageBytes(serverBaseUrl: String, serverToken: String, attId: String): ByteArray {
    val url = java.net.URL(
        "$serverBaseUrl/attachments/$attId?token=${java.net.URLEncoder.encode(serverToken, "UTF-8")}"
    )
    return url.openStream().use { it.readBytes() }
}
