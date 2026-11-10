package com.fisalia.waifugallery

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.content.pm.ActivityInfo
import android.net.Uri
import android.os.Bundle
import android.media.AudioManager
import android.provider.Settings
import android.view.GestureDetector
import android.view.MotionEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.Image
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.NavigateNext
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.NavigateBefore
import androidx.compose.material.icons.filled.NavigateNext
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.FullscreenExit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.blur
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.IntSize
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.content.FileProvider
import coil.ImageLoader
import coil.compose.AsyncImage
import coil.disk.DiskCache
import coil.request.ImageRequest
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlin.math.abs
import kotlin.math.min
import com.fisalia.waifugallery.data.BooruApi
import com.fisalia.waifugallery.data.ImagePost
import com.fisalia.waifugallery.data.RatingFilter
import com.fisalia.waifugallery.data.UserDataBackup
import com.fisalia.waifugallery.data.UserDataBackupCodec
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.security.GeneralSecurityException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private val AppBackground = Color(0xFF17171C)
private val Panel = Color(0xFF24242B)
private val Accent = Color(0xFF8057E8)

private fun Context.findActivity(): Activity? {
    var current: Context = this
    while (current is ContextWrapper) {
        if (current is Activity) return current
        current = current.baseContext
    }
    return current as? Activity
}

private fun Activity.currentScreenBrightness(): Float {
    val windowValue = window.attributes.screenBrightness
    if (windowValue >= 0f) return windowValue
    return try {
        Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS) / 255f
    } catch (_: Settings.SettingNotFoundException) {
        0.5f
    }
}

private fun openUpdateInstaller(context: Context, apk: File): String? {
    return try {
        val apkUri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apk,
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(apkUri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        null
    } catch (error: ActivityNotFoundException) {
        "No Android package installer is available."
    } catch (error: IllegalArgumentException) {
        "The downloaded APK could not be opened safely."
    } catch (error: SecurityException) {
        "Android blocked access to the downloaded APK."
    }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { WaifuGalleryApp() }
    }
}

