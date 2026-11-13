package com.fisalia.waifugallery

import android.app.Application
import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.util.Log
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.fisalia.waifugallery.data.AppPreferences
import com.fisalia.waifugallery.data.BooruApi
import com.fisalia.waifugallery.data.ImagePost
import com.fisalia.waifugallery.data.ProviderConnectionStatus
import com.fisalia.waifugallery.data.RatingFilter
import com.fisalia.waifugallery.data.ReleaseUpdate
import com.fisalia.waifugallery.data.ReleaseUpdateChecker
import com.fisalia.waifugallery.data.SearchPage
import com.fisalia.waifugallery.data.UserDataBackup
import com.fisalia.waifugallery.data.UserDataBackupCodec
import com.fisalia.waifugallery.data.VideoVariant
import com.fisalia.waifugallery.data.originalImageUrl
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.ConcurrentHashMap
import okhttp3.Call
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
enum class DownloadStatus { QUEUED, DOWNLOADING, SAVED, FAILED, CANCELLED }

private class DownloadCancelledException : IOException("Download cancelled")

data class DownloadItem(
    val id: String,
    val post: ImagePost,
    val status: DownloadStatus,
    val error: String? = null,
    val progress: Float? = null,
    val savedUri: String? = null,
    val savedLocation: String? = null,
)

private data class SavedDownload(val uri: Uri, val location: String)

