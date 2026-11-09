package com.fisalia.waifugallery.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

class AppPreferences(context: Context) {
    private val store = context.getSharedPreferences("waifu_gallery", Context.MODE_PRIVATE)

    var allowNsfw: Boolean
        get() = store.getBoolean("nsfw", false)
        set(value) = store.edit().putBoolean("nsfw", value).apply()

    var ratingFilter: String
        get() = (store.getString("rating_filter", "sfw") ?: "sfw")
            .takeIf { it in setOf("sfw", "nsfw", "all") } ?: "sfw"
        set(value) {
            require(value in setOf("sfw", "nsfw", "all"))
            store.edit().putString("rating_filter", value).apply()
        }

    var useDoh: Boolean
        get() = store.getBoolean("doh", false)
        set(value) = store.edit().putBoolean("doh", value).apply()

    var selectedProvider: String
        get() = (store.getString("provider", "Auto") ?: "Auto").let { saved ->
            if (saved == "Konachan") "Auto" else saved
        }
        set(value) = store.edit().putString("provider", value).apply()

    var gelbooruUserId: String
        get() = store.getString("gelbooru_user_id", "") ?: ""
        set(value) = store.edit().putString("gelbooru_user_id", value.trim()).apply()

    var gelbooruApiKey: String
        get() = store.getString("gelbooru_api_key", "") ?: ""
        set(value) = store.edit().putString("gelbooru_api_key", value.trim()).apply()

    var rule34UserId: String
        get() = store.getString("rule34_user_id", "") ?: ""
        set(value) = store.edit().putString("rule34_user_id", value.trim()).apply()

    var rule34ApiKey: String
        get() = store.getString("rule34_api_key", "") ?: ""
        set(value) = store.edit().putString("rule34_api_key", value.trim()).apply()

    var dohProvider: String
        get() = store.getString("doh_provider", "Cloudflare") ?: "Cloudflare"
        set(value) = store.edit().putString("doh_provider", value).apply()

    var customDohEndpoint: String
        get() = store.getString("custom_doh_endpoint", "") ?: ""
        set(value) = store.edit().putString("custom_doh_endpoint", value.trim()).apply()

    var filterGore: Boolean
        get() = store.getBoolean("filter_gore", true)
        set(value) = store.edit().putBoolean("filter_gore", value).apply()

    var excludeMale: Boolean
        get() = store.getBoolean("exclude_male", true)
        set(value) = store.edit().putBoolean("exclude_male", value).apply()

    var customBlockTags: String
        get() = store.getString("custom_block_tags", "") ?: ""
        set(value) = store.edit().putString("custom_block_tags", value).apply()

    var mediaFilter: String
        get() = store.getString("media_filter", "image") ?: "image"
        set(value) = store.edit().putString("media_filter", value).apply()

    var videoMaxHeight: Int
        get() = store.getInt("video_max_height", 0)
        set(value) = store.edit().putInt("video_max_height", value.coerceAtLeast(0)).apply()

    var ambientMode: Boolean
        get() = store.getBoolean("ambient_mode", true)
        set(value) = store.edit().putBoolean("ambient_mode", value).apply()

    var customSearchIndex: Int
        get() = store.getInt("custom_search_index", 0)
        set(value) = store.edit().putInt("custom_search_index", value).apply()

    var saveFolderUri: String?
        get() = store.getString("save_folder_uri", null)
        set(value) { store.edit().putString("save_folder_uri", value).apply() }

    fun customSearchTerms(): List<String> = try {
        val array = JSONArray(store.getString("custom_search_terms", "[]"))
        (0 until array.length()).mapNotNull { array.optString(it).takeIf(String::isNotBlank) }
    } catch (_: Exception) {
        emptyList()
    }

    fun setCustomSearchTerms(terms: List<String>) {
        val array = JSONArray()
        terms.forEach(array::put)
        store.edit().putString("custom_search_terms", array.toString()).apply()
    }

    fun favoritePosts(): List<ImagePost> = try {
        val array = JSONArray(store.getString("favorite_posts", "[]"))
        (0 until array.length()).mapNotNull { index ->
            runCatching {
                val item = array.getJSONObject(index)
                ImagePost(
                    id = item.getString("id"),
                    dedupeKey = item.optString("dedupeKey"),
                    provider = item.getString("provider"),
                    imageUrl = item.getString("imageUrl"),
                    thumbnailUrl = item.getString("thumbnailUrl"),
                    thumbnailCandidates = item.optJSONArray("thumbnailCandidates").toStringList(),
                    extension = item.optString("extension", "jpg"),
                    rating = item.optString("rating"),
                    tags = item.optJSONArray("tags").toStringList().toSet(),
                    source = item.optString("source"),
                    artists = item.optJSONArray("artists").toStringList(),
                    mediaType = item.optString("mediaType", "image"),
                    title = item.optString("title", ""),
                    width = item.optInt("width", 0),
                    height = item.optInt("height", 0),
                    videoVariants = item.optJSONArray("videoVariants")?.let { variants ->
                        (0 until variants.length()).mapNotNull { variantIndex ->
                            val variant = variants.optJSONObject(variantIndex) ?: return@mapNotNull null
                            val url = variant.optString("url")
                            if (url.isBlank()) null else VideoVariant(
                                url = url,
                                width = variant.optInt("width", 0),
                                height = variant.optInt("height", 0),
                            )
                        }
                    }.orEmpty(),
                )
            }.getOrNull()
        }
    } catch (_: Exception) {
        emptyList()
    }