@Composable
private fun WaifuGalleryApp(model: MainViewModel = viewModel()) {
    val state by model.state.collectAsState()
    val context = LocalContext.current
    val keyboardController = LocalSoftwareKeyboardController.current
    var pendingUpdateApk by remember { mutableStateOf<File?>(null) }
    val unknownSourcesSettings = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) {
        val apk = pendingUpdateApk
        pendingUpdateApk = null
        if (apk != null) {
            if (context.packageManager.canRequestPackageInstalls()) {
                openUpdateInstaller(context, apk)?.let(model::reportReleaseInstallError)
            } else {
                model.reportReleaseInstallError(
                    "Allow installs from Waifu Gallery in Android Settings, then try again.",
                )
            }
        }
    }
    val installUpdate: (String) -> Unit = { apkPath ->
        val apk = File(apkPath)
        if (!apk.isFile || apk.parentFile != File(context.cacheDir, "updates")) {
            model.reportReleaseInstallError("The downloaded APK could not be found.")
        } else if (!context.packageManager.canRequestPackageInstalls()) {
            pendingUpdateApk = apk
            try {
                unknownSourcesSettings.launch(
                    Intent(
                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:${context.packageName}"),
                    ),
                )
            } catch (error: ActivityNotFoundException) {
                pendingUpdateApk = null
                model.reportReleaseInstallError(
                    "Could not open Android's install-permission settings.",
                )
            }
        } else {
            openUpdateInstaller(context, apk)?.let(model::reportReleaseInstallError)
        }
    }
    var aboutPost by remember { mutableStateOf<ImagePost?>(null) }
    var confirmFavoriteRemoval by remember { mutableStateOf<ImagePost?>(null) }
    var showGalleryFilters by remember { mutableStateOf(false) }
    var mediaFullscreen by remember { mutableStateOf(false) }
    val activity = remember(context) { context.findActivity() }
    val fullscreenPost = when (state.screen) {
        AppScreen.RANDOM -> state.image
        AppScreen.DETAIL -> state.detailImage
        else -> null
    }
    var previousOrientation by rememberSaveable {
        mutableIntStateOf(activity?.requestedOrientation ?: ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED)
    }
    var orientationLocked by rememberSaveable { mutableStateOf(false) }
    val latestPreviousOrientation by rememberUpdatedState(previousOrientation)
    val latestOrientationLocked by rememberUpdatedState(orientationLocked)
    DisposableEffect(activity) {
        onDispose {
            activity?.window?.let {
                WindowCompat.getInsetsController(it, it.decorView)
                    .show(WindowInsetsCompat.Type.systemBars())
            }
            if (latestOrientationLocked) {
                activity?.requestedOrientation = latestPreviousOrientation
            }
        }
    }
    SideEffect {
        val controller = activity?.window?.let {
            WindowCompat.getInsetsController(it, it.decorView)
        }
        if (mediaFullscreen) {
            controller?.systemBarsBehavior =
                androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            controller?.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            controller?.show(WindowInsetsCompat.Type.systemBars())
        }
    }
    LaunchedEffect(mediaFullscreen, fullscreenPost?.id) {
        val currentActivity = activity ?: return@LaunchedEffect
        if (mediaFullscreen && fullscreenPost != null) {
            if (!orientationLocked) {
                previousOrientation = currentActivity.requestedOrientation
                orientationLocked = true
            }
            val dimensions = if (fullscreenPost.mediaType == "video") {
                fullscreenPost.videoVariants
                    .firstOrNull { it.width > 0 && it.height > 0 }
                    ?.let { it.width to it.height }
            } else {
                null
            }
            val width = dimensions?.first ?: fullscreenPost.width
            val height = dimensions?.second ?: fullscreenPost.height
            currentActivity.requestedOrientation = if (width > height) {
                ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            } else {
                ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT
            }
        } else if (orientationLocked) {
            currentActivity.requestedOrientation = previousOrientation
            orientationLocked = false
        }
    }
    LaunchedEffect(state.screen) {
        if (state.screen != AppScreen.GALLERY) showGalleryFilters = false
        if (state.screen != AppScreen.RANDOM && state.screen != AppScreen.DETAIL) {
            mediaFullscreen = false
        }
    }
    LaunchedEffect(state.screen, state.image?.id, state.detailImage?.id) {
        val currentPost = if (state.screen == AppScreen.DETAIL) state.detailImage else state.image
        if (currentPost?.mediaType != "video") mediaFullscreen = false
    }
    BackHandler(
        mediaFullscreen || state.screen == AppScreen.DETAIL || state.screen == AppScreen.FAVORITES,
    ) {
        if (mediaFullscreen) {
            mediaFullscreen = false
        } else if (state.screen == AppScreen.DETAIL) {
            model.backToGallery()
        } else {
            model.goHome()
        }
    }
    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri: Uri? ->
        uri?.let(model::rememberSaveFolder)
    }
    val imageLoader = remember(state.useDoh, state.dohProvider, state.customDohEndpoint) {
        val api = BooruApi(
            useDoh = { state.useDoh },
            gelbooruCredentials = { model.preferences.gelbooruUserId to model.preferences.gelbooruApiKey },
            rule34Credentials = { model.preferences.rule34UserId to model.preferences.rule34ApiKey },
            dohProvider = { state.dohProvider },
            customDohEndpoint = { state.customDohEndpoint },
        )
        ImageLoader.Builder(context)
            .okHttpClient(api.imageClient())
            .diskCache {
                DiskCache.Builder()
                    .directory(context.cacheDir.resolve("waifu-image-cache"))
                    .maxSizeBytes(128L * 1024 * 1024)
                    .build()
            }
            .crossfade(true)
            .build()
    }

    MaterialTheme(colorScheme = darkColorScheme(
        primary = Accent,
        onPrimary = Color.White,
        secondary = Color(0xFFB8A4FF),
        background = AppBackground,
        surface = Panel,
        onBackground = Color(0xFFF2F0F7),
        onSurface = Color(0xFFF2F0F7),
    )) {
        Surface(Modifier.fillMaxSize(), color = AppBackground) {
            if (state.screen == AppScreen.FAVORITES) {
                FavoritesScreen(
                    state = state,
                    imageLoader = imageLoader,
                    model = model,
                    modifier = Modifier.fillMaxSize(),
                    onRequestRemoval = { confirmFavoriteRemoval = it },
                    onClose = model::goHome,
                )
            } else {
                Scaffold(containerColor = AppBackground, topBar = {
                    if (!mediaFullscreen) HeaderBar(
                        isDetail = state.screen == AppScreen.DETAIL,
                        isGallery = state.screen == AppScreen.GALLERY,
                        showHome = state.screen == AppScreen.DETAIL && state.detailOrigin != AppScreen.RANDOM,
                        searchVisible = state.searchVisible && state.screen != AppScreen.DETAIL,
                        query = state.queryInput,
                        onQueryChanged = model::updateQuery,
                        onSearchSubmit = {
                            keyboardController?.hide()
                            model.search()
                        },
                        onBack = model::backToGallery,
                        onHome = model::goHome,
                        onRefresh = model::refresh,
                        onSearch = model::toggleSearch,
                        onSave = model::saveCurrentImage,
                        isFavorite = model.isFavorite(if (state.screen == AppScreen.DETAIL) state.detailImage else state.image),
                        onFavorite = {
                            val post = if (state.screen == AppScreen.DETAIL) state.detailImage else state.image
                            if (post != null) {
                                if (model.isFavorite(post)) confirmFavoriteRemoval = post else model.toggleFavorite(post)
                            }
                        },
                        onSettings = model::openSettings,
                        onOpenFilters = { showGalleryFilters = true },
                        onDownloads = model::openDownloadQueue,
                        onFavorites = model::openFavorites,
                        onAbout = { aboutPost = if (state.screen == AppScreen.DETAIL) state.detailImage else state.image },
                        canSave = when (state.screen) {
                            AppScreen.RANDOM -> state.image != null && !state.isLoading
                            AppScreen.DETAIL -> state.detailImage != null && !state.isLoading
                            AppScreen.GALLERY, AppScreen.FAVORITES -> false
                        },
                    )
                }) { padding ->
                    when (state.screen) {
                        AppScreen.RANDOM -> RandomScreen(
                            state,
                            imageLoader,
                            Modifier.padding(padding),
                            mediaFullscreen,
                            onFullscreenChanged = { mediaFullscreen = it },
                        )
                        AppScreen.GALLERY -> GalleryScreen(
                            state,
                            imageLoader,
                            model,
                            Modifier.padding(padding),
                            showFilters = showGalleryFilters,
                            onCloseFilters = { showGalleryFilters = false },
                        )
                        AppScreen.FAVORITES -> Unit
                        AppScreen.DETAIL -> DetailScreen(
                            state,
                            imageLoader,
                            onPageSelected = model::selectDetail,
                            onLoadAdjacentPage = model::loadAdjacentDetailPage,
                            modifier = Modifier.padding(padding),
                            mediaFullscreen = mediaFullscreen,
                            onFullscreenChanged = { mediaFullscreen = it },
                        )
                    }
                }
            }
        }
    state.error?.let { message ->
        AlertDialog(
            onDismissRequest = model::dismissError,
            title = { Text("Waifu Gallery") },
            text = { Text(message) },
            confirmButton = { TextButton(onClick = model::dismissError) { Text("Close") } },
        )
    }
    state.showSettings.let { visible ->
        if (visible) SettingsScreen(
            state = state,
            model = model,
            onChooseFolder = { folderPicker.launch(null) },
            onClose = model::closeSettings,
        )
    }
    if (state.requestGelbooruCredentials) {
        GelbooruCredentialsDialog(
            initialUserId = model.preferences.gelbooruUserId,
            initialApiKey = model.preferences.gelbooruApiKey,
            onSave = model::saveGelbooruCredentials,
            onDismiss = model::cancelGelbooruCredentials,
        )
    }
    if (state.requestRule34Credentials) {
        ProviderCredentialsDialog(
            provider = "Rule34.xxx",
            initialUserId = model.preferences.rule34UserId,
            initialApiKey = model.preferences.rule34ApiKey,
            onSave = model::saveRule34Credentials,
            onDismiss = model::cancelRule34Credentials,
        )
    }
    confirmFavoriteRemoval?.let { post ->
        AlertDialog(
            onDismissRequest = { confirmFavoriteRemoval = null },
            title = { Text("Remove favorite?") },
            text = { Text("Remove this image from your local favorites?") },
            confirmButton = {
                TextButton(onClick = { model.removeFavorite(post); confirmFavoriteRemoval = null }) { Text("Remove") }
            },
            dismissButton = { TextButton(onClick = { confirmFavoriteRemoval = null }) { Text("Cancel") } },
        )
    }
    aboutPost?.let { post ->
        AboutDialog(
            post = post,
            onDismiss = { aboutPost = null },
            onTagClick = { tag ->
                aboutPost = null
                model.searchTag(tag)
            },
        )
    }
    state.releaseUpdate?.let { update ->
        val downloadedUpdateApk = state.downloadedUpdateApk
        AlertDialog(
            onDismissRequest = {
                if (!state.isDownloadingReleaseUpdate) {
                    model.dismissReleaseUpdate()
                }
            },
            title = { Text("Update available") },
            text = {
                Box(Modifier.heightIn(max = 320.dp)) {
                    DialogMascot(
                        Modifier
                            .align(Alignment.BottomEnd)
                            .size(width = 112.dp, height = 168.dp),
                    )
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .padding(end = 88.dp)
                            .heightIn(max = 320.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("Waifu Gallery ${update.version}", fontWeight = FontWeight.SemiBold)
                        Text(update.notes.ifBlank { "A newer stable release is available." })
                        if (state.isDownloadingReleaseUpdate) {
                            val progress = state.releaseDownloadProgress
                            Text(if (progress == null) "Downloading APK..." else "Downloading APK... $progress%")
                            if (progress == null) {
                                LinearProgressIndicator(
                                    modifier = Modifier.fillMaxWidth(),
                                    color = Accent,
                                )
                            } else {
                                LinearProgressIndicator(
                                    progress = { progress / 100f },
                                    modifier = Modifier.fillMaxWidth(),
                                    color = Accent,
                                )
                            }
                        }
                        state.releaseDownloadError?.let { error ->
                            Text(error, color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            },
            confirmButton = {
                when {
                    downloadedUpdateApk != null -> TextButton(
                        onClick = { installUpdate(downloadedUpdateApk) },
                    ) {
                        Text("Install update")
                    }
                    state.isDownloadingReleaseUpdate -> TextButton(
                        onClick = {},
                        enabled = false,
                    ) {
                        Text("Downloading...")
                    }
                    else -> TextButton(onClick = model::downloadReleaseUpdate) {
                        Text(if (state.releaseDownloadError == null) "Download APK" else "Retry download")
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = model::dismissReleaseUpdate,
                    enabled = !state.isDownloadingReleaseUpdate,
                ) { Text("Later") }
            },
        )
    }
    if (state.showDownloadQueue) {
        DownloadQueueScreen(
            downloads = state.downloads,
            onOpen = model::openSavedDownload,
            onRetry = model::retryDownload,
            onClearFinished = model::clearFinishedDownloads,
            onDismiss = model::closeDownloadQueue,
        )
    }
    state.notice?.let { message ->
        LaunchedEffect(message) {
            kotlinx.coroutines.delay(2200)
            model.dismissNotice()
        }
        Box(Modifier.fillMaxSize().padding(bottom = 24.dp), contentAlignment = Alignment.BottomCenter) {
            Surface(
                shape = RoundedCornerShape(24.dp),
                color = Color(0xFF35323E),
                contentColor = Color.White,
            ) {
                Text(
                    message,
                    Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                    color = Color.White,
                )
            }
        }
    }
    }
}

@Composable
private fun HeaderBar(
    isDetail: Boolean,
    isGallery: Boolean,
    showHome: Boolean,
    searchVisible: Boolean,
    query: String,
    onQueryChanged: (String) -> Unit,
    onSearchSubmit: () -> Unit,
    onBack: () -> Unit,
    onHome: () -> Unit,
    onRefresh: () -> Unit,
    onSearch: () -> Unit,
    onSave: () -> Unit,
    isFavorite: Boolean,
    onFavorite: () -> Unit,
    onSettings: () -> Unit,
    onOpenFilters: () -> Unit,
    onDownloads: () -> Unit,
    onFavorites: () -> Unit,
    onAbout: () -> Unit,
    canSave: Boolean,
) {
    var settingsMenuExpanded by remember { mutableStateOf(false) }
    Surface(color = Panel) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(58.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            if (isDetail) {
                IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back to results") }
            } else {
                IconButton(onClick = onRefresh) { Icon(Icons.Default.Refresh, "Refresh") }
            }
            if (showHome) IconButton(onClick = onHome) { Icon(Icons.Default.Home, "Home") }
            if (searchVisible) {
                BasicTextField(
                    value = query,
                    onValueChange = onQueryChanged,
                    modifier = Modifier
                        .weight(1f)
                        .height(42.dp)
                        .offset(y = 3.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFF303038))
                        .padding(horizontal = 10.dp),
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodyLarge.copy(color = MaterialTheme.colorScheme.onSurface),
                    decorationBox = { innerTextField ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Search, contentDescription = null, tint = Color.LightGray)
                            Box(Modifier.weight(1f).padding(horizontal = 8.dp)) {
                                if (query.isEmpty()) {
                                    Text("Search name or tags", maxLines = 1, color = Color.LightGray, style = MaterialTheme.typography.bodyMedium)
                                }
                                innerTextField()
                            }
                            if (query.isNotEmpty()) {
                                Icon(
                                    Icons.Default.Close,
                                    contentDescription = "Clear search",
                                    tint = Color.LightGray,
                                    modifier = Modifier
                                        .size(32.dp)
                                        .clickable { onQueryChanged("") }
                                        .padding(6.dp),
                                )
                            }
                        }
                    },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { onSearchSubmit() }),
                )
                IconButton(onClick = onSearch) { Icon(Icons.Default.Close, "Close search") }
            } else {
                if (!isDetail) IconButton(onClick = onSearch) { Icon(Icons.Default.Search, "Search") }
                Spacer(Modifier.weight(1f))
            }
            if (canSave && !searchVisible) IconButton(onClick = onSave) { Icon(Icons.Default.Download, "Save image") }
            if (canSave && !searchVisible) IconButton(onClick = onAbout) { Icon(Icons.Default.Info, "Media info") }
            if (canSave && !searchVisible) IconButton(onClick = onFavorite) {
                Icon(if (isFavorite) Icons.Default.Favorite else Icons.Default.FavoriteBorder, if (isFavorite) "Remove favorite" else "Add favorite", tint = if (isFavorite) Accent else MaterialTheme.colorScheme.onSurface)
            }
            Box {
                IconButton(onClick = { settingsMenuExpanded = true }) { Icon(Icons.Default.MoreVert, "More options") }
                DropdownMenu(expanded = settingsMenuExpanded, onDismissRequest = { settingsMenuExpanded = false }) {
                    if (isGallery) {
                        DropdownMenuItem(
                            text = { Text("Filters") },
                            onClick = { settingsMenuExpanded = false; onOpenFilters() },
                        )
                    }
                    DropdownMenuItem(
                        text = { Text("Settings") },
                        onClick = { settingsMenuExpanded = false; onSettings() },
                    )
                    DropdownMenuItem(
                        text = { Text("Downloads") },
                        onClick = { settingsMenuExpanded = false; onDownloads() },
                    )
                    DropdownMenuItem(
                        text = { Text("Favorites") },
                        onClick = { settingsMenuExpanded = false; onFavorites() },
                    )
                }
            }
        }
    }
}

@Composable
private fun DialogMascot(modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(R.drawable.waifu_mascot_iro),
        contentDescription = null,
        modifier = modifier.graphicsLayer { alpha = 0.5f },
        contentScale = ContentScale.Fit,
    )
}

