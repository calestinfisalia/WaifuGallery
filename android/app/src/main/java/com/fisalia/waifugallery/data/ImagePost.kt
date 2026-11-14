package com.fisalia.waifugallery.data

data class ImagePost(
    val id: String,
    val dedupeKey: String,
    val provider: String,
    val imageUrl: String,
    val thumbnailUrl: String,
    val thumbnailCandidates: List<String>,
    val extension: String,
    val rating: String,
    val tags: Set<String>,
    val source: String,
    val artists: List<String>,
    val mediaType: String = "image",
    val title: String = "",
    val width: Int = 0,
    val height: Int = 0,
    val videoVariants: List<VideoVariant> = emptyList(),
    val sampleUrl: String = "",
)

data class VideoVariant(val url: String, val width: Int, val height: Int)

fun ImagePost.mediumPreviewCandidates(): List<String> {
    val mediumUrl = sampleUrl.takeIf(String::isNotBlank)
        ?: thumbnailCandidates.firstOrNull {
            it.isNotBlank() && it != thumbnailUrl && it != imageUrl
        }.orEmpty()
    return (listOf(mediumUrl) + thumbnailCandidates)
        .filter { it.isNotBlank() && it != imageUrl }
        .distinct()
}

fun originalImageUrl(imageUrl: String, thumbnailCandidates: List<String>): String =
    if (imageUrl in thumbnailCandidates) {
        thumbnailCandidates.lastOrNull { it != imageUrl } ?: imageUrl
    } else {
        imageUrl
    }

data class SearchPage(
    val posts: List<ImagePost>,
    val hasMore: Boolean,
    val totalPages: Int? = null,
    val totalResults: Int? = null,
    val providerErrors: List<String> = emptyList(),
)

enum class RatingFilter(val label: String) {
    ALL("Show All"), SFW("Only SFW"), NSFW("Only NSFW"),
}