    fun backupFavoritePosts(): List<ImagePost> {
        val saved = store.getString("favorite_posts", "[]") ?: "[]"
        val count = try {
            JSONArray(saved).length()
        } catch (error: Exception) {
            throw IllegalStateException("Saved favorites could not be read for backup.", error)
        }
        val favorites = favoritePosts()
        if (favorites.size != count) {
            throw IllegalStateException("Some saved favorites could not be read for backup.")
        }
        return favorites
    }

    fun setFavoritePosts(posts: List<ImagePost>) {
        store.edit().putString("favorite_posts", favoritePostsJson(posts)).apply()
    }

    fun applyUserData(data: UserDataBackup, merge: Boolean): List<ImagePost> {
        val favorites = if (merge) {
            val combined = favoritePosts().toMutableList()
            val existingKeys = combined.mapTo(mutableSetOf()) { "${it.provider}:${it.id}" }
            data.favorites.forEach { post ->
                if (existingKeys.add("${post.provider}:${post.id}")) combined.add(post)
            }
            combined
        } else {
            data.favorites
        }
        val gelbooruCredentials = if (merge && hasCredentials(gelbooruUserId, gelbooruApiKey)) {
            gelbooruUserId to gelbooruApiKey
        } else data.gelbooruUserId to data.gelbooruApiKey
        val rule34Credentials = if (merge && hasCredentials(rule34UserId, rule34ApiKey)) {
            rule34UserId to rule34ApiKey
        } else data.rule34UserId to data.rule34ApiKey

        val editor = store.edit()
            .putString("favorite_posts", favoritePostsJson(favorites))
            .putString("gelbooru_user_id", gelbooruCredentials.first.trim())
            .putString("gelbooru_api_key", gelbooruCredentials.second.trim())
            .putString("rule34_user_id", rule34Credentials.first.trim())
            .putString("rule34_api_key", rule34Credentials.second.trim())
            .putString("provider", if (data.provider == "All") "Auto" else data.provider)
            .putBoolean("nsfw", data.allowNsfw)
            .putString("rating_filter", if (data.allowNsfw) data.rating else "sfw")
            .putBoolean("doh", data.useDoh)
            .putString("doh_provider", data.dohProvider)
            .putString("custom_doh_endpoint", data.customDohEndpoint.trim())
            .putBoolean("filter_gore", data.filterGore)
            .putBoolean("exclude_male", data.excludeMale)
            .putString("custom_block_tags", data.customBlockTags)
            .putString("media_filter", data.mediaFilter)
            .putInt("video_max_height", data.videoMaxHeight)
            .putBoolean("ambient_mode", data.ambientMode)
            .putString("custom_search_terms", JSONArray(data.customTerms).toString())
            .putInt("custom_search_index", 0)
        if (!editor.commit()) {
            throw IllegalStateException("Could not save imported user data.")
        }
        return favorites
    }

    private fun favoritePostsJson(posts: List<ImagePost>): String {
        val array = JSONArray()
        posts.forEach { post ->
            array.put(JSONObject().apply {
                put("id", post.id)
                put("dedupeKey", post.dedupeKey)
                put("provider", post.provider)
                put("imageUrl", post.imageUrl)
                put("thumbnailUrl", post.thumbnailUrl)
                put("thumbnailCandidates", JSONArray(post.thumbnailCandidates))
                put("extension", post.extension)
                put("rating", post.rating)
                put("tags", JSONArray(post.tags))
                put("source", post.source)
                put("artists", JSONArray(post.artists))
                put("mediaType", post.mediaType)
                put("title", post.title)
                put("width", post.width)
                put("height", post.height)
                put("videoVariants", JSONArray().apply {
                    post.videoVariants.forEach { variant ->
                        put(JSONObject().apply {
                            put("url", variant.url)
                            put("width", variant.width)
                            put("height", variant.height)
                        })
                    }
                })
            })
        }
        return array.toString()
    }

    private fun hasCredentials(userId: String, apiKey: String): Boolean =
        userId.isNotBlank() && apiKey.isNotBlank()

    private fun JSONArray?.toStringList(): List<String> = this?.let { array ->
        (0 until array.length()).mapNotNull { array.optString(it).takeIf(String::isNotBlank) }
    }.orEmpty()
}