@Composable
private fun RandomScreen(
    state: UiState,
    imageLoader: ImageLoader,
    modifier: Modifier = Modifier,
    mediaFullscreen: Boolean = false,
    onFullscreenChanged: (Boolean) -> Unit = {},
) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        state.image?.let { post ->
            ImageFrame(
                post.imageUrl,
                post,
                imageLoader,
                Modifier.fillMaxSize(),
                zoomEnabled = true,
                showLoadingIndicator = !state.isLoading,
                ambientMode = state.ambientMode,
                videoMaxHeight = state.videoMaxHeight,
                mediaFullscreen = mediaFullscreen,
                onFullscreenChanged = onFullscreenChanged,
            )
        }
        if (state.image == null && !state.isLoading) Text("No image loaded")
        if (state.isLoading) LoadingSpinner(Modifier.align(Alignment.Center))
    }
}

@Composable
private fun GalleryScreen(
    state: UiState,
    imageLoader: ImageLoader,
    model: MainViewModel,
    modifier: Modifier = Modifier,
    showFilters: Boolean,
    onCloseFilters: () -> Unit,
) {
    val gridState = rememberLazyGridState()
    LaunchedEffect(state.page, state.galleryQuery, state.galleryProvider, state.rating) {
        gridState.scrollToItem(0)
    }
    Column(modifier.fillMaxSize().padding(horizontal = 10.dp)) {
        Text("${state.galleryProvider}  |  ${state.rating.label}", Modifier.padding(bottom = 5.dp), style = MaterialTheme.typography.labelSmall, color = Color.LightGray)
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (state.gallery.isNotEmpty()) {
                LazyVerticalGrid(
                    state = gridState,
                    columns = GridCells.Adaptive(minSize = 145.dp),
                    contentPadding = PaddingValues(bottom = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.gallery, key = { it.id }) { post ->
                        Card(
                            modifier = Modifier.fillMaxWidth().aspectRatio(0.95f).clickable { model.openDetail(post) },
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = Panel),
                        ) {
                            Box(Modifier.fillMaxSize()) {
                                ImageFrame(
                                    post.thumbnailUrl,
                                    post,
                                    imageLoader,
                                    Modifier.fillMaxSize(),
                                    allowThumbnailFallback = true,
                                )
                                if (post.mediaType == "video") {
                                    VideoPlayBadge(Modifier.align(Alignment.Center))
                                }
                            }
                        }
                    }
                }
            }
            if (state.isLoading) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                LoadingSpinner()
            }
            if (!state.isLoading && state.gallery.isEmpty()) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                if (state.galleryProviderErrors.isEmpty()) {
                    Text("No images found")
                } else {
                    Column(
                        Modifier.padding(horizontal = 24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Text("No results from available providers")
                        Text(
                            state.galleryProviderErrors.joinToString("\n"),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        TextButton(onClick = model::refresh) { Text("Try again") }
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { model.changePage(-1) }, enabled = state.page > 1) {
                Icon(Icons.Default.NavigateBefore, contentDescription = null); Text("Previous")
            }
            val pageCount = state.totalPages?.toString() ?: if (state.hasMore) "..." else state.page.toString()
            val imageCount = state.gallery.count { it.mediaType != "video" }
            val videoCount = state.gallery.size - imageCount
            val mediaCount = when (state.mediaFilter) {
                "video" -> "$videoCount videos"
                "all" -> "$imageCount images, $videoCount videos"
                else -> "$imageCount images"
            }
            Text("${state.page}/$pageCount  |  $mediaCount", Modifier.padding(horizontal = 8.dp), style = MaterialTheme.typography.labelMedium)
            TextButton(onClick = { model.changePage(1) }, enabled = state.hasMore) {
                Text("Next"); Icon(Icons.Default.NavigateNext, contentDescription = null)
            }
        }
    }
    if (showFilters) {
        GalleryFiltersDialog(
            selectedProvider = state.galleryProvider,
            selectedRating = state.rating,
            allowNsfw = state.allowNsfw,
            onDismiss = onCloseFilters,
            onApply = { provider, rating ->
                onCloseFilters()
                model.setGalleryFilters(provider, rating)
            },
        )
    }
}

@Composable
private fun VideoPlayBadge(
    modifier: Modifier = Modifier,
    label: String? = null,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(50.dp),
        color = Color(0xCC15151A),
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = if (label == null) 8.dp else 10.dp,
                vertical = 6.dp,
            ),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Default.PlayArrow,
                contentDescription = if (label == null) "Video" else null,
                modifier = Modifier.size(22.dp),
                tint = Color.White,
            )
            if (label != null) {
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.White,
                )
            }
        }
    }
}

