package com.fisalia.waifugallery

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
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
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.ImageLoader
import coil.compose.AsyncImage
import coil.disk.DiskCache
import coil.request.ImageRequest
import kotlinx.coroutines.launch
import com.fisalia.waifugallery.data.BooruApi
import com.fisalia.waifugallery.data.ImagePost
import com.fisalia.waifugallery.data.RatingFilter

private val AppBackground = Color(0xFF17171C)
private val Panel = Color(0xFF24242B)
private val Accent = Color(0xFF8057E8)

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
    var aboutPost by remember { mutableStateOf<ImagePost?>(null) }
    var showAppAbout by remember { mutableStateOf(false) }
    var confirmFavoriteRemoval by remember { mutableStateOf<ImagePost?>(null) }
    BackHandler(state.screen == AppScreen.DETAIL || state.screen == AppScreen.FAVORITES) {
        if (state.screen == AppScreen.DETAIL) model.backToGallery() else model.goHome()
    }
    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri: Uri? ->
        uri?.let(model::rememberSaveFolder)
    }
    val imageLoader = remember(state.useDoh) {
        val api = BooruApi(
            useDoh = { state.useDoh },
            gelbooruCredentials = { model.preferences.gelbooruUserId to model.preferences.gelbooruApiKey },
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
            Scaffold(containerColor = AppBackground, topBar = {
                HeaderBar(
                    isDetail = state.screen == AppScreen.DETAIL,
                    showHome = state.screen == AppScreen.FAVORITES || (state.screen == AppScreen.DETAIL && state.detailOrigin != AppScreen.RANDOM),
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
                    onPreferences = model::openPreferences,
                    onDownloads = model::openDownloadQueue,
                    onFavorites = model::openFavorites,
                    onAbout = { aboutPost = if (state.screen == AppScreen.DETAIL) state.detailImage else state.image },
                    onAppAbout = { showAppAbout = true },
                    canSave = when (state.screen) {
                        AppScreen.RANDOM -> state.image != null && !state.isLoading
                        AppScreen.DETAIL -> state.detailImage != null && !state.isLoading
                        AppScreen.GALLERY, AppScreen.FAVORITES -> false
                    },
                )
            }) { padding ->
                when (state.screen) {
                    AppScreen.RANDOM -> RandomScreen(state, imageLoader, Modifier.padding(padding))
                    AppScreen.GALLERY -> GalleryScreen(state, imageLoader, model, Modifier.padding(padding))
                    AppScreen.FAVORITES -> FavoritesScreen(state, imageLoader, model, Modifier.padding(padding), onRequestRemoval = { confirmFavoriteRemoval = it })
                    AppScreen.DETAIL -> DetailScreen(
                        state,
                        imageLoader,
                        onPageSelected = model::selectDetail,
                        onLoadAdjacentPage = model::loadAdjacentDetailPage,
                        modifier = Modifier.padding(padding),
                    )
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
    state.showPreferences.let { visible ->
        if (visible) PreferencesDialog(
            state = state,
            model = model,
            onChooseFolder = { folderPicker.launch(null) },
            onClose = model::closePreferences,
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
    aboutPost?.let { post -> AboutDialog(post = post, onDismiss = { aboutPost = null }) }
    if (showAppAbout) AppAboutDialog(onDismiss = { showAppAbout = false })
    if (state.showDownloadQueue) {
        DownloadQueueDialog(
            downloads = state.downloads,
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
            Surface(shape = RoundedCornerShape(24.dp), color = Color(0xFF35323E)) {
                Text(message, Modifier.padding(horizontal = 20.dp, vertical = 12.dp))
            }
        }
    }
    }
}

@Composable
private fun HeaderBar(
    isDetail: Boolean,
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
    onPreferences: () -> Unit,
    onDownloads: () -> Unit,
    onFavorites: () -> Unit,
    onAbout: () -> Unit,
    onAppAbout: () -> Unit,
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
                OutlinedTextField(
                    value = query,
                    onValueChange = onQueryChanged,
                    modifier = Modifier.weight(1f).height(54.dp),
                    singleLine = true,
                    placeholder = { Text("Search name or tags", maxLines = 1) },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    trailingIcon = {
                        if (query.isNotEmpty()) IconButton(onClick = { onQueryChanged("") }) {
                            Icon(Icons.Default.Close, contentDescription = "Clear search")
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
            if (canSave && !searchVisible) IconButton(onClick = onAbout) { Icon(Icons.Default.Info, "Image credits and information") }
            if (canSave && !searchVisible) IconButton(onClick = onFavorite) {
                Icon(if (isFavorite) Icons.Default.Favorite else Icons.Default.FavoriteBorder, if (isFavorite) "Remove favorite" else "Add favorite", tint = if (isFavorite) Accent else MaterialTheme.colorScheme.onSurface)
            }
            Box {
                IconButton(onClick = { settingsMenuExpanded = true }) { Icon(Icons.Default.Settings, "Settings menu") }
                DropdownMenu(expanded = settingsMenuExpanded, onDismissRequest = { settingsMenuExpanded = false }) {
                    DropdownMenuItem(
                        text = { Text("Preferences") },
                        onClick = { settingsMenuExpanded = false; onPreferences() },
                    )
                    DropdownMenuItem(
                        text = { Text("Downloads") },
                        onClick = { settingsMenuExpanded = false; onDownloads() },
                    )
                    DropdownMenuItem(
                        text = { Text("Favorites") },
                        onClick = { settingsMenuExpanded = false; onFavorites() },
                    )
                    DropdownMenuItem(
                        text = { Text("About") },
                        onClick = { settingsMenuExpanded = false; onAppAbout() },
                    )
                }
            }
        }
    }
}

@Composable
private fun AppAboutDialog(onDismiss: () -> Unit) {
    val context = LocalContext.current
    val version = remember {
        runCatching {
            context.packageManager.getPackageInfo(context.packageName, 0).versionName
        }.getOrNull().orEmpty()
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("About") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Waifu Gallery", fontWeight = FontWeight.SemiBold)
                if (version.isNotBlank()) Text("Version $version")
                Text("Android edition by Fisalia Cantarella.")
                Text("Inspired by NyarchLinux/WaifuDownloader.")
                Text("MIT License · provided without warranty.")
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun RandomScreen(state: UiState, imageLoader: ImageLoader, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        state.image?.let { post -> ImageFrame(post.imageUrl, post, imageLoader, Modifier.fillMaxSize(), zoomEnabled = true, showLoadingIndicator = true) }
        if (state.image == null && !state.isLoading) Text("No image loaded")
        if (state.isLoading) LinearProgressIndicator(
            modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(3.dp),
            color = Accent,
        )
    }
}

@Composable
private fun GalleryScreen(state: UiState, imageLoader: ImageLoader, model: MainViewModel, modifier: Modifier = Modifier) {
    var showFilters by remember { mutableStateOf(false) }
    val gridState = rememberLazyGridState()
    LaunchedEffect(state.page, state.galleryQuery, state.galleryProvider, state.rating) {
        gridState.scrollToItem(0)
    }
    Column(modifier.fillMaxSize().padding(horizontal = 10.dp)) {
        Row(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Results for \"${state.galleryQuery}\"", Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, maxLines = 1)
            OutlinedButton(onClick = { showFilters = true }, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)) {
                Icon(Icons.Default.Tune, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Filter")
            }
        }
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
                            ImageFrame(post.thumbnailUrl, post, imageLoader, Modifier.fillMaxSize(), allowThumbnailFallback = true)
                        }
                    }
                }
            }
            if (state.isLoading) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Loading images…", color = Color.LightGray)
                LinearProgressIndicator(
                    modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(3.dp),
                    color = Accent,
                )
            }
            if (!state.isLoading && state.gallery.isEmpty()) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No images found")
            }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { model.changePage(-1) }, enabled = state.page > 1) {
                Icon(Icons.Default.NavigateBefore, contentDescription = null); Text("Previous")
            }
            val pageCount = state.totalPages?.toString() ?: if (state.hasMore) "…" else state.page.toString()
            Text("${state.page}/$pageCount  |  ${state.gallery.size} images", Modifier.padding(horizontal = 8.dp), style = MaterialTheme.typography.labelMedium)
            TextButton(onClick = { model.changePage(1) }, enabled = state.hasMore) {
                Text("Next"); Icon(Icons.Default.NavigateNext, contentDescription = null)
            }
        }
    }
    if (showFilters) {
        GalleryFiltersDialog(
            selectedProvider = state.galleryProvider,
            selectedRating = state.rating,
            onDismiss = { showFilters = false },
            onApply = { provider, rating ->
                showFilters = false
                model.setGalleryFilters(provider, rating)
            },
        )
    }
}