data class UiState(
    val screen: AppScreen = AppScreen.RANDOM,
    val image: ImagePost? = null,
    val detailImage: ImagePost? = null,
    val detailOrigin: AppScreen = AppScreen.RANDOM,
    val queryInput: String = "",
    val galleryQuery: String = "",
    val gallery: List<ImagePost> = emptyList(),
    val galleryProviderErrors: List<String> = emptyList(),
    val providerConnectionStatuses: List<ProviderConnectionStatus> = emptyList(),
    val isTestingProviderConnections: Boolean = false,
    val providerConnectionError: String? = null,
    val favorites: List<ImagePost> = emptyList(),
    val favoritesLockEnabled: Boolean = false,
    val favoritesPinSet: Boolean = false,
    val requestFavoritesUnlock: Boolean = false,
    val parentalControlEnabled: Boolean = false,
    val parentalPinSet: Boolean = false,
    val parentalMaximumRating: String = "s",
    val parentalAllowedTags: List<String> = emptyList(),
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
    val showSettings: Boolean = false,
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
    val isCheckingReleaseUpdate: Boolean = false,
    val releaseUpdateCheckMessage: String? = null,
    val isDownloadingReleaseUpdate: Boolean = false,
    val releaseDownloadProgress: Int? = null,
    val downloadedUpdateApk: String? = null,
    val releaseDownloadError: String? = null,
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
            favoritesLockEnabled = preferences.favoritesLockEnabled,
            favoritesPinSet = preferences.hasSafetyPin("favorites_lock"),
            parentalControlEnabled = preferences.parentalControlEnabled,
            parentalPinSet = preferences.hasSafetyPin("parent"),
            parentalMaximumRating = preferences.parentalMaximumRating,
            parentalAllowedTags = preferences.parentalAllowedTags,
            customTerms = preferences.customSearchTerms(),
            saveFolderLabel = preferences.saveFolderUri?.let { runCatching { DocumentFile.fromTreeUri(application, Uri.parse(it))?.name }.getOrNull() },
            downloads = restoreDownloadHistory(preferences.downloadHistoryJson),
        ),
    )
    val state: StateFlow<UiState> = _state.asStateFlow()
    private var downloadJob: Job? = null
    @Volatile private var activeDownloadId: String? = null
    @Volatile private var activeDownloadCall: Call? = null
    private val cancelledDownloadIds = ConcurrentHashMap.newKeySet<String>()
    private var releaseDownloadJob: Job? = null
    private var pendingGalleryFilters: Pair<String, RatingFilter>? = null

    init {
        persistDownloadHistory()
        refreshRandom()
        checkForReleaseUpdate()
    }

    fun checkForReleaseUpdate() {
        if (_state.value.isCheckingReleaseUpdate) return
        _state.update {
            it.copy(
                isCheckingReleaseUpdate = true,
                releaseUpdateCheckMessage = "Checking GitHub Releases...",
            )
        }
        viewModelScope.launch {
            try {
                val result = ReleaseUpdateChecker.checkForUpdateResult(getApplication())
                _state.update {
                    it.copy(
                        releaseUpdate = result.update,
                        releaseUpdateCheckMessage = result.error
                            ?: result.update?.let { update -> "Version ${update.version} is available." }
                            ?: "You're up to date.",
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } finally {
                _state.update { it.copy(isCheckingReleaseUpdate = false) }
            }
        }
    }

    fun dismissReleaseUpdate() = _state.update {
        it.copy(
            releaseUpdate = null,
            releaseDownloadProgress = null,
            isDownloadingReleaseUpdate = false,
            downloadedUpdateApk = null,
            releaseDownloadError = null,
        )
    }
    fun downloadReleaseUpdate() {
        val update = _state.value.releaseUpdate ?: return
        if (releaseDownloadJob?.isActive == true) return
        _state.update {
            it.copy(
                isDownloadingReleaseUpdate = true,
                releaseDownloadProgress = null,
                downloadedUpdateApk = null,
                releaseDownloadError = null,
            )
        }
        releaseDownloadJob = viewModelScope.launch {
            try {
                val apk = ReleaseUpdateChecker.downloadApk(getApplication(), update) { progress ->
                    _state.update { state ->
                        state.copy(releaseDownloadProgress = progress)
                    }
                }
                _state.update {
                    it.copy(
                        isDownloadingReleaseUpdate = false,
                        releaseDownloadProgress = null,
                        downloadedUpdateApk = apk.absolutePath,
                        releaseDownloadError = null,
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                _state.update {
                    it.copy(
                        isDownloadingReleaseUpdate = false,
                        releaseDownloadProgress = null,
                        releaseDownloadError = error.message ?: "APK download failed.",
                    )
                }
            } finally {
                releaseDownloadJob = null
            }
        }
    }

    fun reportReleaseInstallError(message: String) {
        _state.update { it.copy(releaseDownloadError = message) }
    }
    fun updateQuery(value: String) = _state.update { it.copy(queryInput = value) }
    fun toggleSearch() {
        _state.update { it.copy(searchVisible = !it.searchVisible, queryInput = if (it.searchVisible) "" else it.queryInput) }
        if (!_state.value.searchVisible && _state.value.screen == AppScreen.GALLERY) refreshRandom()
    }
    fun openSettings() = _state.update { it.copy(showSettings = true) }
    fun closeSettings() = _state.update { it.copy(showSettings = false) }
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
    fun openFavorites() {
        if (!preferences.favoritesLockEnabled) {
            _state.update { it.copy(screen = AppScreen.FAVORITES, searchVisible = false) }
        } else if (!preferences.hasSafetyPin("favorites_lock")) {
            _state.update {
                it.copy(notice = "Favorites PIN is unavailable. Reset it from Settings > Safety & Privacy.")
            }
        } else {
            _state.update { it.copy(requestFavoritesUnlock = true) }
        }
    }

    fun cancelFavoritesUnlock() = _state.update { it.copy(requestFavoritesUnlock = false) }

    fun verifyFavoritesUnlock(pin: String): AppPreferences.PinVerification {
        val result = preferences.verifySafetyPin("favorites_lock", pin)
        if (result.accepted) {
            _state.update {
                it.copy(requestFavoritesUnlock = false, screen = AppScreen.FAVORITES, searchVisible = false)
            }
        }
        return result
    }

    fun verifySafetyPin(scope: String, pin: String): AppPreferences.PinVerification =
        preferences.verifySafetyPin(scope, pin)

    fun setSafetyPin(scope: String, pin: String) {
        preferences.setSafetyPin(scope, pin)
        refreshSafetyState()
    }

    fun removeSafetyPin(scope: String) {
        preferences.removeSafetyPin(scope)
        when (scope) {
            "favorites_lock" -> preferences.favoritesLockEnabled = false
            "parent" -> preferences.parentalControlEnabled = false
            else -> throw IllegalArgumentException("Unknown safety PIN.")
        }
        refreshSafetyState()
        refreshCurrentResults()
    }

    fun setFavoritesLockEnabled(enabled: Boolean) {
        preferences.favoritesLockEnabled = enabled
        refreshSafetyState()
    }

    fun setParentalControlEnabled(enabled: Boolean) {
        preferences.parentalControlEnabled = enabled
        refreshSafetyState()
        refreshCurrentResults()
    }

    fun setParentalPolicy(maximumRating: String, allowedTags: String) {
        preferences.parentalMaximumRating = maximumRating
        preferences.parentalAllowedTags = allowedTags.split(Regex("[,\\s]+"))
        refreshSafetyState()
        refreshCurrentResults()
    }

    private fun refreshSafetyState() {
        _state.update { current ->
            val visibleDetailImage = current.detailImage?.takeIf(::parentAllowsPost)
            val returnFromRestrictedDetail = current.screen == AppScreen.DETAIL &&
                current.detailImage != null && visibleDetailImage == null
            current.copy(
                favoritesLockEnabled = preferences.favoritesLockEnabled,
                favoritesPinSet = preferences.hasSafetyPin("favorites_lock"),
                parentalControlEnabled = preferences.parentalControlEnabled,
                parentalPinSet = preferences.hasSafetyPin("parent"),
                parentalMaximumRating = preferences.parentalMaximumRating,
                parentalAllowedTags = preferences.parentalAllowedTags,
                screen = if (returnFromRestrictedDetail) current.detailOrigin else current.screen,
                image = current.image?.takeIf(::parentAllowsPost),
                detailImage = visibleDetailImage,
                gallery = current.gallery.filter(::parentAllowsPost),
                detailPosts = current.detailPosts.filter(::parentAllowsPost),
            )
        }
    }

    fun parentalAllows(post: ImagePost): Boolean = parentAllowsPost(post)

    private fun parentAllowsPost(post: ImagePost): Boolean {
        if (!preferences.parentalControlEnabled) return true
        val ranks = mapOf("s" to 0, "q" to 1, "e" to 2)
        val postRank = ranks[post.rating] ?: return false
        if (postRank > (ranks[preferences.parentalMaximumRating] ?: 0)) return false
        val allowedTags = preferences.parentalAllowedTags
        return allowedTags.isEmpty() || post.tags.any { tag ->
            tag.trim().lowercase().replace(Regex("\\s+"), "_") in allowedTags
        }
    }

    private fun effectiveRating(requested: RatingFilter): RatingFilter {
        if (!preferences.parentalControlEnabled) return requested
        val maximum = mapOf("s" to 0, "q" to 1, "e" to 2)[preferences.parentalMaximumRating] ?: 0
        val requestedRank = if (requested == RatingFilter.SFW) 0 else 2
        return if (requestedRank <= maximum) requested else if (maximum == 0) {
            RatingFilter.SFW
        } else {
            RatingFilter.ALL
        }
    }
    fun openDownloadQueue() = _state.update { it.copy(showSettings = false, showDownloadQueue = true) }
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

    fun searchTag(tag: String) {
        val normalizedTag = tag.trim()
        if (normalizedTag.isBlank()) return
        _state.update { it.copy(queryInput = normalizedTag) }
        search()
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
                val maximumRating = if (preferences.parentalControlEnabled) {
                    preferences.parentalMaximumRating
                } else {
                    null
                }
                val randomNsfw = preferences.allowNsfw && maximumRating != "s"
                val attempts = if (preferences.parentalControlEnabled && preferences.parentalAllowedTags.isNotEmpty()) 10 else 1
                var image: ImagePost? = null
                for (attempt in 0 until attempts) {
                    val candidate = api.randomImage(
                        randomNsfw,
                        term,
                        preferences.selectedProvider,
                        maximumRating,
                    )
                    if (parentAllowsPost(candidate)) {
                        image = candidate
                        break
                    }
                }
                val selectedImage = image
                    ?: throw IllegalStateException("No image matched the active parental rating and allowed tags.")
                _state.update { it.copy(image = selectedImage, isLoading = false) }
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
        val effective = effectiveRating(rating)
        if (!preferences.allowNsfw && effective != RatingFilter.SFW) {
            _state.update { it.copy(notice = "Enable NSFW results in Settings to use this rating.") }
            return
        }
        if (provider == "Gelbooru" && !hasGelbooruCredentials()) {
            pendingGalleryFilters = provider to effective
            openGelbooruCredentials()
            return
        }
        if (provider == "Rule34.xxx" && !hasRule34Credentials()) {
            pendingGalleryFilters = provider to effective
            openRule34Credentials()
            return
        }
        if (provider == _state.value.galleryProvider && effective == _state.value.rating) return
        preferences.ratingFilter = effective.name.lowercase()
        _state.update { it.copy(galleryProvider = provider, rating = effective, page = 1, totalPages = null, hasMore = false) }
        loadGallery()
    }

    fun setRating(rating: RatingFilter) {
        val effective = effectiveRating(rating)
        if (!preferences.allowNsfw && effective != RatingFilter.SFW) {
            _state.update { it.copy(notice = "Enable NSFW results in Settings to use this rating.") }
            return
        }
        if (effective == _state.value.rating) return
        preferences.ratingFilter = effective.name.lowercase()
        _state.update { it.copy(rating = effective, page = 1, totalPages = null, hasMore = false) }
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
        _state.update {
            it.copy(
                screen = AppScreen.GALLERY,
                gallery = emptyList(),
                galleryProviderErrors = emptyList(),
                totalResults = null,
                isLoading = true,
                error = null,
            )
        }
        viewModelScope.launch {
            try {
                val result: SearchPage = api.search(
                    snapshot.galleryQuery,
                    effectiveRating(snapshot.rating),
                    snapshot.galleryProvider,
                    snapshot.page,
                )
                _state.update {
                    it.copy(
                        gallery = result.posts.filter(::parentAllowsPost),
                        galleryProviderErrors = result.providerErrors,
                        hasMore = result.hasMore,
                        totalPages = result.totalPages,
                        totalResults = result.totalResults,
                        isLoading = false,
                    )
                }
            } catch (error: Exception) {
                _state.update {
                    it.copy(
                        galleryProviderErrors = emptyList(),
                        isLoading = false,
                        error = "Failed to search images:\n${error.message ?: "Unknown error"}",
                    )
                }
            }
        }
    }

    fun openDetail(post: ImagePost) {
        if (!parentAllowsPost(post)) {
            _state.update { it.copy(notice = "This post is restricted by Parental control.") }
            return
        }
        _state.update { current ->
            val origin = current.screen
            val detailPosts = when (origin) {
                AppScreen.GALLERY -> current.gallery
                AppScreen.FAVORITES -> current.favorites.filter(::parentAllowsPost)
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
                totalResults = if (origin == AppScreen.FAVORITES) detailPosts.size else current.totalResults,
                detailLoadingPrevious = false,
                detailLoadingNext = false,
                detailPreviousFailed = false,
                detailNextFailed = false,
            )
        }
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
                val result = api.search(
                    snapshot.galleryQuery,
                    effectiveRating(snapshot.rating),
                    snapshot.galleryProvider,
                    requestedPage,
                )
                _state.update { current ->
                    val pagePosts = result.posts.filter(::parentAllowsPost)
                    val merged = if (previous) pagePosts + current.detailPosts else current.detailPosts + pagePosts
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
        removeFavorites(listOf(post))
    }

    fun removeFavorites(posts: List<ImagePost>) {
        val selectedIds = posts.mapTo(mutableSetOf()) { it.id }
        if (selectedIds.isEmpty()) return
        val currentFavorites = _state.value.favorites
        val updated = currentFavorites.filterNot { it.id in selectedIds }
        val removedCount = currentFavorites.size - updated.size
        if (removedCount == 0) return
        preferences.setFavoritePosts(updated)
        _state.update { current ->
            current.copy(
                favorites = current.favorites.filterNot { it.id in selectedIds },
                detailPosts = if (current.detailOrigin == AppScreen.FAVORITES) {
                    current.detailPosts.filterNot { it.id in selectedIds }
                } else current.detailPosts,
                detailImage = if (
                    current.detailOrigin == AppScreen.FAVORITES &&
                    current.detailImage?.id in selectedIds
                ) null else current.detailImage,
                notice = if (removedCount == 1) {
                    "Removed from favorites"
                } else {
                    "Removed $removedCount favorites"
                },
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
        val importsSettings = "settings" in data.includedSections
        val importedRating = if (importsSettings) {
            when (data.rating) {
                "nsfw" -> RatingFilter.NSFW
                "all" -> RatingFilter.ALL
                else -> RatingFilter.SFW
            }
        } else null
        _state.update { current ->
            current.copy(
                favorites = favorites,
                provider = if (importsSettings) {
                    if (data.provider == "All") "Auto" else data.provider
                } else current.provider,
                allowNsfw = if (importsSettings) data.allowNsfw else current.allowNsfw,
                rating = if (importsSettings) {
                    if (data.allowNsfw) importedRating ?: RatingFilter.SFW else RatingFilter.SFW
                } else current.rating,
                useDoh = if (importsSettings) data.useDoh else current.useDoh,
                dohProvider = if (importsSettings) data.dohProvider else current.dohProvider,
                customDohEndpoint = if (importsSettings) data.customDohEndpoint else current.customDohEndpoint,
                filterGore = if (importsSettings) data.filterGore else current.filterGore,
                excludeMale = if (importsSettings) data.excludeMale else current.excludeMale,
                customBlockTags = if (importsSettings) data.customBlockTags else current.customBlockTags,
                mediaFilter = if (importsSettings) data.mediaFilter else current.mediaFilter,
                videoMaxHeight = if (importsSettings) data.videoMaxHeight else current.videoMaxHeight,
                ambientMode = if (importsSettings) data.ambientMode else current.ambientMode,
                customTerms = if (importsSettings) data.customTerms else current.customTerms,
                detailPosts = if (
                    "favorites" in data.includedSections &&
                    current.detailOrigin == AppScreen.FAVORITES
                ) favorites else current.detailPosts,
                notice = "User data imported",
            )
        }
        if (importsSettings) refreshCurrentResults()
    }

    fun setRatingPreference(rating: RatingFilter) {
        val effective = effectiveRating(rating)
        val allowNsfw = effective != RatingFilter.SFW
        if (effective == _state.value.rating && allowNsfw == _state.value.allowNsfw) return
        preferences.allowNsfw = allowNsfw
        preferences.ratingFilter = effective.name.lowercase()
        _state.update {
            it.copy(
                allowNsfw = allowNsfw,
                rating = effective,
                page = 1,
                totalPages = null,
                hasMore = false,
                notice = if (effective != rating) {
                    "The rating was limited by Parental control."
                } else {
                    it.notice
                },
            )
        }
        val current = _state.value
        when (current.screen) {
            AppScreen.RANDOM -> refreshRandom()
            AppScreen.GALLERY -> loadGallery()
            AppScreen.DETAIL -> when (current.detailOrigin) {
                AppScreen.RANDOM -> refreshRandom()
                AppScreen.GALLERY -> loadGallery()
                else -> Unit
            }
            AppScreen.FAVORITES -> Unit
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
        val current = _state.value
        when (current.screen) {
            AppScreen.RANDOM -> refreshRandom()
            AppScreen.GALLERY -> loadGallery()
            AppScreen.DETAIL -> when (current.detailOrigin) {
                AppScreen.RANDOM -> refreshRandom()
                AppScreen.GALLERY -> loadGallery()
                else -> Unit
            }
            AppScreen.FAVORITES -> Unit
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

    fun testProviderConnections() {
        if (_state.value.isTestingProviderConnections) return
        _state.update {
            it.copy(
                isTestingProviderConnections = true,
                providerConnectionStatuses = emptyList(),
                providerConnectionError = null,
            )
        }
        viewModelScope.launch {
            try {
                val statuses = api.testProviderConnections()
                _state.update {
                    it.copy(
                        isTestingProviderConnections = false,
                        providerConnectionStatuses = statuses,
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: IOException) {
                _state.update {
                    it.copy(
                        isTestingProviderConnections = false,
                        providerConnectionError = "Provider test failed: ${error.message ?: "Network request failed"}",
                    )
                }
            } catch (error: IllegalArgumentException) {
                _state.update {
                    it.copy(
                        isTestingProviderConnections = false,
                        providerConnectionError = "Provider test failed: ${error.message ?: "Invalid request"}",
                    )
                }
            }
        }
    }

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
        queueDownloads(listOf(post))
    }

    fun queueFavoriteDownloads(posts: List<ImagePost>) {
        queueDownloads(posts)
    }

    private fun queueDownloads(posts: List<ImagePost>) {
        val uniquePosts = posts.distinctBy { it.dedupeKey.ifBlank { it.id } }
        val existingPosts = _state.value.downloads
            .filter { it.status != DownloadStatus.FAILED && it.status != DownloadStatus.CANCELLED }
            .map { it.post }
        val existingIds = existingPosts.mapTo(mutableSetOf()) { it.id }
        val existingDedupeKeys = existingPosts.mapNotNullTo(mutableSetOf()) {
            it.dedupeKey.takeIf { key -> key.isNotBlank() }
        }
        val newPosts = uniquePosts.filterNot { post ->
            post.id in existingIds || (post.dedupeKey.isNotBlank() && post.dedupeKey in existingDedupeKeys)
        }
        val skipped = uniquePosts.size - newPosts.size
        if (newPosts.isEmpty()) {
            _state.update {
                it.copy(notice = "Selected media are already saved or queued")
            }
            return
        }
        val newItems = newPosts.map { post ->
            DownloadItem(java.util.UUID.randomUUID().toString(), post, DownloadStatus.QUEUED)
        }
        val notice = "Added ${newItems.size} media to the download queue" +
            if (skipped > 0) "; skipped $skipped already saved or queued" else ""
        _state.update {
            it.copy(downloads = it.downloads + newItems, error = null, notice = notice)
        }
        persistDownloadHistory()
        processDownloadQueue()
    }

    fun retryDownload(id: String) {
        _state.update { state ->
            state.copy(downloads = state.downloads.map { if (it.id == id && it.status == DownloadStatus.FAILED) it.copy(status = DownloadStatus.QUEUED, error = null, progress = 0f) else it })
        }
        persistDownloadHistory()
        processDownloadQueue()
    }

    fun cancelDownload(id: String) {
        if (activeDownloadId != id) return
        cancelledDownloadIds.add(id)
        activeDownloadCall?.cancel()
    }

    fun openSavedDownload(id: String) {
        val item = _state.value.downloads.firstOrNull { it.id == id } ?: return
        val savedUri = item.savedUri
        if (item.status != DownloadStatus.SAVED || savedUri.isNullOrBlank()) {
            _state.update { it.copy(notice = "This downloaded file is no longer available.") }
            return
        }

        val mime = if (item.post.mediaType == "video") {
            "video/${item.post.extension.lowercase().ifBlank { "mp4" }}"
        } else {
            when (item.post.extension.lowercase()) {
                "png" -> "image/png"
                "webp" -> "image/webp"
                "gif" -> "image/gif"
                else -> "image/jpeg"
            }
        }
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(Uri.parse(savedUri), mime)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            getApplication<Application>().startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            _state.update { it.copy(notice = "No gallery app is available to open this file.") }
        } catch (_: SecurityException) {
            _state.update { it.copy(notice = "Permission to open this downloaded file was denied.") }
        }
    }

    fun clearFinishedDownloads() {
        _state.update { state ->
            state.copy(downloads = state.downloads.filter { it.status == DownloadStatus.QUEUED || it.status == DownloadStatus.DOWNLOADING })
        }
        persistDownloadHistory()
    }

    private fun processDownloadQueue() {
        if (downloadJob?.isActive == true) return
        downloadJob = viewModelScope.launch {
            while (true) {
                val next = _state.value.downloads.firstOrNull { it.status == DownloadStatus.QUEUED } ?: break
                _state.update { state -> state.copy(downloads = state.downloads.map { if (it.id == next.id) it.copy(status = DownloadStatus.DOWNLOADING, error = null, progress = 0f) else it }) }
                persistDownloadHistory()
                try {
                    activeDownloadId = next.id
                    val downloaded = withContext(Dispatchers.IO) {
                        downloadToCache(
                            next.post,
                            reportProgress = { progress ->
                                _state.update { state ->
                                    state.copy(downloads = state.downloads.map {
                                        if (it.id == next.id) it.copy(progress = progress) else it
                                    })
                                }
                            },
                            onCallCreated = { activeDownloadCall = it },
                            isCancelled = { next.id in cancelledDownloadIds },
                        )
                    }
                    activeDownloadCall = null
                    activeDownloadId = null
                    val savedDownload = try {
                        if (cancelledDownloadIds.remove(next.id)) throw DownloadCancelledException()
                        withContext(Dispatchers.IO) { writeImage(next.post, downloaded) }
                    } finally {
                        downloaded.delete()
                    }
                    _state.update { state ->
                        state.copy(
                            downloads = state.downloads.map {
                                if (it.id == next.id) it.copy(
                                    status = DownloadStatus.SAVED,
                                    progress = 1f,
                                    savedUri = savedDownload.uri.toString(),
                                    savedLocation = savedDownload.location,
                                ) else it
                            },
                            notice = "Media saved",
                        )
                    }
                    persistDownloadHistory()
                } catch (_: DownloadCancelledException) {
                    cancelledDownloadIds.remove(next.id)
                    _state.update { state ->
                        state.copy(downloads = state.downloads.map {
                            if (it.id == next.id) it.copy(
                                status = DownloadStatus.CANCELLED,
                                error = null,
                                progress = null,
                            ) else it
                        })
                    }
                    persistDownloadHistory()
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    _state.update { state -> state.copy(downloads = state.downloads.map { if (it.id == next.id) it.copy(status = DownloadStatus.FAILED, error = error.message ?: "Download failed") else it }) }
                    persistDownloadHistory()
                } finally {
                    activeDownloadCall = null
                    if (activeDownloadId == next.id) activeDownloadId = null
                    cancelledDownloadIds.remove(next.id)
                }
            }
        }
    }

    private fun persistDownloadHistory() {
        preferences.downloadHistoryJson = JSONArray().apply {
            _state.value.downloads.forEach { item ->
                put(JSONObject().apply {
                    put("id", item.id)
                    put("post", item.post.toDownloadJson())
                    put("status", item.status.name)
                    put("error", item.error)
                    put("savedUri", item.savedUri)
                    put("savedLocation", item.savedLocation)
                })
            }
        }.toString()
    }

    private fun restoreDownloadHistory(json: String): List<DownloadItem> {
        val entries = try {
            JSONArray(json)
        } catch (error: Exception) {
            throw IllegalStateException("Saved download history could not be read.", error)
        }
        return (0 until entries.length()).mapNotNull { index ->
            val item = entries.optJSONObject(index)
            if (item == null) {
                Log.w("WaifuGallery", "Skipped an invalid download history entry.")
                return@mapNotNull null
            }
            try {
                val status = DownloadStatus.valueOf(item.getString("status"))
                val interrupted = status == DownloadStatus.QUEUED || status == DownloadStatus.DOWNLOADING
                DownloadItem(
                    id = item.getString("id"),
                    post = item.getJSONObject("post").toImagePost(),
                    status = if (interrupted) DownloadStatus.FAILED else status,
                    error = if (interrupted) {
                        "App closed before download completed. Retry to download again."
                    } else {
                        item.optString("error").takeIf(String::isNotBlank)
                    },
                    savedUri = item.optString("savedUri").takeIf(String::isNotBlank),
                    savedLocation = item.optString("savedLocation").takeIf(String::isNotBlank),
                )
            } catch (error: Exception) {
                Log.w("WaifuGallery", "Skipped an unreadable download history entry.", error)
                null
            }
        }
    }

    private fun ImagePost.toDownloadJson() = JSONObject().apply {
        put("id", id)
        put("dedupeKey", dedupeKey)
        put("provider", provider)
        put("imageUrl", imageUrl)
        put("thumbnailUrl", thumbnailUrl)
        put("thumbnailCandidates", JSONArray(thumbnailCandidates))
        put("extension", extension)
        put("rating", rating)
        put("tags", JSONArray(tags))
        put("source", source)
        put("artists", JSONArray(artists))
        put("mediaType", mediaType)
        put("title", title)
        put("width", width)
        put("height", height)
        put("videoVariants", JSONArray().apply {
            videoVariants.forEach { variant ->
                put(JSONObject().apply {
                    put("url", variant.url)
                    put("width", variant.width)
                    put("height", variant.height)
                })
            }
        })
    }

    private fun JSONObject.toImagePost(): ImagePost {
        val thumbnailCandidates = optJSONArray("thumbnailCandidates").stringList()
        val mediaType = optString("mediaType", "image")
        return ImagePost(
            id = getString("id"),
            dedupeKey = optString("dedupeKey"),
            provider = getString("provider"),
            imageUrl = getString("imageUrl").let { url ->
                if (mediaType == "video") url else originalImageUrl(url, thumbnailCandidates)
            },
            thumbnailUrl = getString("thumbnailUrl"),
            thumbnailCandidates = thumbnailCandidates,
            extension = optString("extension", "jpg"),
            rating = optString("rating"),
            tags = optJSONArray("tags").stringList().toSet(),
            source = optString("source"),
            artists = optJSONArray("artists").stringList(),
            mediaType = mediaType,
            title = optString("title"),
            width = optInt("width", 0),
            height = optInt("height", 0),
            videoVariants = optJSONArray("videoVariants")?.let { variants ->
                (0 until variants.length()).mapNotNull { variantIndex ->
                    val variant = variants.optJSONObject(variantIndex) ?: return@mapNotNull null
                    variant.optString("url").takeIf(String::isNotBlank)?.let { url ->
                        VideoVariant(url, variant.optInt("width", 0), variant.optInt("height", 0))
                    }
                }
            }.orEmpty(),
        )
    }

    private fun JSONArray?.stringList(): List<String> = this?.let { array ->
        (0 until array.length()).mapNotNull { array.optString(it).takeIf(String::isNotBlank) }
    }.orEmpty()

    private fun downloadToCache(
        post: ImagePost,
        reportProgress: (Float?) -> Unit,
        onCallCreated: (Call) -> Unit,
        isCancelled: () -> Boolean,
    ): File {
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
                    if (isCancelled()) throw DownloadCancelledException()
                    if (attempt > 0) reportProgress(0f)
                    val call = api.imageClient().newCall(request)
                    onCallCreated(call)
                    call.execute().use { response ->
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
                                    if (isCancelled()) throw DownloadCancelledException()
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
                                reportProgress(1f)
                            }
                        }
                        if (isCancelled()) throw DownloadCancelledException()
                        if (temp.length() == 0L) throw IOException("Empty image response")
                        return temp
                    }
                } catch (cancelled: DownloadCancelledException) {
                    throw cancelled
                } catch (error: IOException) {
                    if (isCancelled()) throw DownloadCancelledException()
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

    private fun writeImage(post: ImagePost, source: File): SavedDownload {
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
                return SavedDownload(document.uri, directory.name ?: "Selected folder")
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
        return SavedDownload(uri, "Pictures/Waifu Gallery")
    }
}