@Composable
private fun GalleryFiltersDialog(
    selectedProvider: String,
    selectedRating: RatingFilter,
    allowNsfw: Boolean,
    onDismiss: () -> Unit,
    onApply: (String, RatingFilter) -> Unit,
) {
    var provider by remember(selectedProvider) { mutableStateOf(selectedProvider) }
    var rating by remember(selectedRating) { mutableStateOf(selectedRating) }
    var providerMenu by remember { mutableStateOf(false) }
    var ratingMenu by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Filters") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Provider", fontWeight = FontWeight.SemiBold)
                Box {
                    OutlinedButton(onClick = { providerMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Text(provider, Modifier.weight(1f))
                        Icon(Icons.Default.ArrowDropDown, contentDescription = "Choose provider")
                    }
                    DropdownMenu(expanded = providerMenu, onDismissRequest = { providerMenu = false }) {
                        listOf("All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx").forEach { option ->
                            DropdownMenuItem(
                                text = { Text(option) },
                                trailingIcon = { if (provider == option) Icon(Icons.Default.Check, contentDescription = "Selected") },
                                onClick = { provider = option; providerMenu = false },
                            )
                        }
                    }
                }

                Text("Rating", fontWeight = FontWeight.SemiBold)
                if (!allowNsfw) {
                    Text(
                        "Enable NSFW results in Settings to use other ratings.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.LightGray,
                    )
                }
                Box {
                    OutlinedButton(onClick = { ratingMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Text(rating.label, Modifier.weight(1f))
                        Icon(Icons.Default.ArrowDropDown, contentDescription = "Choose rating")
                    }
                    DropdownMenu(expanded = ratingMenu, onDismissRequest = { ratingMenu = false }) {
                        RatingFilter.entries.filter { allowNsfw || it == RatingFilter.SFW }.forEach { option ->
                            DropdownMenuItem(
                                text = { Text(option.label) },
                                trailingIcon = { if (rating == option) Icon(Icons.Default.Check, contentDescription = "Selected") },
                                onClick = { rating = option; ratingMenu = false },
                            )
                        }
                    }
                }
            }
        },
        confirmButton = { Button(onClick = { onApply(provider, rating) }) { Text("Apply") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun FavoritesScreen(
    state: UiState,
    imageLoader: ImageLoader,
    model: MainViewModel,
    modifier: Modifier = Modifier,
    onRequestRemoval: (ImagePost) -> Unit,
    onClose: () -> Unit,
) {
    val imageCount = state.favorites.count { it.mediaType != "video" }
    val videoCount = state.favorites.size - imageCount
    Surface(modifier.fillMaxSize(), color = AppBackground) {
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier.fillMaxWidth().statusBarsPadding().height(64.dp).padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onClose) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to gallery")
                }
                Column {
                    Text("Favorites", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                    Text(
                        "$imageCount images, $videoCount videos",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (state.favorites.isEmpty()) {
                Box(
                    Modifier.weight(1f).fillMaxWidth().navigationBarsPadding(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("No favorites yet")
                }
            } else {
                LazyVerticalGrid(
                    modifier = Modifier.weight(1f).fillMaxWidth().navigationBarsPadding(),
                    columns = GridCells.Adaptive(minSize = 145.dp),
                    contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 8.dp, bottom = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.favorites, key = { it.id }) { post ->
                        Box(Modifier.fillMaxWidth().aspectRatio(0.95f)) {
                            ImageFrame(
                                post.thumbnailUrl,
                                post,
                                imageLoader,
                                Modifier.fillMaxSize().clickable { model.openDetail(post) },
                                allowThumbnailFallback = true,
                                showMetadata = false,
                            )
                            if (post.mediaType == "video") {
                                VideoPlayBadge(
                                    modifier = Modifier.align(Alignment.Center),
                                    label = "VIDEO",
                                )
                            }
                            IconButton(
                                onClick = { onRequestRemoval(post) },
                                modifier = Modifier.align(Alignment.TopEnd),
                            ) {
                                Icon(Icons.Default.Favorite, "Remove from favorites", tint = Accent)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailScreen(
    state: UiState,
    imageLoader: ImageLoader,
    onPageSelected: (Int) -> Unit,
    onLoadAdjacentPage: (Int) -> Unit,
    modifier: Modifier = Modifier,
    mediaFullscreen: Boolean = false,
    onFullscreenChanged: (Boolean) -> Unit = {},
) {
    val posts = state.detailPosts
    val selectedIndex = posts.indexOfFirst { it.id == state.detailImage?.id }.coerceAtLeast(0)
    val pagerState = rememberPagerState(initialPage = selectedIndex, pageCount = { posts.size.coerceAtLeast(1) })
    val pagerScope = rememberCoroutineScope()

    LaunchedEffect(pagerState.currentPage, posts) {
        posts.getOrNull(pagerState.currentPage)?.let { post ->
            if (post.id != state.detailImage?.id) onPageSelected(pagerState.currentPage)
        }
    }
    LaunchedEffect(selectedIndex) {
        if (selectedIndex != pagerState.currentPage) pagerState.scrollToPage(selectedIndex)
    }
    LaunchedEffect(pagerState.currentPage, posts.size, state.detailFirstPage, state.detailLastPage, state.detailLoadingPrevious, state.detailLoadingNext, state.detailPreviousFailed, state.detailNextFailed) {
        if (posts.isEmpty()) return@LaunchedEffect
        if (!state.detailNextFailed && pagerState.currentPage >= posts.lastIndex - 2 && (state.totalPages?.let { state.detailLastPage < it } ?: state.detailHasMore)) {
            onLoadAdjacentPage(1)
        }
        if (!state.detailPreviousFailed && pagerState.currentPage <= 1 && state.detailFirstPage > 1) onLoadAdjacentPage(-1)
    }

    Column(modifier.fillMaxSize()) {
        Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
        if (posts.isNotEmpty()) {
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.fillMaxSize(),
                beyondViewportPageCount = 1,
                key = { page -> posts[page].id },
            ) { page ->
                val post = posts[page]
                ImageFrame(
                    post.imageUrl,
                    post,
                    imageLoader,
                    Modifier.fillMaxSize(),
                    zoomEnabled = true,
                    showLoadingIndicator = true,
                    showMetadata = false,
                    ambientMode = state.ambientMode,
                    playbackAllowed = page == pagerState.currentPage,
                    videoMaxHeight = state.videoMaxHeight,
                    mediaFullscreen = mediaFullscreen,
                    onFullscreenChanged = onFullscreenChanged,
                )
            }
        } else {
            state.detailImage?.let { post ->
                ImageFrame(
                    post.imageUrl,
                    post,
                    imageLoader,
                    Modifier.fillMaxSize(),
                    zoomEnabled = true,
                    ambientMode = state.ambientMode,
                    videoMaxHeight = state.videoMaxHeight,
                    mediaFullscreen = mediaFullscreen,
                    onFullscreenChanged = onFullscreenChanged,
                )
            }
        }
        }
        if (posts.isNotEmpty() && !mediaFullscreen) {
            val absoluteIndex = (state.detailFirstPage - 1) * 50 + pagerState.currentPage + 1
            val total = state.totalResults ?: state.totalPages?.times(50)
            Surface(
                Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
                color = Panel,
                shape = RoundedCornerShape(12.dp),
            ) {
                Row(
                    Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center,
                ) {
                    if (state.detailOrigin == AppScreen.FAVORITES) {
                        IconButton(
                            onClick = { pagerScope.launch { pagerState.animateScrollToPage(pagerState.currentPage - 1) } },
                            enabled = pagerState.currentPage > 0,
                        ) { Icon(Icons.Default.NavigateBefore, contentDescription = "Previous favorite") }
                    }
                    if (state.detailLoadingNext || state.detailLoadingPrevious) {
                        CircularProgressIndicator(color = Accent, modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                    }
                    Text("$absoluteIndex/${total ?: "..."}", style = MaterialTheme.typography.labelMedium)
                    if (state.detailOrigin == AppScreen.FAVORITES) {
                        IconButton(
                            onClick = { pagerScope.launch { pagerState.animateScrollToPage(pagerState.currentPage + 1) } },
                            enabled = pagerState.currentPage < posts.lastIndex,
                        ) { Icon(Icons.Default.NavigateNext, contentDescription = "Next favorite") }
                    }
                }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ImageFrame(
    url: String,
    post: ImagePost,
    imageLoader: ImageLoader,
    modifier: Modifier = Modifier,
    allowThumbnailFallback: Boolean = false,
    zoomEnabled: Boolean = false,
    showLoadingIndicator: Boolean = false,
    showMetadata: Boolean = true,
    ambientMode: Boolean = false,
    playbackAllowed: Boolean = true,
    videoMaxHeight: Int = 0,
    mediaFullscreen: Boolean = false,
    onFullscreenChanged: (Boolean) -> Unit = {},
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val activity = remember(context) { context.findActivity() }
    val metadataControlInset = if (
        post.mediaType == "video" && !allowThumbnailFallback && !mediaFullscreen
    ) 78.dp else 0.dp
    var candidateIndex by remember(post.id, url) { mutableStateOf(0) }
    var showOriginal by remember(post.id) { mutableStateOf(false) }
    val candidates = when {
        allowThumbnailFallback -> post.thumbnailCandidates
        post.mediaType != "video" && zoomEnabled && !showOriginal ->
            post.thumbnailCandidates.filterNot { it == post.imageUrl }
        else -> emptyList()
    }.ifEmpty { listOf(if (showOriginal) post.imageUrl else url) }
    val displayedUrl = candidates[candidateIndex.coerceAtMost(candidates.lastIndex)]
    val canLoadOriginal = post.mediaType != "video" &&
        zoomEnabled &&
        !allowThumbnailFallback &&
        !showOriginal &&
        post.thumbnailCandidates.any { it != post.imageUrl }
    var imageLoading by remember(post.id, url) { mutableStateOf(true) }
    var zoom by remember(post.id) { mutableFloatStateOf(1f) }
    var pan by remember(post.id) { mutableStateOf(Offset.Zero) }
    var viewportSize by remember(post.id) { mutableStateOf(IntSize.Zero) }
    fun constrainPan(offset: Offset, scale: Float): Offset {
        val viewportWidth = viewportSize.width.toFloat()
        val viewportHeight = viewportSize.height.toFloat()
        if (viewportWidth <= 0f || viewportHeight <= 0f) return Offset.Zero
        val imageWidth = post.width.takeIf { it > 0 }?.toFloat() ?: viewportWidth
        val imageHeight = post.height.takeIf { it > 0 }?.toFloat() ?: viewportHeight
        val fitScale = min(viewportWidth / imageWidth, viewportHeight / imageHeight)
        val maxPanX = ((imageWidth * fitScale * scale - viewportWidth) / 2f).coerceAtLeast(0f)
        val maxPanY = ((imageHeight * fitScale * scale - viewportHeight) / 2f).coerceAtLeast(0f)
        return Offset(
            offset.x.coerceIn(-maxPanX, maxPanX),
            offset.y.coerceIn(-maxPanY, maxPanY),
        )
    }
    val transformState = rememberTransformableState { zoomChange, panChange, _ ->
        val newZoom = (zoom * zoomChange).coerceIn(1f, 6f)
        zoom = newZoom
        pan = if (newZoom <= 1f) Offset.Zero else constrainPan(pan + panChange, newZoom)
    }
    val currentZoom by rememberUpdatedState(zoom)
    val currentPan by rememberUpdatedState(pan)
    val zoomGesture = if (zoomEnabled) {
        Modifier
            .pointerInput(post.id) {
                detectTapGestures(
                    onDoubleTap = { tap ->
                        val oldZoom = currentZoom
                        if (oldZoom > 1f) {
                            zoom = 1f
                            pan = Offset.Zero
                        } else {
                            val newZoom = 2.5f
                            val ratio = newZoom / oldZoom
                            val centerX = size.width / 2f
                            val centerY = size.height / 2f
                            pan = Offset(
                                (tap.x - centerX) * (1f - ratio) + currentPan.x * ratio,
                                (tap.y - centerY) * (1f - ratio) + currentPan.y * ratio,
                            ).let { constrainPan(it, newZoom) }
                            zoom = newZoom
                        }
                    },
                )
            }
            .transformable(
                state = transformState,
                canPan = { zoom > 1f },
            )
    } else Modifier
    var videoPlaying by remember(post.id) { mutableStateOf(false) }
    var videoStarted by remember(post.id) { mutableStateOf(false) }
    var videoPrepared by remember(post.id) { mutableStateOf(false) }
    var videoView by remember(post.id) { mutableStateOf<android.widget.VideoView?>(null) }
    val currentVideoPlaying by rememberUpdatedState(videoPlaying)
    var videoDuration by remember(post.id) { mutableStateOf(0) }
    var videoPosition by remember(post.id) { mutableStateOf(0) }
    var videoError by remember(post.id) { mutableStateOf(false) }
    var videoBuffering by remember(post.id) { mutableStateOf(false) }
    var videoFeedback by remember(post.id) { mutableStateOf<String?>(null) }
    LaunchedEffect(videoFeedback) {
        if (videoFeedback != null) {
            delay(900)
            videoFeedback = null
        }
    }
    LaunchedEffect(post.id, playbackAllowed) {
        if (!playbackAllowed) {
            videoPlaying = false
            videoStarted = false
            videoPrepared = false
            videoError = false
            videoBuffering = false
        }
    }
    LaunchedEffect(post.id, videoMaxHeight) {
        videoPlaying = false
        videoStarted = false
        videoPrepared = false
    }
    LaunchedEffect(videoPlaying, videoView) {
        while (videoPlaying) {
            val player = videoView ?: break
            videoPosition = player.currentPosition.coerceAtLeast(0)
            delay(500)
        }
    }
    DisposableEffect(lifecycleOwner, post.id) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_PAUSE) videoPlaying = false
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    Box(
        modifier
            .background(Color.Transparent)
            .onSizeChanged { viewportSize = IntSize(it.width, it.height) }
            .then(if (post.mediaType == "video") Modifier else zoomGesture),
        contentAlignment = Alignment.Center,
    ) {
        if (ambientMode) AsyncImage(
            model = ImageRequest.Builder(LocalContext.current).data(if (post.mediaType == "video") post.thumbnailUrl else displayedUrl).build(),
            imageLoader = imageLoader,
            contentDescription = null,
            modifier = Modifier.fillMaxSize().blur(28.dp).graphicsLayer { scaleX = 1.12f; scaleY = 1.12f },
            contentScale = ContentScale.Crop,
        )
        if (post.mediaType == "video" && videoStarted && playbackAllowed && !allowThumbnailFallback && !videoError) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { context ->
                    android.widget.VideoView(context).apply {
                        val playerView = this
                        videoView = playerView
                        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                        var volumeDrag = 0f
                        val gestureDetector = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
                            override fun onDown(event: MotionEvent): Boolean = true

                            override fun onDoubleTap(event: MotionEvent): Boolean {
                                val duration = playerView.duration
                                if (duration <= 0) return false
                                val forward = event.x >= playerView.width / 2f
                                val destination = (playerView.currentPosition + (if (forward) 5_000 else -5_000))
                                    .coerceIn(0, (duration - 1).coerceAtLeast(0))
                                playerView.seekTo(destination)
                                videoFeedback = if (forward) "+5 seconds" else "-5 seconds"
                                return true
                            }

                            override fun onScroll(
                                first: MotionEvent?,
                                current: MotionEvent,
                                distanceX: Float,
                                distanceY: Float,
                            ): Boolean {
                                val start = first ?: return false
                                if (abs(distanceY) <= abs(distanceX)) return false
                                if (start.x < playerView.width / 2f) {
                                    val currentActivity = activity ?: return false
                                    val window = currentActivity.window
                                    val params = window.attributes
                                    val brightness = if (params.screenBrightness >= 0f) {
                                        params.screenBrightness
                                    } else {
                                        currentActivity.currentScreenBrightness()
                                    }
                                    params.screenBrightness =
                                        (brightness + distanceY / playerView.height.coerceAtLeast(1).toFloat()).coerceIn(0.01f, 1f)
                                    window.attributes = params
                                    videoFeedback = "Brightness ${(params.screenBrightness * 100).toInt()}%"
                                } else {
                                    val maximum = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                                    if (maximum <= 0) return false
                                    volumeDrag += distanceY
                                    val pixelsPerStep = (playerView.height.toFloat() / maximum / 2f).coerceAtLeast(8f)
                                    val steps = (volumeDrag / pixelsPerStep).toInt()
                                    if (steps != 0) {
                                        volumeDrag -= steps * pixelsPerStep
                                        val volume = (audioManager.getStreamVolume(AudioManager.STREAM_MUSIC) + steps)
                                            .coerceIn(0, maximum)
                                        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, volume, 0)
                                    }
                                    val volume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                                    videoFeedback = "Volume ${volume * 100 / maximum}%"
                                }
                                return true
                            }
                        })
                        setOnTouchListener { _, event ->
                            gestureDetector.onTouchEvent(event)
                            false
                        }
                        val headers = when (post.provider) {
                            "Gelbooru" -> mapOf("Referer" to "https://gelbooru.com/")
                            "Rule34.xxx" -> mapOf("Referer" to "https://rule34.xxx/")
                            else -> emptyMap()
                        }
                        val videoUrl = if (videoMaxHeight > 0) {
                            post.videoVariants
                                .filter { it.height in 1..videoMaxHeight }
                                .maxByOrNull { it.height }
                                ?.url
                                ?: post.imageUrl
                        } else {
                            post.imageUrl
                        }
                        setOnPreparedListener { player ->
                            player.isLooping = true
                            videoDuration = player.duration.coerceAtLeast(0)
                            videoBuffering = false
                            videoPrepared = true
                            if (currentVideoPlaying) playerView.start() else playerView.pause()
                        }
                        setOnInfoListener { _, what, _ ->
                            when (what) {
                                android.media.MediaPlayer.MEDIA_INFO_BUFFERING_START -> {
                                    videoBuffering = true
                                    true
                                }
                                android.media.MediaPlayer.MEDIA_INFO_BUFFERING_END -> {
                                    videoBuffering = false
                                    true
                                }
                                else -> false
                            }
                        }
                        setOnErrorListener { _, _, _ ->
                            videoPrepared = false
                            videoError = true
                            videoPlaying = false
                            videoBuffering = false
                            true
                        }
                        setVideoURI(Uri.parse(videoUrl), headers)
                    }
                },
                update = { view ->
                    if (videoPrepared) {
                        if (videoPlaying && !view.isPlaying) view.start()
                        else if (!videoPlaying && view.isPlaying) view.pause()
                    }
                },
                onRelease = {
                    if (videoView === it) videoView = null
                    it.stopPlayback()
                },
            )
        } else {
        AsyncImage(
            model = ImageRequest.Builder(LocalContext.current).data(if (post.mediaType == "video") post.thumbnailUrl else displayedUrl).crossfade(true).build(),
            imageLoader = imageLoader,
            contentDescription = "${post.provider} image, rating ${post.rating}",
            modifier = Modifier.fillMaxSize().graphicsLayer {
                scaleX = if (zoomEnabled) zoom else 1f
                scaleY = if (zoomEnabled) zoom else 1f
                translationX = if (zoomEnabled) pan.x else 0f
                translationY = if (zoomEnabled) pan.y else 0f
            },
            contentScale = ContentScale.Fit,
            onLoading = { imageLoading = true },
            onSuccess = { imageLoading = false },
            onError = {
                if (candidateIndex < candidates.lastIndex) {
                    candidateIndex++
                    imageLoading = true
                } else {
                    imageLoading = false
                }
            },
        )
        }
        if (post.mediaType == "video" && !videoStarted && !videoError && !allowThumbnailFallback) {
            Surface(
                modifier = Modifier.align(Alignment.Center).size(68.dp).clickable {
                    videoError = false
                    videoStarted = true
                    videoPlaying = true
                },
                shape = RoundedCornerShape(50.dp), color = Color(0xBB111118),
            ) { Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.PlayArrow, "Play video", tint = Color.White, modifier = Modifier.size(44.dp)) } }
        }
        if (post.mediaType == "video" && videoError && !allowThumbnailFallback) {
            Surface(
                modifier = Modifier.align(Alignment.Center).padding(16.dp),
                color = Color(0xDD15151A),
                shape = RoundedCornerShape(12.dp),
            ) {
                Column(
                    Modifier.padding(horizontal = 18.dp, vertical = 12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text("Video could not be played", style = MaterialTheme.typography.bodyMedium)
                    TextButton(onClick = { videoError = false; videoStarted = true; videoPlaying = true }) { Text("Try again") }
                }
            }
        }
        if (post.mediaType == "video" && playbackAllowed && !allowThumbnailFallback && !videoError) {
            Surface(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(8.dp),
                color = Color(0xEE1C1E28),
                shape = RoundedCornerShape(12.dp),
            ) {
                Row(
                    Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconButton(
                        onClick = {
                            if (videoStarted) {
                                videoPlaying = !videoPlaying
                                if (!videoPlaying) videoBuffering = false
                            } else {
                                videoStarted = true
                                videoPlaying = true
                            }
                        },
                        enabled = playbackAllowed,
                    ) {
                        Icon(
                            if (videoPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                            contentDescription = if (videoPlaying) "Pause video" else "Play video",
                        )
                    }
                    Slider(
                        value = videoPosition.toFloat().coerceIn(0f, videoDuration.toFloat().coerceAtLeast(1f)),
                        onValueChange = { videoPosition = it.toInt() },
                        onValueChangeFinished = { videoView?.seekTo(videoPosition) },
                        valueRange = 0f..videoDuration.toFloat().coerceAtLeast(1f),
                        enabled = videoDuration > 0,
                        modifier = Modifier.weight(1f),
                        thumb = {
                            Box(
                                Modifier
                                    .graphicsLayer { translationY = 4.dp.toPx() }
                                    .size(8.dp)
                                    .background(Color(0xFFE5E7EB), RoundedCornerShape(50)),
                            )
                        },
                        track = { sliderState ->
                            Canvas(
                                Modifier
                                    .fillMaxWidth()
                                    .height(24.dp),
                            ) {
                                val centerY = size.height / 2
                                val trackHeight = 2.dp.toPx()
                                val progressX = size.width * sliderState.coercedValueAsFraction
                                drawLine(
                                    color = Color(0xFF55565E),
                                    start = Offset(0f, centerY),
                                    end = Offset(size.width, centerY),
                                    strokeWidth = trackHeight,
                                    cap = StrokeCap.Round,
                                )
                                if (progressX > 0f) {
                                    drawLine(
                                        color = Color(0xFFB8BBC2),
                                        start = Offset(0f, centerY),
                                        end = Offset(progressX, centerY),
                                        strokeWidth = trackHeight,
                                        cap = StrokeCap.Round,
                                    )
                                }
                            }
                        },
                    )
                    Text(
                        "${formatPlaybackTime(videoPosition)}/${formatPlaybackTime(videoDuration)}",
                        style = MaterialTheme.typography.labelSmall,
                    )
                    IconButton(onClick = { onFullscreenChanged(!mediaFullscreen) }) {
                        Icon(
                            if (mediaFullscreen) Icons.Default.FullscreenExit else Icons.Default.Fullscreen,
                            contentDescription = if (mediaFullscreen) "Exit fullscreen" else "Enter fullscreen",
                        )
                    }
                }
            }
        }
        if (
            post.mediaType != "video" &&
            !allowThumbnailFallback &&
            playbackAllowed
        ) {
            Surface(
                modifier = Modifier.align(Alignment.BottomEnd).padding(12.dp),
                shape = RoundedCornerShape(50.dp),
                color = Color(0xCC15151A),
            ) {
                IconButton(onClick = { onFullscreenChanged(!mediaFullscreen) }) {
                    Icon(
                        if (mediaFullscreen) Icons.Default.FullscreenExit else Icons.Default.Fullscreen,
                        contentDescription = if (mediaFullscreen) "Exit fullscreen" else "Enter fullscreen",
                    )
                }
            }
        }
        if (videoBuffering && videoPlaying && playbackAllowed && !allowThumbnailFallback) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center)
                    .size(30.dp),
                color = Color(0xFFD1D5DB),
                strokeWidth = 3.dp,
            )
        }
        videoFeedback?.let { feedback ->
            Surface(
                Modifier.align(Alignment.Center),
                color = Color(0xCC15151A),
                shape = RoundedCornerShape(16.dp),
            ) {
                Text(feedback, Modifier.padding(horizontal = 16.dp, vertical = 10.dp), style = MaterialTheme.typography.labelLarge)
            }
        }
        if (showLoadingIndicator && imageLoading) {
            LoadingSpinner(Modifier.align(Alignment.Center))
        }
        if (canLoadOriginal) {
            Surface(
                modifier = Modifier.align(Alignment.TopEnd).padding(10.dp).clickable {
                    showOriginal = true
                    imageLoading = true
                },
                color = Color(0xCC15151A),
                shape = RoundedCornerShape(8.dp),
            ) {
                Text(
                    "View original",
                    Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
        if (showMetadata) {
            Surface(
                Modifier.align(Alignment.BottomStart).padding(start = 8.dp, top = 8.dp, bottom = 8.dp + metadataControlInset),
                color = Color(0xAA15151A),
                shape = RoundedCornerShape(6.dp),
            ) {
                Text("${post.provider} | ${post.rating.uppercase()}", Modifier.padding(horizontal = 8.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun LoadingSpinner(modifier: Modifier = Modifier) {
    CircularProgressIndicator(
        modifier = modifier.size(30.dp),
        color = Color(0xFFD1D5DB),
        strokeWidth = 3.dp,
    )
}

private fun formatPlaybackTime(milliseconds: Int): String {
    val seconds = milliseconds.coerceAtLeast(0) / 1000
    return "%d:%02d".format(seconds / 60, seconds % 60)
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun SettingsScreen(
    state: UiState,
    model: MainViewModel,
    onChooseFolder: () -> Unit,
    onClose: () -> Unit,
) {
    var selectedPage by rememberSaveable { mutableStateOf("") }
    var customTerm by rememberSaveable { mutableStateOf("") }
    var showCustomTermsDialog by rememberSaveable { mutableStateOf(false) }
    var newBlockedTags by rememberSaveable { mutableStateOf("") }
    var showBlockedTagsDialog by rememberSaveable { mutableStateOf(false) }
    var providerMenu by remember { mutableStateOf(false) }
    var dohMenu by remember { mutableStateOf(false) }
    var ratingMenu by remember { mutableStateOf(false) }
    var mediaMenu by remember { mutableStateOf(false) }
    var videoResolutionMenu by remember { mutableStateOf(false) }
    BackHandler {
        if (selectedPage.isNotEmpty()) selectedPage = "" else onClose()
    }

    val pageTitle = when (selectedPage) {
        "browsing" -> "Browsing"
        "providers" -> "Providers"
        "network" -> "Network"
        "filters" -> "Filters"
        "display" -> "Display"
        "downloads" -> "Downloads"
        "backup" -> "Backup & restore"
        "updates" -> "Updates"
        "about" -> "About"
        else -> "Settings"
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier.fillMaxWidth().statusBarsPadding().height(64.dp).padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(
                    onClick = { if (selectedPage.isNotEmpty()) selectedPage = "" else onClose() },
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = if (selectedPage.isNotEmpty()) "Back to settings" else "Back to gallery",
                    )
                }
                Text(pageTitle, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            }

            Column(
                Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                    .navigationBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                if (selectedPage.isEmpty()) {
                    SettingsCategoryRow("Browsing", "Default provider and search terms", Icons.Default.Search) {
                        selectedPage = "browsing"
                    }
                    SettingsCategoryRow("Providers", "Provider account credentials", Icons.Default.Info) { selectedPage = "providers" }
                    SettingsCategoryRow("Network", "DNS-over-HTTPS settings", Icons.Default.Refresh) { selectedPage = "network" }
                    SettingsCategoryRow("Filters", "Rating and blocked content", Icons.Default.Check) { selectedPage = "filters" }
                    SettingsCategoryRow("Display", "Ambient background and video resolution", Icons.Default.Fullscreen) { selectedPage = "display" }
                    SettingsCategoryRow("Downloads", "Choose where downloaded media is saved", Icons.Default.Download) { selectedPage = "downloads" }
                    SettingsCategoryRow("Backup & restore", "Export or import encrypted user data", Icons.Default.Check) { selectedPage = "backup" }
                    SettingsCategoryRow("Updates", "Check for the latest app version", Icons.Default.Refresh) { selectedPage = "updates" }
                    SettingsCategoryRow("About", "App version, creator, and licenses", Icons.Default.Info) { selectedPage = "about" }
                } else {
                    when (selectedPage) {
                        "browsing" -> {
                            Box {
                                SettingsValueRow("Default provider", state.provider) { providerMenu = true }
                                DropdownMenu(expanded = providerMenu, onDismissRequest = { providerMenu = false }) {
                                    listOf("Auto", "yande.re", "Gelbooru", "Rule34.xxx", "Danbooru").forEach { provider ->
                                        DropdownMenuItem(
                                            text = { Text(provider) },
                                            onClick = { providerMenu = false; model.setProvider(provider) },
                                        )
                                    }
                                }
                            }
                            SettingsValueRow(
                                "Custom search terms",
                                "${state.customTerms.size} saved",
                            ) { showCustomTermsDialog = true }
                            if (showCustomTermsDialog) {
                                AlertDialog(
                                    onDismissRequest = { showCustomTermsDialog = false },
                                    title = { Text("Custom search terms") },
                                    text = {
                                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                OutlinedTextField(
                                                    value = customTerm,
                                                    onValueChange = { customTerm = it },
                                                    modifier = Modifier.weight(1f),
                                                    singleLine = true,
                                                    placeholder = { Text("Add a character or tag") },
                                                )
                                                IconButton(
                                                    onClick = {
                                                        model.addCustomTerm(customTerm)
                                                        customTerm = ""
                                                    },
                                                    enabled = customTerm.isNotBlank(),
                                                ) { Icon(Icons.Default.Add, "Add search term") }
                                            }
                                            Column(
                                                Modifier.heightIn(max = 240.dp).verticalScroll(rememberScrollState()),
                                            ) {
                                                state.customTerms.forEach { term ->
                                                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                                        Text(term, Modifier.weight(1f))
                                                        IconButton(onClick = { model.removeCustomTerm(term) }) {
                                                            Icon(Icons.Default.Delete, "Remove $term")
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    confirmButton = {
                                        TextButton(onClick = { showCustomTermsDialog = false }) { Text("Done") }
                                    },
                                )
                            }
                        }
                        "providers" -> {
                            Text("Provider accounts", fontWeight = FontWeight.SemiBold)
                            ProviderAccountRow(
                                "Gelbooru",
                                model.hasGelbooruCredentials(),
                                model::openGelbooruCredentials,
                                { model.logoutProvider("Gelbooru") },
                            )
                            ProviderAccountRow(
                                "Rule34.xxx",
                                model.hasRule34Credentials(),
                                model::openRule34Credentials,
                                { model.logoutProvider("Rule34.xxx") },
                            )
                        }
                        "network" -> {
                            SettingSwitch(
                                "Use DNS over HTTPS",
                                state.useDoh,
                                "Resolve provider and image hosts through the selected DNS resolver",
                                model::setUseDoh,
                            )
                            Box {
                                SettingsValueRow(
                                    "DNS provider",
                                    state.dohProvider,
                                    enabled = state.useDoh,
                                ) { dohMenu = true }
                                DropdownMenu(expanded = dohMenu, onDismissRequest = { dohMenu = false }) {
                                    listOf("Cloudflare", "Cloudflare Security", "Cloudflare Family", "Google Public DNS", "AdGuard DNS", "Custom").forEach { name ->
                                        DropdownMenuItem(
                                            text = { Text(name) },
                                            onClick = { model.setDohProvider(name); dohMenu = false },
                                        )
                                    }
                                }
                            }
                            if (state.dohProvider == "Custom") {
                                OutlinedTextField(
                                    value = state.customDohEndpoint,
                                    onValueChange = model::setCustomDohEndpoint,
                                    modifier = Modifier.fillMaxWidth(),
                                    singleLine = true,
                                    label = { Text("DNS-over-HTTPS URL") },
                                    placeholder = { Text("https://resolver.example/dns-query") },
                                    enabled = state.useDoh,
                                )
                            }
                        }
                        "filters" -> {
                            Box {
                                SettingsValueRow(
                                    "Media type",
                                    when (state.mediaFilter) {
                                        "image" -> "Images only"
                                        "video" -> "Videos only"
                                        else -> "Images and videos"
                                    },
                                ) { mediaMenu = true }
                                DropdownMenu(expanded = mediaMenu, onDismissRequest = { mediaMenu = false }) {
                                    listOf(
                                        "image" to "Images only",
                                        "video" to "Videos only",
                                        "all" to "Images and videos",
                                    ).forEach { (value, label) ->
                                        DropdownMenuItem(
                                            text = { Text(label) },
                                            onClick = { model.setMediaFilter(value); mediaMenu = false },
                                        )
                                    }
                                }
                            }
                            Box {
                                SettingsValueRow("Default rating", state.rating.label) { ratingMenu = true }
                                DropdownMenu(expanded = ratingMenu, onDismissRequest = { ratingMenu = false }) {
                                    RatingFilter.entries.forEach { option ->
                                        DropdownMenuItem(
                                            text = { Text(option.label) },
                                            trailingIcon = {
                                                if (state.rating == option) Icon(Icons.Default.Check, contentDescription = "Selected")
                                            },
                                            onClick = {
                                                model.setRatingPreference(option)
                                                ratingMenu = false
                                            },
                                        )
                                    }
                                }
                            }
                            SettingSwitch(
                                "Filter gore",
                                state.filterGore,
                                "Hide posts tagged with gore-related terms",
                                model::setFilterGore,
                            )
                            SettingSwitch(
                                "Exclude male-only posts",
                                state.excludeMale,
                                "Hide posts tagged as male-only",
                                model::setExcludeMale,
                            )
                            val blockedTags = state.customBlockTags
                                .replace(",", " ")
                                .split(Regex("\\s+"))
                                .filter(String::isNotBlank)
                                .distinctBy(String::lowercase)
                            SettingsValueRow(
                                "Custom blocked tags",
                                "${blockedTags.size} tags",
                            ) { showBlockedTagsDialog = true }
                            if (showBlockedTagsDialog) {
                                AlertDialog(
                                    onDismissRequest = { showBlockedTagsDialog = false },
                                    title = { Text("Custom blocked tags") },
                                    text = {
                                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                OutlinedTextField(
                                                    value = newBlockedTags,
                                                    onValueChange = { newBlockedTags = it },
                                                    modifier = Modifier.weight(1f),
                                                    singleLine = true,
                                                    placeholder = { Text("Add blocked tags") },
                                                )
                                                IconButton(
                                                    onClick = {
                                                        val existing = blockedTags.map(String::lowercase).toSet()
                                                        val additions = newBlockedTags
                                                            .replace(",", " ")
                                                            .split(Regex("\\s+"))
                                                            .map { it.trim().lowercase().replace(Regex("\\s+"), "_") }
                                                            .filter { it.isNotBlank() && it !in existing }
                                                        if (additions.isNotEmpty()) {
                                                            model.setCustomBlockTags((blockedTags + additions).joinToString(", "))
                                                        }
                                                        newBlockedTags = ""
                                                    },
                                                    enabled = newBlockedTags.isNotBlank(),
                                                ) {
                                                    Icon(Icons.Default.Add, contentDescription = "Add blocked tags")
                                                }
                                            }
                                            Column(
                                                Modifier.heightIn(max = 280.dp).verticalScroll(rememberScrollState()),
                                            ) {
                                                if (blockedTags.isNotEmpty()) {
                                                    FlowRow(
                                                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                                                        verticalArrangement = Arrangement.spacedBy(4.dp),
                                                    ) {
                                                        blockedTags.forEach { tag ->
                                                            Surface(
                                                                shape = RoundedCornerShape(50),
                                                                color = Panel,
                                                            ) {
                                                                Row(
                                                                    Modifier.padding(start = 12.dp),
                                                                    verticalAlignment = Alignment.CenterVertically,
                                                                ) {
                                                                    Text(tag, style = MaterialTheme.typography.labelLarge)
                                                                    IconButton(
                                                                        onClick = {
                                                                            model.setCustomBlockTags(
                                                                                blockedTags.filterNot { it.equals(tag, ignoreCase = true) }
                                                                                    .joinToString(", "),
                                                                            )
                                                                        },
                                                                        modifier = Modifier.size(36.dp),
                                                                    ) {
                                                                        Icon(
                                                                            Icons.Default.Close,
                                                                            contentDescription = "Remove $tag",
                                                                            modifier = Modifier.size(16.dp),
                                                                        )
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                } else {
                                                    Text(
                                                        "No custom blocked tags",
                                                        style = MaterialTheme.typography.bodySmall,
                                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                    )
                                                }
                                            }
                                        }
                                    },
                                    confirmButton = {
                                        TextButton(onClick = { showBlockedTagsDialog = false }) { Text("Done") }
                                    },
                                )
                            }
                        }
                        "display" -> {
                            SettingSwitch(
                                "Ambient background",
                                state.ambientMode,
                                "Use a blurred version of the current media behind it",
                                model::setAmbientMode,
                            )
                            Box {
                                SettingsValueRow(
                                    "Video resolution",
                                    if (state.videoMaxHeight == 0) "Auto" else "Up to ${state.videoMaxHeight}p",
                                ) { videoResolutionMenu = true }
                                DropdownMenu(
                                    expanded = videoResolutionMenu,
                                    onDismissRequest = { videoResolutionMenu = false },
                                ) {
                                    listOf(
                                        0 to "Auto",
                                        2160 to "Up to 2160p",
                                        1080 to "Up to 1080p",
                                        720 to "Up to 720p",
                                        480 to "Up to 480p",
                                    ).forEach { (height, label) ->
                                        DropdownMenuItem(
                                            text = { Text(label) },
                                            onClick = { model.setVideoMaxHeight(height); videoResolutionMenu = false },
                                        )
                                    }
                                }
                            }
                        }
                        "downloads" -> {
                            SettingsValueRow(
                                "Save location",
                                state.saveFolderLabel ?: "Default: Pictures/Waifu Gallery",
                            ) { onChooseFolder() }
                        }
                        "backup" -> UserDataBackupSection(model)
                        "updates" -> {
                            Text(
                                state.releaseUpdateCheckMessage ?: "Check GitHub Releases for the latest version.",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Button(
                                onClick = model::checkForReleaseUpdate,
                                enabled = !state.isCheckingReleaseUpdate,
                            ) {
                                if (state.isCheckingReleaseUpdate) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(18.dp),
                                        strokeWidth = 2.dp,
                                        color = MaterialTheme.colorScheme.onPrimary,
                                    )
                                    Spacer(Modifier.width(8.dp))
                                }
                                Text(if (state.isCheckingReleaseUpdate) "Checking..." else "Check for updates")
                            }
                            if (state.isDownloadingReleaseUpdate) {
                                val progress = state.releaseDownloadProgress
                                Text(
                                    if (progress == null) "Downloading update..."
                                    else "Downloading update... $progress%",
                                )
                                if (progress == null) {
                                    LinearProgressIndicator(
                                        modifier = Modifier.fillMaxWidth(),
                                        color = Accent,
                                    )
                                } else {
                                    LinearProgressIndicator(
                                        progress = { progress / 100f },
                                        modifier = Modifier.fillMaxWidth(),
                                        color = Accent,
                                    )
                                }
                            }
                            state.releaseDownloadError?.let { error ->
                                Text(error, color = MaterialTheme.colorScheme.error)
                            }
                        }
                        "about" -> {
                            val context = LocalContext.current
                            val version = remember {
                                runCatching {
                                    context.packageManager.getPackageInfo(context.packageName, 0).versionName
                                }.getOrNull().orEmpty()
                            }
                            Column(
                                Modifier.fillMaxWidth().padding(vertical = 8.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                Image(
                                    painter = painterResource(R.drawable.waifu_mascot_iro),
                                    contentDescription = "Waifu Gallery mascot",
                                    modifier = Modifier.size(width = 112.dp, height = 168.dp),
                                    contentScale = ContentScale.Fit,
                                )
                                Text("Waifu Gallery", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                                if (version.isNotBlank()) {
                                    Text("Version $version", style = MaterialTheme.typography.bodyMedium)
                                }
                                Text(
                                    "An independent Android media gallery for discovering, viewing, and " +
                                        "downloading images and videos.\nCreated by calestinfisalia",
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                                Text(
                                    "Source code: MIT License.\n" +
                                        "Bundled icons and artwork retain their own licenses and creator rights.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingsCategoryRow(
    title: String,
    description: String,
    icon: ImageVector,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        color = Panel,
    ) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 72.dp).padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(20.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.bodyLarge)
                Text(description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.AutoMirrored.Filled.NavigateNext, contentDescription = null)
        }
    }
}

@Composable
private fun SettingsValueRow(
    title: String,
    summary: String,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(enabled = enabled, onClick = onClick),
        shape = RoundedCornerShape(18.dp),
        color = Panel,
    ) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 68.dp).padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.bodyLarge)
                Text(
                    summary,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (enabled) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.NavigateNext,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun UserDataBackupSection(model: MainViewModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var exportPassphrase by remember { mutableStateOf("") }
    var confirmExportPassphrase by remember { mutableStateOf("") }
    var pendingExportPassphrase by remember { mutableStateOf("") }
    var importPassphrase by remember { mutableStateOf("") }
    var pendingImport by remember { mutableStateOf<UserDataBackup?>(null) }
    var pendingImportUri by remember { mutableStateOf<Uri?>(null) }
    var showExportDialog by remember { mutableStateOf(false) }
    var showImportDialog by remember { mutableStateOf(false) }
    var isBusy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("") }

    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json"),
    ) { uri ->
        if (uri != null && pendingExportPassphrase.isNotEmpty()) {
            val passphrase = pendingExportPassphrase
            pendingExportPassphrase = ""
            scope.launch {
                isBusy = true
                try {
                    val content = withContext(Dispatchers.IO) {
                        UserDataBackupCodec.encrypt(model.createUserDataBackup(), passphrase)
                    }
                    withContext(Dispatchers.IO) {
                        val output = context.contentResolver.openOutputStream(uri, "wt")
                            ?: throw IOException("Could not open the selected backup file.")
                        output.use { it.write(content.toByteArray(Charsets.UTF_8)) }
                    }
                    status = "Encrypted backup exported."
                } catch (error: Exception) {
                    if (error is CancellationException) throw error
                    if (error is IOException || error is GeneralSecurityException ||
                        error is IllegalArgumentException || error is SecurityException
                    ) {
                        status = "Could not export backup: ${error.message ?: "Unknown error"}"
                    } else {
                        throw error
                    }
                } finally {
                    isBusy = false
                }
            }
        } else {
            pendingExportPassphrase = ""
        }
    }

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) {
            pendingImportUri = uri
            showImportDialog = true
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "Encrypted backups include favorites, provider credentials, and portable preferences. " +
                "Download locations stay on this device. The passphrase cannot be recovered.",
            style = MaterialTheme.typography.bodySmall,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = {
                    exportPassphrase = ""
                    confirmExportPassphrase = ""
                    showExportDialog = true
                },
                enabled = !isBusy,
            ) { Text("Export data") }
            OutlinedButton(
                onClick = { importLauncher.launch(arrayOf("application/json", "application/octet-stream", "*/*")) },
                enabled = !isBusy,
            ) { Text("Import data") }
        }
        if (isBusy) CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
        if (status.isNotBlank()) Text(status, style = MaterialTheme.typography.bodySmall)
    }

    if (showExportDialog) {
        AlertDialog(
            onDismissRequest = { showExportDialog = false },
            title = { Text("Encrypt backup") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Choose a passphrase with at least 8 characters. Use the same passphrase when importing.")
                    OutlinedTextField(
                        value = exportPassphrase,
                        onValueChange = { exportPassphrase = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        label = { Text("Passphrase") },
                        visualTransformation = PasswordVisualTransformation(),
                    )
                    OutlinedTextField(
                        value = confirmExportPassphrase,
                        onValueChange = { confirmExportPassphrase = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        label = { Text("Confirm passphrase") },
                        visualTransformation = PasswordVisualTransformation(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (exportPassphrase.codePointCount(0, exportPassphrase.length) < 8) {
                            status = "Use a passphrase with at least 8 characters."
                        } else if (exportPassphrase != confirmExportPassphrase) {
                            status = "The passphrases do not match."
                        } else {
                            pendingExportPassphrase = exportPassphrase
                            showExportDialog = false
                            exportLauncher.launch("waifu-gallery-backup.wgbak")
                        }
                    },
                ) { Text("Choose file") }
            },
            dismissButton = { TextButton(onClick = { showExportDialog = false }) { Text("Cancel") } },
        )
    }

    if (showImportDialog) {
        AlertDialog(
            onDismissRequest = {
                showImportDialog = false
                importPassphrase = ""
                pendingImportUri = null
            },
            title = { Text("Decrypt backup") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Enter the passphrase used when this backup was exported.")
                    OutlinedTextField(
                        value = importPassphrase,
                        onValueChange = { importPassphrase = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        label = { Text("Passphrase") },
                        visualTransformation = PasswordVisualTransformation(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val passphrase = importPassphrase
                        showImportDialog = false
                        importPassphrase = ""
                        isBusy = true
                        scope.launch {
                            try {
                                val data = withContext(Dispatchers.IO) {
                                    val uri = pendingImportUri ?: throw IOException("No backup file was selected.")
                                    val text = context.contentResolver.openInputStream(uri)?.use { input ->
                                        val output = ByteArrayOutputStream()
                                        val buffer = ByteArray(8192)
                                        var total = 0
                                        while (true) {
                                            val count = input.read(buffer)
                                            if (count < 0) break
                                            total += count
                                            if (total > 32 * 1024 * 1024) {
                                                throw IOException("The backup file is too large.")
                                            }
                                            output.write(buffer, 0, count)
                                        }
                                        output.toString(Charsets.UTF_8.name())
                                    } ?: throw IOException("Could not read the selected backup file.")
                                    UserDataBackupCodec.decrypt(text, passphrase)
                                }
                                pendingImport = data
                                pendingImportUri = null
                                status = "Backup decrypted and validated."
                            } catch (error: Exception) {
                                if (error is CancellationException) throw error
                                if (error is IOException || error is GeneralSecurityException ||
                                    error is IllegalArgumentException || error is SecurityException
                                ) {
                                    status = "Could not import backup: ${error.message ?: "Unknown error"}"
                                } else {
                                    throw error
                                }
                            } finally {
                                isBusy = false
                            }
                        }
                    },
                    enabled = importPassphrase.codePointCount(0, importPassphrase.length) >= 8,
                ) { Text("Continue") }
            },
            dismissButton = { TextButton(onClick = { showImportDialog = false }) { Text("Cancel") } },
        )
    }

    pendingImport?.let { data ->
        AlertDialog(
            onDismissRequest = { pendingImport = null },
            title = { Text("Import user data") },
            text = {
                Text(
                    "${data.favorites.size} favorites, " +
                        "${listOf(data.gelbooruUserId, data.rule34UserId).count(String::isNotBlank)} provider accounts, " +
                        "and portable preferences. Merge keeps existing favorites and credentials when present; " +
                        "Replace uses the backup's favorites and credentials. Both options import preferences.",
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        isBusy = true
                        scope.launch {
                            try {
                                withContext(Dispatchers.IO) { model.applyUserDataBackup(data, merge = false) }
                                status = "User data replaced from backup."
                            } catch (error: Exception) {
                                if (error is CancellationException) throw error
                                if (error is IllegalStateException || error is IllegalArgumentException) {
                                    status = "Could not import backup: ${error.message ?: "Unknown error"}"
                                } else {
                                    throw error
                                }
                            } finally {
                                isBusy = false
                                pendingImport = null
                            }
                        }
                    },
                    enabled = !isBusy,
                ) { Text("Replace") }
            },
            dismissButton = {
                Row {
                    TextButton(
                        onClick = {
                            isBusy = true
                            scope.launch {
                                try {
                                    withContext(Dispatchers.IO) { model.applyUserDataBackup(data, merge = true) }
                                    status = "User data merged from backup."
                                } catch (error: Exception) {
                                    if (error is CancellationException) throw error
                                    if (error is IllegalStateException || error is IllegalArgumentException) {
                                        status = "Could not import backup: ${error.message ?: "Unknown error"}"
                                    } else {
                                        throw error
                                    }
                                } finally {
                                    isBusy = false
                                    pendingImport = null
                                }
                            }
                        },
                        enabled = !isBusy,
                    ) { Text("Merge") }
                    TextButton(onClick = { pendingImport = null }, enabled = !isBusy) { Text("Cancel") }
                }
            },
        )
    }
}

@Composable
private fun ProviderAccountRow(name: String, signedIn: Boolean, onSignIn: () -> Unit, onLogout: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(name, Modifier.weight(1f))
        Text(if (signedIn) "Signed in" else "Signed out", style = MaterialTheme.typography.labelMedium)
        TextButton(onClick = if (signedIn) onLogout else onSignIn) { Text(if (signedIn) "Logout" else "Sign in") }
    }
}

@Composable
private fun ProviderCredentialsDialog(
    provider: String,
    initialUserId: String,
    initialApiKey: String,
    onSave: (String, String) -> Unit,
    onDismiss: () -> Unit,
) {
    var userId by remember(initialUserId) { mutableStateOf(initialUserId) }
    var apiKey by remember(initialApiKey) { mutableStateOf(initialApiKey) }
    val uriHandler = LocalUriHandler.current
    val accountUrl = if (provider == "Rule34.xxx") "https://rule34.xxx/index.php?page=account&s=options" else "https://gelbooru.com/index.php?page=account&s=options"
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Sign in to $provider") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Copy your user ID and API key from your account settings. Credentials are stored locally on this device.")
                OutlinedTextField(userId, { userId = it }, modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text("User ID") })
                OutlinedTextField(apiKey, { apiKey = it }, modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text("API key") }, visualTransformation = PasswordVisualTransformation())
                TextButton(onClick = { uriHandler.openUri(accountUrl) }) { Text("Open $provider account settings") }
            }
        },
        confirmButton = { TextButton(onClick = { onSave(userId.trim(), apiKey.trim()) }, enabled = userId.isNotBlank() && apiKey.isNotBlank()) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun GelbooruCredentialsDialog(
    initialUserId: String,
    initialApiKey: String,
    onSave: (String, String) -> Unit,
    onDismiss: () -> Unit,
) {
    var userId by remember(initialUserId) { mutableStateOf(initialUserId) }
    var apiKey by remember(initialApiKey) { mutableStateOf(initialApiKey) }
    val uriHandler = LocalUriHandler.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Gelbooru login") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Enter your Gelbooru user ID and API key. They are stored locally on this device.", style = MaterialTheme.typography.bodyMedium)
                OutlinedTextField(
                    value = userId,
                    onValueChange = { userId = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("User ID") },
                )
                OutlinedTextField(
                    value = apiKey,
                    onValueChange = { apiKey = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("API key") },
                    visualTransformation = PasswordVisualTransformation(),
                )
                TextButton(onClick = { uriHandler.openUri("https://gelbooru.com/index.php?page=account&s=options") }) {
                    Text("Open Gelbooru account settings")
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(userId.trim(), apiKey.trim()) }, enabled = userId.isNotBlank() && apiKey.isNotBlank()) {
                Text("Save and unlock")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun AboutDialog(post: ImagePost, onDismiss: () -> Unit, onTagClick: (String) -> Unit) {
    val uriHandler = LocalUriHandler.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Media info") },
        text = {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 480.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Artist(s): ${post.artists.joinToString().ifBlank { "Not provided by the source" }}")
                Text("Provider: ${post.provider}")
                Text("Rating: ${post.rating.uppercase().ifBlank { "Unknown" }}")
                Text("Post ID: ${post.id.substringAfter('_')}")
                Text("Source", fontWeight = FontWeight.SemiBold)
                if (post.source.startsWith("https://") || post.source.startsWith("http://")) {
                    Text(post.source, color = MaterialTheme.colorScheme.primary, modifier = Modifier.clickable { uriHandler.openUri(post.source) })
                } else {
                    Text(post.source.ifBlank { "No source link provided" })
                }
                Text("Tags", fontWeight = FontWeight.SemiBold)
                if (post.tags.isEmpty()) {
                    Text("No tags provided", style = MaterialTheme.typography.bodySmall)
                } else {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        post.tags.sorted().forEach { tag ->
                            AssistChip(
                                onClick = { onTagClick(tag) },
                                label = {
                                    Text(
                                        tag,
                                        style = MaterialTheme.typography.bodySmall,
                                        maxLines = 1,
                                        softWrap = false,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                },
                                modifier = Modifier.widthIn(max = 280.dp),
                            )
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun DownloadQueueScreen(
    downloads: List<DownloadItem>,
    onOpen: (String) -> Unit,
    onRetry: (String) -> Unit,
    onClearFinished: () -> Unit,
    onDismiss: () -> Unit,
) {
    val hasFinished = downloads.any { it.status == DownloadStatus.SAVED || it.status == DownloadStatus.FAILED }
    BackHandler(onBack = onDismiss)
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier.fillMaxWidth().statusBarsPadding().height(64.dp).padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onDismiss) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to gallery")
                }
                Column(Modifier.weight(1f)) {
                    Text("Downloads", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                    Text(
                        "Downloads run one at a time",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                TextButton(onClick = onClearFinished, enabled = hasFinished) {
                    Text("Clear history")
                }
            }
            if (downloads.isEmpty()) {
                Box(
                    Modifier.weight(1f).fillMaxWidth().navigationBarsPadding(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("No downloads yet")
                }
            } else {
                Column(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                        .navigationBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    downloads.forEach { item ->
                        Card(
                            modifier = Modifier.fillMaxWidth().clickable(enabled = item.status == DownloadStatus.SAVED) {
                                onOpen(item.id)
                            },
                            colors = CardDefaults.cardColors(containerColor = Panel),
                        ) {
                            Column(
                                Modifier.fillMaxWidth().padding(14.dp),
                                verticalArrangement = Arrangement.spacedBy(5.dp),
                            ) {
                                Text(
                                    "waifu_${item.post.id.substringAfter('_')}.${item.post.extension.ifBlank { "jpg" }}",
                                    fontWeight = FontWeight.SemiBold,
                                    maxLines = 1,
                                )
                                Text(
                                    "${item.post.provider} - ${item.post.artists.joinToString().ifBlank { "Artist info unavailable" }}",
                                    style = MaterialTheme.typography.bodySmall,
                                    maxLines = 1,
                                )
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        when (item.status) {
                                            DownloadStatus.QUEUED -> "Queued"
                                            DownloadStatus.DOWNLOADING ->
                                                if (item.progress != null) "Downloading ${(item.progress * 100).toInt()}%" else "Downloading"
                                            DownloadStatus.SAVED -> "Completed"
                                            DownloadStatus.FAILED -> "Failed: ${item.error ?: "Unknown error"}"
                                        },
                                        Modifier.weight(1f),
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                    if (item.status == DownloadStatus.FAILED) {
                                        TextButton(onClick = { onRetry(item.id) }) { Text("Retry") }
                                    }
                                }
                                if (item.status == DownloadStatus.DOWNLOADING) {
                                    if (item.progress == null) {
                                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Accent)
                                    } else {
                                        LinearProgressIndicator(
                                            progress = { item.progress },
                                            modifier = Modifier.fillMaxWidth(),
                                            color = Accent,
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingSwitch(title: String, checked: Boolean, description: String, onChecked: (Boolean) -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable { onChecked(!checked) },
        shape = RoundedCornerShape(18.dp),
        color = Panel,
    ) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 68.dp).padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f).padding(end = 12.dp)) {
                Text(title, style = MaterialTheme.typography.bodyLarge)
                Text(description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(checked = checked, onCheckedChange = onChecked)
        }
    }
}