@Composable
private fun GalleryFiltersDialog(
    selectedProvider: String,
    selectedRating: RatingFilter,
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
                        listOf("All", "Danbooru", "yande.re", "Gelbooru").forEach { option ->
                            DropdownMenuItem(
                                text = { Text(option) },
                                trailingIcon = { if (provider == option) Icon(Icons.Default.Check, contentDescription = "Selected") },
                                onClick = { provider = option; providerMenu = false },
                            )
                        }
                    }
                }

                Text("Rating", fontWeight = FontWeight.SemiBold)
                Box {
                    OutlinedButton(onClick = { ratingMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Text(rating.label, Modifier.weight(1f))
                        Icon(Icons.Default.ArrowDropDown, contentDescription = "Choose rating")
                    }
                    DropdownMenu(expanded = ratingMenu, onDismissRequest = { ratingMenu = false }) {
                        RatingFilter.entries.forEach { option ->
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
) {
    Column(modifier.fillMaxSize().padding(horizontal = 10.dp)) {
        Text("Favorites · ${state.favorites.size} images", Modifier.padding(vertical = 10.dp), style = MaterialTheme.typography.titleSmall)
        if (state.favorites.isEmpty()) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text("No favorites yet")
            }
        } else {
            LazyVerticalGrid(
                columns = GridCells.Adaptive(minSize = 145.dp),
                contentPadding = PaddingValues(bottom = 10.dp),
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

@Composable
private fun DetailScreen(
    state: UiState,
    imageLoader: ImageLoader,
    onPageSelected: (Int) -> Unit,
    onLoadAdjacentPage: (Int) -> Unit,
    modifier: Modifier = Modifier,
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

    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        if (posts.isNotEmpty()) {
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.fillMaxSize(),
                beyondViewportPageCount = 1,
                key = { page -> posts[page].id },
            ) { page ->
                val post = posts[page]
                ImageFrame(post.imageUrl, post, imageLoader, Modifier.fillMaxSize(), zoomEnabled = true, showLoadingIndicator = true, showMetadata = false)
            }
        } else {
            state.detailImage?.let { post -> ImageFrame(post.imageUrl, post, imageLoader, Modifier.fillMaxSize(), zoomEnabled = true) }
        }
        if (posts.isNotEmpty()) {
            val absoluteIndex = (state.detailFirstPage - 1) * 50 + pagerState.currentPage + 1
            val total = state.totalResults ?: state.totalPages?.times(50)
            Surface(
                Modifier.align(Alignment.BottomCenter).padding(bottom = 10.dp),
                color = Color(0xAA15151A),
                shape = RoundedCornerShape(16.dp),
            ) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
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
                    Text("$absoluteIndex/${total ?: "…"}", style = MaterialTheme.typography.labelMedium)
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
private fun ImageFrame(
    url: String,
    post: ImagePost,
    imageLoader: ImageLoader,
    modifier: Modifier = Modifier,
    allowThumbnailFallback: Boolean = false,
    zoomEnabled: Boolean = false,
    showLoadingIndicator: Boolean = false,
    showMetadata: Boolean = true,
) {
    var candidateIndex by remember(post.id, url) { mutableStateOf(0) }
    val candidates = (if (allowThumbnailFallback) post.thumbnailCandidates else emptyList()).ifEmpty { listOf(url) }
    val displayedUrl = candidates[candidateIndex.coerceAtMost(candidates.lastIndex)]
    var imageLoading by remember(post.id, url) { mutableStateOf(true) }
    var zoom by remember(post.id) { mutableFloatStateOf(1f) }
    var pan by remember(post.id) { mutableStateOf(Offset.Zero) }
    val transformState = rememberTransformableState { zoomChange, panChange, _ ->
        zoom = (zoom * zoomChange).coerceIn(1f, 6f)
        pan = if (zoom <= 1f) Offset.Zero else pan + panChange
    }
    val zoomGesture = if (zoomEnabled) Modifier.transformable(
        state = transformState,
        canPan = { zoom > 1f },
    ) else Modifier
    Box(modifier.background(Color.Transparent).then(zoomGesture), contentAlignment = Alignment.Center) {
        AsyncImage(
            model = ImageRequest.Builder(LocalContext.current).data(displayedUrl).crossfade(true).build(),
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
        if (showLoadingIndicator && imageLoading) {
            LinearProgressIndicator(
                color = Accent,
                modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(3.dp),
            )
        }
        if (zoomEnabled && zoom > 1f) {
            TextButton(onClick = { zoom = 1f; pan = Offset.Zero }, modifier = Modifier.align(Alignment.TopEnd).padding(6.dp)) {
                Text("Reset zoom")
            }
        }
        if (showMetadata) {
            Surface(
                Modifier.align(Alignment.BottomStart).padding(8.dp),
                color = Color(0xAA15151A),
                shape = RoundedCornerShape(6.dp),
            ) {
                Text("${post.provider} | ${post.rating.uppercase()}", Modifier.padding(horizontal = 8.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun PreferencesDialog(
    state: UiState,
    model: MainViewModel,
    onChooseFolder: () -> Unit,
    onClose: () -> Unit,
) {
    var customTerm by remember { mutableStateOf("") }
    var providerMenu by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text("Preferences") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 520.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Images", fontWeight = FontWeight.SemiBold)
                SettingSwitch("Allow NSFW images", state.allowNsfw, "Include questionable and explicit ratings", model::setAllowNsfw)

                Text("Provider", fontWeight = FontWeight.SemiBold)
                Box {
                    OutlinedButton(onClick = { providerMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Text(state.provider)
                        Spacer(Modifier.width(6.dp))
                        Icon(Icons.Default.ArrowDropDown, contentDescription = "Choose provider")
                    }
                    DropdownMenu(expanded = providerMenu, onDismissRequest = { providerMenu = false }) {
                        listOf("Auto", "yande.re", "Gelbooru", "Danbooru").forEach { provider ->
                            DropdownMenuItem(text = { Text(provider) }, onClick = {
                                providerMenu = false
                                model.setProvider(provider)
                            })
                        }
                    }
                }

                Text("Network", fontWeight = FontWeight.SemiBold)
                SettingSwitch("Use DNS over HTTPS", state.useDoh, "Resolve provider and image hosts through Cloudflare DNS", model::setUseDoh)

                Text("Save location", fontWeight = FontWeight.SemiBold)
                Text("${state.saveFolderLabel ?: "Default: Pictures/Waifu Gallery"}", style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = onChooseFolder, modifier = Modifier.fillMaxWidth()) { Text("Choose save folder") }

                Text("Custom search terms", fontWeight = FontWeight.SemiBold)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = customTerm,
                        onValueChange = { customTerm = it },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        placeholder = { Text("Add a character or tag") },
                    )
                    IconButton(onClick = { model.addCustomTerm(customTerm); customTerm = "" }, enabled = customTerm.isNotBlank()) {
                        Icon(Icons.Default.Add, "Add search term")
                    }
                }
                state.customTerms.forEach { term ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(term, Modifier.weight(1f))
                        IconButton(onClick = { model.removeCustomTerm(term) }) { Icon(Icons.Default.Delete, "Remove $term") }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onClose) { Text("Close") } },
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
private fun AboutDialog(post: ImagePost, onDismiss: () -> Unit) {
    val uriHandler = LocalUriHandler.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("About this image") },
        text = {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 480.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Credits", fontWeight = FontWeight.SemiBold)
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
                Text(post.tags.sorted().joinToString().ifBlank { "No tags provided" }, style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun DownloadQueueDialog(
    downloads: List<DownloadItem>,
    onRetry: (String) -> Unit,
    onClearFinished: () -> Unit,
    onDismiss: () -> Unit,
) {
    val activeCount = downloads.count { it.status == DownloadStatus.QUEUED || it.status == DownloadStatus.DOWNLOADING }
    val hasFinished = downloads.any { it.status == DownloadStatus.SAVED || it.status == DownloadStatus.FAILED }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Downloads") },
        text = {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 480.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("$activeCount active · downloads run one at a time")
                if (downloads.isEmpty()) Text("No downloads yet")
                downloads.forEach { item ->
                    Column(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("waifu_${item.post.id.substringAfter('_')}.${item.post.extension.ifBlank { "jpg" }}", fontWeight = FontWeight.SemiBold, maxLines = 1)
                        Text("${item.post.provider} · ${item.post.artists.joinToString().ifBlank { "Artist credit unavailable" }}", style = MaterialTheme.typography.bodySmall, maxLines = 1)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                when (item.status) {
                                    DownloadStatus.QUEUED -> "Queued"
                                    DownloadStatus.DOWNLOADING -> if (item.progress != null) "Downloading ${(item.progress * 100).toInt()}%" else "Downloading"
                                    DownloadStatus.SAVED -> "Completed"
                                    DownloadStatus.FAILED -> "Failed: ${item.error ?: "Unknown error"}"
                                },
                                Modifier.weight(1f),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            if (item.status == DownloadStatus.FAILED) TextButton(onClick = { onRetry(item.id) }) { Text("Retry") }
                        }
                        if (item.status == DownloadStatus.DOWNLOADING) {
                            if (item.progress == null) {
                                LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Accent)
                            } else {
                                LinearProgressIndicator(progress = { item.progress }, modifier = Modifier.fillMaxWidth(), color = Accent)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
        dismissButton = {
            TextButton(onClick = onClearFinished, enabled = hasFinished) { Text("Clear history") }
        },
    )
}

@Composable
private fun SettingSwitch(title: String, checked: Boolean, description: String, onChecked: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title)
            Text(description, style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
        }
        Switch(checked = checked, onCheckedChange = onChecked)
    }
}
