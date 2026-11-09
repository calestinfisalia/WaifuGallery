package com.fisalia.waifugallery

import android.app.Application
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.fisalia.waifugallery.data.AppPreferences
import com.fisalia.waifugallery.data.BooruApi
import com.fisalia.waifugallery.data.ImagePost
import com.fisalia.waifugallery.data.RatingFilter
import com.fisalia.waifugallery.data.ReleaseUpdate
import com.fisalia.waifugallery.data.ReleaseUpdateChecker
import com.fisalia.waifugallery.data.SearchPage
import com.fisalia.waifugallery.data.UserDataBackup
import com.fisalia.waifugallery.data.UserDataBackupCodec
import java.io.IOException
import java.io.File
import java.io.FileOutputStream
import okhttp3.Request
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class AppScreen { RANDOM, GALLERY, FAVORITES, DETAIL }
enum class DownloadStatus { QUEUED, DOWNLOADING, SAVED, FAILED }

data class DownloadItem(
    val id: String,
    val post: ImagePost,
    val status: DownloadStatus,
    val error: String? = null,
    val progress: Float? = null,
)

data class UiState(
    val screen: AppScreen = AppScreen.RANDOM,
    val image: ImagePost? = null,
    val detailImage: ImagePost? = null,
    val detailOrigin: AppScreen = AppScreen.RANDOM,
    val queryInput: String = "",
    val galleryQuery: String = "",
    val gallery: List<ImagePost> = emptyList(),
    val favorites: List<ImagePost> = emptyList(),
    val totalResults: Int? = null,
    val detailPosts: List<ImagePost> = emptyList(),
    val detailFirstPage: Int = 1,
    val detailLastPage: Int = 1,
    val detailHasMore: Boolean = false,
    val detailLoadingPrevious: Boolean = false,
    val detailLoadingNext: Boolean = false,
    val detailPreviousFailed: Boolean = false,
    val detailNextFailed: Boolean = false,
    val galleryProvider: String = "All",
    val rating: RatingFilter = RatingFilter.SFW,
    val page: Int = 1,
    val totalPages: Int? = null,
    val hasMore: Boolean = false,
    val isLoading: Boolean = true,
    val searchVisible: Boolean = false,
    val showPreferences: Boolean = false,
    val requestGelbooruCredentials: Boolean = false,
    val requestRule34Credentials: Boolean = false,
    val showDownloadQueue: Boolean = false,
    val downloads: List<DownloadItem> = emptyList(),
    val error: String? = null,
    val notice: String? = null,
    val allowNsfw: Boolean = false,
    val useDoh: Boolean = false,
    val dohProvider: String = "Cloudflare",
    val customDohEndpoint: String = "",
    val filterGore: Boolean = true,
    val excludeMale: Boolean = true,
    val customBlockTags: String = "",
    val mediaFilter: String = "image",
    val videoMaxHeight: Int = 0,
    val ambientMode: Boolean = true,
    val provider: String = "Auto",
    val customTerms: List<String> = emptyList(),
    val saveFolderLabel: String? = null,
    val releaseUpdate: ReleaseUpdate? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    val preferences = AppPreferences(application)
    private val api = BooruApi(
        useDoh = { preferences.useDoh },
        gelbooruCredentials = { preferences.gelbooruUserId to preferences.gelbooruApiKey },
        rule34Credentials = { preferences.rule34UserId to preferences.rule34ApiKey },
        dohProvider = { preferences.dohProvider },
        customDohEndpoint = { preferences.customDohEndpoint },
        filterGore = { preferences.filterGore },
        excludeMale = { preferences.excludeMale },
        customBlockTags = { preferences.customBlockTags },
        mediaFilter = { preferences.mediaFilter },
    )
    private val _state = MutableStateFlow(
        UiState(
            allowNsfw = preferences.allowNsfw,
            rating = if (preferences.allowNsfw) {
                when (preferences.ratingFilter) {
                    "nsfw" -> RatingFilter.NSFW
                    "all" -> RatingFilter.ALL
                    else -> RatingFilter.SFW
                }
            } else RatingFilter.SFW,
            useDoh = preferences.useDoh,
            dohProvider = preferences.dohProvider,
            customDohEndpoint = preferences.customDohEndpoint,
            filterGore = preferences.filterGore,
            excludeMale = preferences.excludeMale,
            customBlockTags = preferences.customBlockTags,
            mediaFilter = preferences.mediaFilter,
            videoMaxHeight = preferences.videoMaxHeight,
            ambientMode = preferences.ambientMode,
            provider = preferences.selectedProvider,
            favorites = preferences.backupFavoritePosts(),
            customTerms = preferences.customSearchTerms(),
            saveFolderLabel = preferences.saveFolderUri?.let { runCatching { DocumentFile.fromTreeUri(application, Uri.parse(it))?.name }.getOrNull() },
        ),
    )
    val state: StateFlow<UiState> = _state.asStateFlow()
    private var downloadJob: Job? = null
    private var pendingGalleryFilters: Pair<String, RatingFilter>? = null

    init {
        refreshRandom()
        viewModelScope.launch {
            ReleaseUpdateChecker.checkForUpdate(getApplication())?.let { update ->
                _state.update { it.copy(releaseUpdate = update) }
            }
        }
    }

    fun dismissReleaseUpdate() = _state.update { it.copy(releaseUpdate = null) }
    fun updateQuery(value: String) = _state.update { it.copy(queryInput = value) }
    fun toggleSearch() {
        _state.update { it.copy(searchVisible = !it.searchVisible, queryInput = if (it.searchVisible) "" else it.queryInput) }
        if (!_state.value.searchVisible && _state.value.screen == AppScreen.GALLERY) refreshRandom()
    }
    fun openPreferences() = _state.update { it.copy(showPreferences = true) }
    fun closePreferences() = _state.update { it.copy(showPreferences = false) }
    fun openGelbooruCredentials() = _state.update { it.copy(requestGelbooruCredentials = true) }
    fun openRule34Credentials() = _state.update { it.copy(requestRule34Credentials = true) }
    fun cancelGelbooruCredentials() {
        pendingGalleryFilters = null
        _state.update { it.copy(requestGelbooruCredentials = false) }
    }
    fun cancelRule34Credentials() {
        pendingGalleryFilters = null
        _state.update { it.copy(requestRule34Credentials = false) }
    }
    fun openFavorites() = _state.update { it.copy(screen = AppScreen.FAVORITES, searchVisible = false) }
    fun openDownloadQueue() = _state.update { it.copy(showPreferences = false, showDownloadQueue = true) }
    fun closeDownloadQueue() = _state.update { it.copy(showDownloadQueue = false) }
    fun dismissError() = _state.update { it.copy(error = null) }
    fun dismissNotice() = _state.update { it.copy(notice = null) }

    fun search() {
        val query = _state.value.queryInput.trim()
        if (query.isBlank()) { refreshRandom(); return }
        val selectedProvider = preferences.selectedProvider
        val galleryProvider = if (selectedProvider == "Auto") "All" else selectedProvider
        _state.update { it.copy(galleryQuery = query, galleryProvider = galleryProvider, page = 1, totalPages = null, totalResults = null, hasMore = false, screen = AppScreen.GALLERY, detailPosts = emptyList()) }
        loadGallery()
    }

    fun refresh() {
        if (_state.value.screen == AppScreen.GALLERY) loadGallery()
        else refreshRandom()
    }

    fun refreshRandom() {
        val input = _state.value.queryInput.trim()
        val term = if (input.isNotEmpty()) input else {
            val terms = preferences.customSearchTerms()
            if (terms.isEmpty()) "" else {
                val index = preferences.customSearchIndex.mod(terms.size)
                preferences.customSearchIndex = (index + 1) % terms.size
                terms[index]
            }
        }
        _state.update { it.copy(screen = AppScreen.RANDOM, detailImage = null, image = null, isLoading = true, error = null, notice = null) }
        viewModelScope.launch {
            try {
                val image = api.randomImage(preferences.allowNsfw, term, preferences.selectedProvider)
                _state.update { it.copy(image = image, isLoading = false) }
            } catch (error: Exception) {
                _state.update { it.copy(isLoading = false, error = "Failed to load image:\n${error.message ?: "Unknown error"}") }
            }
        }
    }

    fun setGalleryProvider(provider: String) {
        if (provider == _state.value.galleryProvider) return
        _state.update { it.copy(galleryProvider = provider, page = 1, totalPages = null, hasMore = false) }
        loadGallery()
    }

    fun setGalleryFilters(provider: String, rating: RatingFilter) {
        if (!preferences.allowNsfw && rating != RatingFilter.SFW) {
            _state.update { it.copy(notice = "Enable NSFW results in Preferences to use this rating.") }
            return
        }
        if (provider == "Gelbooru" && !hasGelbooruCredentials()) {
            pendingGalleryFilters = provider to rating
            openGelbooruCredentials()
            return
        }
        if (provider == "Rule34.xxx" && !hasRule34Credentials()) {
            pendingGalleryFilters = provider to rating
            openRule34Credentials()
            return
        }
        if (provider == _state.value.galleryProvider && rating == _state.value.rating) return
        preferences.ratingFilter = rating.name.lowercase()
        _state.update { it.copy(galleryProvider = provider, rating = rating, page = 1, totalPages = null, hasMore = false) }
        loadGallery()
    }

    fun setRating(rating: RatingFilter) {
        if (!preferences.allowNsfw && rating != RatingFilter.SFW) {
            _state.update { it.copy(notice = "Enable NSFW results in Preferences to use this rating.") }
            return
        }
        if (rating == _state.value.rating) return
        preferences.ratingFilter = rating.name.lowercase()
        _state.update { it.copy(rating = rating, page = 1, totalPages = null, hasMore = false) }
        if (_state.value.galleryQuery.isNotBlank()) loadGallery()
    }

    fun changePage(delta: Int) {
        val page = _state.value.page + delta
        val state = _state.value
        if (page < 1 || (delta > 0 && (!state.hasMore || (state.totalPages != null && page > state.totalPages)))) return
        _state.update { it.copy(page = page) }
        loadGallery()
    }

    private fun loadGallery() {
        val snapshot = _state.value
        if (snapshot.galleryQuery.isBlank()) return
        _state.update { it.copy(screen = AppScreen.GALLERY, gallery = emptyList(), totalResults = null, isLoading = true, error = null) }
        viewModelScope.launch {
            try {
                val result: SearchPage = api.search(snapshot.galleryQuery, snapshot.rating, snapshot.galleryProvider, snapshot.page)
                _state.update { it.copy(gallery = result.posts, hasMore = result.hasMore, totalPages = result.totalPages, totalResults = result.totalResults, isLoading = false) }
                if (result.posts.isEmpty() && result.providerErrors.isNotEmpty()) {
                    _state.update { it.copy(error = "Search providers failed:\n${result.providerErrors.joinToString("\n")}") }
                }
            } catch (error: Exception) {
                _state.update { it.copy(isLoading = false, error = "Failed to search images:\n${error.message ?: "Unknown error"}") }
            }
        }
    }

    fun openDetail(post: ImagePost) = _state.update { current ->
        val origin = current.screen
        val detailPosts = when (origin) {
            AppScreen.GALLERY -> current.gallery
            AppScreen.FAVORITES -> current.favorites
            else -> emptyList()
        }
        current.copy(
            screen = AppScreen.DETAIL,
            detailOrigin = origin,
            detailImage = post,
            detailPosts = detailPosts,
            detailFirstPage = if (origin == AppScreen.GALLERY) current.page else 1,
            detailLastPage = if (origin == AppScreen.GALLERY) current.page else 1,
            detailHasMore = origin == AppScreen.GALLERY && current.hasMore,
            totalResults = if (origin == AppScreen.FAVORITES) current.favorites.size else current.totalResults,
            detailLoadingPrevious = false,
            detailLoadingNext = false,
            detailPreviousFailed = false,
            detailNextFailed = false,
        )
    }
    fun selectDetail(index: Int) {
        _state.update { state ->
            val post = state.detailPosts.getOrNull(index) ?: return@update state
            state.copy(detailImage = post)
        }
    }
    fun loadAdjacentDetailPage(direction: Int) {
        val snapshot = _state.value
        if (snapshot.screen != AppScreen.DETAIL || snapshot.detailOrigin != AppScreen.GALLERY || direction !in setOf(-1, 1)) return
        val previous = direction < 0
        if (previous) {
            if (snapshot.detailFirstPage <= 1 || snapshot.detailLoadingPrevious || snapshot.detailPreviousFailed) return
        } else {
            if (snapshot.detailLoadingNext || snapshot.detailNextFailed) return
            if (snapshot.totalPages != null && snapshot.detailLastPage >= snapshot.totalPages) return
            if (snapshot.totalPages == null && !snapshot.detailHasMore) return
        }
        val requestedPage = if (previous) snapshot.detailFirstPage - 1 else snapshot.detailLastPage + 1
        _state.update {
            if (previous) it.copy(detailLoadingPrevious = true) else it.copy(detailLoadingNext = true)
        }
        viewModelScope.launch {
            try {
                val result = api.search(snapshot.galleryQuery, snapshot.rating, snapshot.galleryProvider, requestedPage)
                _state.update { current ->
                    val merged = if (previous) result.posts + current.detailPosts else current.detailPosts + result.posts
                    val unique = merged.distinctBy { it.dedupeKey }
                    current.copy(
                        detailPosts = unique,
                        detailFirstPage = if (previous) requestedPage else current.detailFirstPage,
                        detailLastPage = if (previous) current.detailLastPage else requestedPage,
                        detailHasMore = if (previous) current.detailHasMore else result.hasMore,
                        totalResults = result.totalResults ?: current.totalResults,
                        detailLoadingPrevious = false,
                        detailLoadingNext = false,
                        detailPreviousFailed = if (previous) false else current.detailPreviousFailed,
                        detailNextFailed = if (previous) current.detailNextFailed else false,
                    )
                }
            } catch (error: Exception) {
                _state.update {
                    it.copy(
                        detailLoadingPrevious = false,
                        detailLoadingNext = false,
                        detailPreviousFailed = if (previous) true else it.detailPreviousFailed,
                        detailNextFailed = if (previous) it.detailNextFailed else true,
                        notice = "Couldn't load more images: ${error.message ?: "Request failed"}",
                    )
                }
            }
        }
    }
    fun backToGallery() = _state.update { state ->
        val destination = when (state.detailOrigin) {
            AppScreen.FAVORITES -> AppScreen.FAVORITES
            AppScreen.RANDOM -> AppScreen.RANDOM
            else -> AppScreen.GALLERY
        }
        state.copy(screen = destination, detailImage = null, detailPosts = emptyList())
    }

    fun goHome() {
        _state.update { it.copy(queryInput = "", searchVisible = false) }
        refreshRandom()
    }

    fun isFavorite(post: ImagePost?): Boolean = post != null && _state.value.favorites.any { it.id == post.id }

    fun toggleFavorite(post: ImagePost) {
        val current = _state.value.favorites
        val exists = current.any { it.id == post.id }
        val updated = if (exists) current.filterNot { it.id == post.id } else current + post
        preferences.setFavoritePosts(updated)
        _state.update { it.copy(favorites = updated, notice = if (exists) "Removed from favorites" else "Added to favorites") }
    }

    fun removeFavorite(post: ImagePost) {
        val updated = _state.value.favorites.filterNot { it.id == post.id }
        preferences.setFavoritePosts(updated)
        _state.update { current ->
            current.copy(
                favorites = updated,
                detailPosts = if (current.detailOrigin == AppScreen.FAVORITES) current.detailPosts.filterNot { it.id == post.id } else current.detailPosts,
                detailImage = if (current.detailOrigin == AppScreen.FAVORITES && current.detailImage?.id == post.id) null else current.detailImage,
                notice = "Removed from favorites",
            )
        }
    }

    fun createUserDataBackup(): UserDataBackup {
        val current = _state.value
        return UserDataBackupCodec.create(
            favorites = preferences.favoritePosts(),
            gelbooruUserId = preferences.gelbooruUserId,
            gelbooruApiKey = preferences.gelbooruApiKey,
            rule34UserId = preferences.rule34UserId,
            rule34ApiKey = preferences.rule34ApiKey,
            provider = current.provider,
            rating = current.rating.name.lowercase(),
            allowNsfw = current.allowNsfw,
            customTerms = preferences.customSearchTerms(),
            excludeMale = current.excludeMale,
            filterGore = current.filterGore,
            customBlockTags = current.customBlockTags,
            mediaFilter = current.mediaFilter,
            useDoh = current.useDoh,
            dohProvider = current.dohProvider,
            customDohEndpoint = current.customDohEndpoint,
            ambientMode = current.ambientMode,
            videoMaxHeight = current.videoMaxHeight,
        )
    }

    fun applyUserDataBackup(data: UserDataBackup, merge: Boolean) {
        val favorites = preferences.applyUserData(data, merge)
        val provider = if (data.provider == "All") "Auto" else data.provider
        val importedRating = when (data.rating) {
            "nsfw" -> RatingFilter.NSFW
            "all" -> RatingFilter.ALL
            else -> RatingFilter.SFW
        }
        _state.update { current ->
            current.copy(
                favorites = favorites,
                provider = provider,
                allowNsfw = data.allowNsfw,
                rating = if (data.allowNsfw) importedRating else RatingFilter.SFW,
                useDoh = data.useDoh,
                dohProvider = data.dohProvider,
                customDohEndpoint = data.customDohEndpoint,
                filterGore = data.filterGore,
                excludeMale = data.excludeMale,
                customBlockTags = data.customBlockTags,
                mediaFilter = data.mediaFilter,
                videoMaxHeight = data.videoMaxHeight,
                ambientMode = data.ambientMode,
                customTerms = data.customTerms,
                detailPosts = if (current.detailOrigin == AppScreen.FAVORITES) favorites else current.detailPosts,
                notice = "User data imported",
            )
        }
        refreshCurrentResults()
    }

    fun setAllowNsfw(value: Boolean) {
        preferences.allowNsfw = value
        val resetRating = !value && _state.value.rating != RatingFilter.SFW
        if (resetRating) preferences.ratingFilter = "sfw"
        _state.update {
            it.copy(
                allowNsfw = value,
                rating = if (resetRating) RatingFilter.SFW else it.rating,
                page = if (resetRating) 1 else it.page,
                totalPages = if (resetRating) null else it.totalPages,
                hasMore = if (resetRating) false else it.hasMore,
            )
        }
        when (_state.value.screen) {
            AppScreen.RANDOM -> refreshRandom()
            AppScreen.GALLERY -> if (resetRating) loadGallery()
            else -> Unit
        }
    }
    fun setUseDoh(value: Boolean) {
        preferences.useDoh = value
        _state.update { it.copy(useDoh = value) }
    }
    fun setDohProvider(value: String) {
        preferences.dohProvider = value
        _state.update { it.copy(dohProvider = value) }
    }
    fun setCustomDohEndpoint(value: String) {
        preferences.customDohEndpoint = value.trim()
        _state.update { it.copy(customDohEndpoint = value.trim()) }
    }
    fun setFilterGore(value: Boolean) {
        preferences.filterGore = value
        _state.update { it.copy(filterGore = value) }
        refreshCurrentResults()
    }
    fun setExcludeMale(value: Boolean) {
        preferences.excludeMale = value
        _state.update { it.copy(excludeMale = value) }
        refreshCurrentResults()
    }
    fun setCustomBlockTags(value: String) {
        preferences.customBlockTags = value
        _state.update { it.copy(customBlockTags = value) }
        refreshCurrentResults()
    }
    fun setMediaFilter(value: String) {
        preferences.mediaFilter = value
        _state.update { it.copy(mediaFilter = value) }
        refreshCurrentResults()
    }
    fun setVideoMaxHeight(value: Int) {
        preferences.videoMaxHeight = value
        _state.update { it.copy(videoMaxHeight = preferences.videoMaxHeight) }
    }
    fun setAmbientMode(value: Boolean) {
        preferences.ambientMode = value
        _state.update { it.copy(ambientMode = value) }
    }
    private fun refreshCurrentResults() {
        when (_state.value.screen) {
            AppScreen.RANDOM -> refreshRandom()
            AppScreen.GALLERY -> loadGallery()
            else -> Unit
        }
    }
    fun setProvider(value: String) {
        if (value == "Gelbooru" && !hasGelbooruCredentials()) {
            openGelbooruCredentials()
            return
        }
        if (value == "Rule34.xxx" && !hasRule34Credentials()) {
            openRule34Credentials()
            return
        }
        preferences.selectedProvider = value
        _state.update { it.copy(provider = value) }
        if (_state.value.screen == AppScreen.RANDOM) refreshRandom()
    }
    fun hasGelbooruCredentials(): Boolean =
        preferences.gelbooruUserId.isNotBlank() && preferences.gelbooruApiKey.isNotBlank()

    fun hasRule34Credentials(): Boolean = preferences.rule34UserId.isNotBlank() && preferences.rule34ApiKey.isNotBlank()

    fun logoutProvider(provider: String) {
        when (provider) {
            "Gelbooru" -> { preferences.gelbooruUserId = ""; preferences.gelbooruApiKey = "" }
            "Rule34.xxx" -> { preferences.rule34UserId = ""; preferences.rule34ApiKey = "" }
            else -> return
        }
        val selectedAsDefault = _state.value.provider == provider
        val selectedInGallery = _state.value.galleryProvider == provider
        if (selectedAsDefault) preferences.selectedProvider = "Auto"
        _state.update { current ->
            current.copy(
                provider = if (selectedAsDefault) "Auto" else current.provider,
                galleryProvider = if (selectedInGallery) "All" else current.galleryProvider,
                page = if (selectedInGallery) 1 else current.page,
                totalPages = if (selectedInGallery) null else current.totalPages,
                hasMore = if (selectedInGallery) false else current.hasMore,
                notice = "Signed out of $provider",
            )
        }
        if (selectedInGallery && _state.value.galleryQuery.isNotBlank()) {
            loadGallery()
        } else if (selectedAsDefault && _state.value.screen == AppScreen.RANDOM) refreshRandom()
    }

    fun saveGelbooruCredentials(userId: String, apiKey: String) {
        preferences.gelbooruUserId = userId
        preferences.gelbooruApiKey = apiKey
        if (hasGelbooruCredentials()) {
            preferences.selectedProvider = "Gelbooru"
            val pendingFilters = pendingGalleryFilters
            pendingGalleryFilters = null
            _state.update { current ->
                current.copy(
                    provider = "Gelbooru",
                    galleryProvider = if (pendingFilters != null) "Gelbooru" else current.galleryProvider,
                    rating = pendingFilters?.second ?: current.rating,
                    page = if (pendingFilters != null) 1 else current.page,
                    totalPages = if (pendingFilters != null) null else current.totalPages,
                    hasMore = if (pendingFilters != null) false else current.hasMore,
                    error = null,
                    requestGelbooruCredentials = false,
                )
            }
            if (pendingFilters != null && _state.value.galleryQuery.isNotBlank()) loadGallery()
            else if (_state.value.screen == AppScreen.RANDOM) refreshRandom()
        }
    }
    fun saveRule34Credentials(userId: String, apiKey: String) {
        preferences.rule34UserId = userId
        preferences.rule34ApiKey = apiKey
        if (hasRule34Credentials()) {
            preferences.selectedProvider = "Rule34.xxx"
            val pendingFilters = pendingGalleryFilters
            pendingGalleryFilters = null
            _state.update { current -> current.copy(
                provider = "Rule34.xxx",
                galleryProvider = if (pendingFilters != null) "Rule34.xxx" else current.galleryProvider,
                rating = pendingFilters?.second ?: current.rating,
                page = if (pendingFilters != null) 1 else current.page,
                totalPages = if (pendingFilters != null) null else current.totalPages,
                hasMore = if (pendingFilters != null) false else current.hasMore,
                error = null,
                requestRule34Credentials = false,
            ) }
            if (pendingFilters != null && _state.value.galleryQuery.isNotBlank()) loadGallery()
            else if (_state.value.screen == AppScreen.RANDOM) refreshRandom()
        }
    }
    fun addCustomTerm(raw: String) {
        val term = raw.trim()
        if (term.isBlank()) return
        val terms = preferences.customSearchTerms().toMutableList()
        if (terms.none { it.equals(term, ignoreCase = true) }) terms.add(term)
        preferences.setCustomSearchTerms(terms)
        preferences.customSearchIndex = 0
        _state.update { it.copy(customTerms = terms) }
    }
    fun removeCustomTerm(term: String) {
        val terms = preferences.customSearchTerms().filterNot { it == term }
        preferences.setCustomSearchTerms(terms)
        preferences.customSearchIndex = 0
        _state.update { it.copy(customTerms = terms) }
    }

    fun rememberSaveFolder(uri: Uri) {
        val resolver = getApplication<Application>().contentResolver
        try {
            resolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        } catch (_: SecurityException) { }
        preferences.saveFolderUri = uri.toString()
        val name = runCatching { DocumentFile.fromTreeUri(getApplication(), uri)?.name }.getOrNull()
        _state.update { it.copy(saveFolderLabel = name ?: "Selected folder", notice = "Save folder selected") }
    }

    fun saveCurrentImage() {
        val post = _state.value.detailImage ?: _state.value.image ?: return
        val pending = _state.value.downloads.any {
            it.post.id == post.id && it.status in setOf(DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)
        }
        if (pending) {
            _state.update { it.copy(notice = "This image is already in the download queue") }
            return
        }
        val item = DownloadItem(java.util.UUID.randomUUID().toString(), post, DownloadStatus.QUEUED)
        _state.update { it.copy(downloads = it.downloads + item, error = null, notice = "Added to download queue") }
        processDownloadQueue()
    }

    fun retryDownload(id: String) {
        _state.update { state ->
            state.copy(downloads = state.downloads.map { if (it.id == id && it.status == DownloadStatus.FAILED) it.copy(status = DownloadStatus.QUEUED, error = null, progress = 0f) else it })
        }
        processDownloadQueue()
    }

    fun clearFinishedDownloads() {
        _state.update { state ->
            state.copy(downloads = state.downloads.filter { it.status == DownloadStatus.QUEUED || it.status == DownloadStatus.DOWNLOADING })
        }
    }

    private fun processDownloadQueue() {
        if (downloadJob?.isActive == true) return
        downloadJob = viewModelScope.launch {
            while (true) {
                val next = _state.value.downloads.firstOrNull { it.status == DownloadStatus.QUEUED } ?: break
                _state.update { state -> state.copy(downloads = state.downloads.map { if (it.id == next.id) it.copy(status = DownloadStatus.DOWNLOADING, error = null, progress = 0f) else it }) }
                try {
                    val downloaded = withContext(Dispatchers.IO) { downloadToCache(next.post) { progress ->
                        _state.update { state -> state.copy(downloads = state.downloads.map { if (it.id == next.id) it.copy(progress = progress) else it }) }
                    } }
                    try {
                        withContext(Dispatchers.IO) { writeImage(next.post, downloaded) }
                    } finally {
                        downloaded.delete()
                    }
                    _state.update { state -> state.copy(downloads = state.downloads.map { if (it.id == next.id) it.copy(status = DownloadStatus.SAVED, progress = 1f) else it }, notice = "Media saved") }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    _state.update { state -> state.copy(downloads = state.downloads.map { if (it.id == next.id) it.copy(status = DownloadStatus.FAILED, error = error.message ?: "Download failed") else it }) }
                }
            }
        }
    }

    private fun downloadToCache(post: ImagePost, reportProgress: (Float?) -> Unit): File {
        val temp = File.createTempFile("waifu-download-", ".tmp", getApplication<Application>().cacheDir)
        try {
            val request = Request.Builder()
                .url(post.imageUrl)
                .header("User-Agent", "Waifu Gallery/0.1")
                .header("Accept", "image/avif,image/webp,image/apng,image/*,*/*;q=0.8")
                .build()
            var lastError: Exception? = null
            repeat(3) { attempt ->
                try {
                    if (attempt > 0) reportProgress(0f)
                    api.imageClient().newCall(request).execute().use { response ->
                        if (!response.isSuccessful) {
                            val retryable = response.code == 408 || response.code == 429 || response.code >= 500
                            if (!retryable || attempt == 2) throw IOException("HTTP ${response.code}")
                            lastError = IOException("HTTP ${response.code}")
                            Thread.sleep((attempt + 1L) * 700L)
                            return@repeat
                        }
                        val body = response.body ?: throw IOException("Empty image response")
                        val contentLength = body.contentLength()
                        FileOutputStream(temp, false).use { output ->
                            body.byteStream().use { input ->
                                val buffer = ByteArray(64 * 1024)
                                var copied = 0L
                                var lastReportAt = System.nanoTime()
                                while (true) {
                                    val read = input.read(buffer)
                                    if (read < 0) break
                                    output.write(buffer, 0, read)
                                    copied += read
                                    val now = System.nanoTime()
                                    if (now - lastReportAt >= 120_000_000L) {
                                        reportProgress(if (contentLength > 0) (copied.toFloat() / contentLength).coerceIn(0f, 0.99f) else null)
                                        lastReportAt = now
                                    }
                                }
                                output.flush()
                                reportProgress(if (contentLength > 0) 1f else null)
                            }
                        }
                        if (temp.length() == 0L) throw IOException("Empty image response")
                        return temp
                    }
                } catch (error: IOException) {
                    lastError = error
                    if (attempt == 2) throw error
                    Thread.sleep((attempt + 1L) * 700L)
                }
            }
            throw lastError ?: IOException("Image download failed")
        } catch (error: Exception) {
            temp.delete()
            throw error
        }
    }

    private fun writeImage(post: ImagePost, source: File) {
        val app = getApplication<Application>()
        val name = "waifu_${post.id.substringAfterLast(':').replace(Regex("[^A-Za-z0-9_-]"), "_")}.${post.extension.ifBlank { "jpg" }}"
        val mime = if (post.mediaType == "video") "video/${post.extension.lowercase().ifBlank { "mp4" }}" else when (post.extension.lowercase()) {
            "png" -> "image/png"
            "webp" -> "image/webp"
            "gif" -> "image/gif"
            else -> "image/jpeg"
        }
        val treeUri = preferences.saveFolderUri?.let(Uri::parse)
        if (treeUri != null) {
            val directory = DocumentFile.fromTreeUri(app, treeUri)
            if (directory != null && directory.canWrite()) {
                directory.findFile(name)?.delete()
                val document = directory.createFile(mime, name) ?: throw IOException("Could not create file in selected folder")
                try {
                    app.contentResolver.openOutputStream(document.uri)?.use { output -> source.inputStream().use { it.copyTo(output) } }
                        ?: throw IOException("Could not open selected folder")
                } catch (error: Exception) {
                    document.delete()
                    throw error
                }
                return
            }
        }
        val resolver = app.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.MIME_TYPE, mime)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) put(MediaStore.MediaColumns.RELATIVE_PATH, "Pictures/Waifu Gallery")
        }
        val collection = if (post.mediaType == "video") MediaStore.Video.Media.EXTERNAL_CONTENT_URI else MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        val uri = resolver.insert(collection, values) ?: throw IOException("Could not create media in Pictures")
        try {
            resolver.openOutputStream(uri)?.use { output -> source.inputStream().use { it.copyTo(output) } } ?: throw IOException("Could not write image")
        } catch (error: Exception) {
            resolver.delete(uri, null, null)
            throw error
        } finally {
            source.delete()
        }
    }
}
