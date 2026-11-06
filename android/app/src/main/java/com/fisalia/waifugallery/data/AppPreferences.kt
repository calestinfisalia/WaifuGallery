package com.fisalia.waifugallery.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

class AppPreferences(context: Context) {
    private val store = context.getSharedPreferences("waifu_gallery", Context.MODE_PRIVATE)

    var allowNsfw: Boolean
        get() = store.getBoolean("nsfw", false)
        set(value) = store.edit().putBoolean("nsfw", value).apply()

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
                )
            }.getOrNull()
        }
    } catch (_: Exception) {
        emptyList()
    }

    fun setFavoritePosts(posts: List<ImagePost>) {
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
            })
        }
        store.edit().putString("favorite_posts", array.toString()).apply()
    }

    private fun JSONArray?.toStringList(): List<String> = this?.let { array ->
        (0 until array.length()).mapNotNull { array.optString(it).takeIf(String::isNotBlank) }
    }.orEmpty()
}
