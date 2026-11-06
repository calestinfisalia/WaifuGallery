package com.fisalia.waifugallery.data

import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.dnsoverhttps.DnsOverHttps
import org.json.JSONArray
import org.json.JSONObject
import java.net.InetAddress
import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.ConcurrentHashMap
import kotlin.random.Random
import android.util.Xml
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext

class BooruApi(
    private val useDoh: () -> Boolean,
    private val gelbooruCredentials: () -> Pair<String, String>,
) {
    private data class Provider(val name: String, val endpoint: String, val yandere: Boolean)
    private data class ProviderSearchResult(val posts: List<ImagePost>, val totalCount: Int?)
    private data class CachedCount(val value: Int, val storedAt: Long)

    private val danbooru = Provider("Danbooru", "https://danbooru.donmai.us/posts.json", false)
    private val yandere = Provider("yande.re", "https://yande.re/post.json", true)
    private val gelbooru = Provider("Gelbooru", "https://gelbooru.com/index.php", false)
    private val countCache = ConcurrentHashMap<String, CachedCount>()
    private val randomHistory = mutableMapOf<String, ArrayDeque<String>>()
    private val randomHistoryLock = Any()

    private val standardClient: OkHttpClient by lazy { baseClient(readSeconds = 30, callSeconds = 45).build() }
    private val standardImageClient: OkHttpClient by lazy { imageClientBuilder().build() }
    private val dohClient: OkHttpClient by lazy {
        val bootstrap = baseClient(readSeconds = 30, callSeconds = 45).build()
        val cloudflareDns = DnsOverHttps.Builder()
            .client(bootstrap)
            .url("https://cloudflare-dns.com/dns-query".toHttpUrl())
            .bootstrapDnsHosts(InetAddress.getByName("1.1.1.1"), InetAddress.getByName("1.0.0.1"))
            .build()
        bootstrap.newBuilder().dns(cloudflareDns).build()
    }

    private val dohImageClient: OkHttpClient by lazy {
        val bootstrap = imageClientBuilder().build()
        val cloudflareDns = DnsOverHttps.Builder()
            .client(bootstrap)
            .url("https://cloudflare-dns.com/dns-query".toHttpUrl())
            .bootstrapDnsHosts(InetAddress.getByName("1.1.1.1"), InetAddress.getByName("1.0.0.1"))
            .build()
        bootstrap.newBuilder().dns(cloudflareDns).build()
    }

    private fun baseClient(readSeconds: Long, callSeconds: Long): OkHttpClient.Builder = OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(readSeconds, TimeUnit.SECONDS)
            .callTimeout(callSeconds, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)

    private fun imageClientBuilder(): OkHttpClient.Builder = baseClient(readSeconds = 60, callSeconds = 120)
        .addInterceptor { chain ->
            val request = chain.request()
            val host = request.url.host.lowercase()
            if ((host == "gelbooru.com" || host.endsWith(".gelbooru.com")) && request.header("Referer") == null) {
                chain.proceed(request.newBuilder().header("Referer", "https://gelbooru.com/").build())
            } else {
                chain.proceed(request)
            }
        }

    fun imageClient(): OkHttpClient = if (useDoh()) dohImageClient else standardImageClient
    private fun apiClient(): OkHttpClient = if (useDoh()) dohClient else standardClient

    suspend fun randomImage(nsfw: Boolean, searchTerm: String, selectedProvider: String): ImagePost =
        withContext(Dispatchers.IO) {
            val providers = when (selectedProvider) {
                "Danbooru" -> listOf(danbooru)
                "yande.re" -> listOf(yandere)
                "Gelbooru" -> listOf(gelbooru)
                else -> buildList {
                    add(yandere)
                    if (hasGelbooruCredentials()) add(gelbooru)
                    add(danbooru)
                }
            }
            val errors = mutableListOf<String>()
            for (provider in providers) {
                try {
                    val candidates = randomCandidates(provider, nsfw, searchTerm)
                    if (candidates.isNotEmpty()) return@withContext chooseNonRecent(provider, nsfw, searchTerm, candidates)
                } catch (error: Exception) {
                    errors += "${provider.name}: ${error.message ?: "Request failed"}"
                }
            }
            if (errors.isNotEmpty()) throw IllegalStateException("All providers failed: ${errors.joinToString(" | ")}")
            throw IllegalStateException("The providers returned no matching images.")
        }

    private fun chooseNonRecent(provider: Provider, nsfw: Boolean, query: String, candidates: List<ImagePost>): ImagePost =
        synchronized(randomHistoryLock) {
            val key = "${provider.name}|${if (nsfw) "explicit" else "safe"}|${query.trim().lowercase()}"
            val recent = randomHistory.getOrPut(key) { ArrayDeque() }
            val fresh = candidates.filterNot { it.id in recent }
            val pool = if (fresh.isNotEmpty()) fresh else candidates.also { recent.clear() }
            val chosen = pool.random()
            recent.addLast(chosen.id)
            while (recent.size > 160) recent.removeFirst()
            chosen
        }

    suspend fun search(
        query: String,
        rating: RatingFilter,
        providerName: String,
        page: Int,
        limit: Int = 50,
    ): SearchPage = coroutineScope {
        val providers = when (providerName) {
            "Danbooru" -> listOf(danbooru)
            "yande.re" -> listOf(yandere)
            "Gelbooru" -> listOf(gelbooru)
            else -> buildList {
                add(yandere)
                if (hasGelbooruCredentials()) add(gelbooru)
                add(danbooru)
            }
        }
        val results = providers.map { provider ->
            async(Dispatchers.IO) {
                val result: Result<ProviderSearchResult> = try {
                    Result.success(searchProvider(provider, query, rating, page, limit))
                } catch (error: Exception) {
                    Result.failure(error)
                }
                provider.name to result
            }
        }.awaitAll()

        val successes = results.mapNotNull { (name, result) ->
            result.getOrNull()?.let { name to it.posts }
        }.toMap()
        val totalCount = results.mapNotNull { (_, result) -> result.getOrNull()?.totalCount }.takeIf { it.size == providers.size }?.sum()
        val errors = results.mapNotNull { (name, result) ->
            result.exceptionOrNull()?.let { "$name: ${it.message ?: "Request failed"}" }
        }
        if (successes.values.all { it.isEmpty() } && errors.size == providers.size) {
            throw IllegalStateException("All providers failed: ${errors.joinToString(" | ")}")
        }

        val posts = if (providerName == "All") {
            val merged = mutableListOf<ImagePost>()
            val seen = mutableSetOf<String>()
            val lists = providers.map { successes[it.name].orEmpty() }
            for (index in 0 until (lists.maxOfOrNull { it.size } ?: 0)) {
                for (list in lists) {
                    list.getOrNull(index)?.let { post ->
                        if (seen.add(post.dedupeKey)) merged += post
                        if (merged.size == limit) break
                    }
                }
                if (merged.size == limit) break
            }
            merged
        } else successes[providerName].orEmpty().take(limit)
        SearchPage(
            posts = posts,
            totalPages = totalCount?.let { ((it + limit - 1) / limit).coerceAtLeast(1) },
            totalResults = totalCount,
            hasMore = totalCount?.let { page * limit < it } ?: (posts.size >= limit || successes.values.any { it.size >= limit }),
            providerErrors = errors,
        )
    }

    private suspend fun searchProvider(
        provider: Provider,
        query: String,
        rating: RatingFilter,
        page: Int,
        limit: Int,
    ): ProviderSearchResult {
        val tagsQueries = searchTags(query).toMutableList()
        prefixFallback(query)?.let { if (it !in tagsQueries) tagsQueries += it }
        var knownTotal: Int? = null
        for (tags in tagsQueries) {
            val posts = mutableListOf<ImagePost>()
            for (ratingTag in ratings(rating)) {
                val queryRating = ratingTag?.let { providerRatingTag(provider, it) }
                val params = mutableMapOf("tags" to (tags + listOfNotNull(queryRating?.let { "rating:$it" })).joinToString(" "), "limit" to minOf(limit, 100).toString(), "page" to page.toString())
                if (provider.yandere) params["api_version"] = "2"
                val result = requestPosts(provider, params)
                posts += result.mapNotNull { parsePost(it, provider) }
            }
            val filtered = posts.filter {
                ratingMatches(it, rating) && acceptableGender(it) &&
                    (rating != RatingFilter.SFW || safeForSfw(it))
            }
            val count = countMatches(provider, tags, rating)
            if (count != null && knownTotal == null) knownTotal = count
            if (filtered.isNotEmpty()) return ProviderSearchResult(filtered.distinctBy { it.id }.take(limit), count)
            if (count != null && count > 0) return ProviderSearchResult(emptyList(), count)
        }
        return ProviderSearchResult(emptyList(), knownTotal ?: 0)
    }

    private fun countMatches(provider: Provider, tags: List<String>, rating: RatingFilter): Int? {
        val perRatingCounts = ratings(rating).map { ratingTag ->
            val queryTags = tags + listOfNotNull(ratingTag?.let { "rating:${providerRatingTag(provider, it)}" })
            runCatching { requestCount(provider, queryTags.joinToString(" ")) }.getOrNull() ?: return null
        }
        return perRatingCounts.sum()
    }

    private fun requestCount(provider: Provider, tags: String): Int {
        val cacheKey = "${provider.endpoint}|$tags"
        countCache[cacheKey]?.let { cached ->
            if (System.currentTimeMillis() - cached.storedAt < 60_000) return cached.value
        }
        val endpoint = when (provider.name) {
            "Danbooru" -> provider.endpoint.replace("/posts.json", "/counts/posts.json")
            "Gelbooru" -> provider.endpoint
            else -> provider.endpoint.replace("/post.json", "/post.xml")
        }
        val urlBuilder = endpoint.toHttpUrl().newBuilder()
            .addQueryParameter("tags", tags)
            .addQueryParameter("limit", "1")
        if (provider.name == "Gelbooru") urlBuilder.addQueryParameter("json", "1")
        if (provider.name == "Gelbooru") {
            urlBuilder.addQueryParameter("page", "dapi")
                .addQueryParameter("s", "post")
                .addQueryParameter("q", "index")
        }
        addGelbooruCredentials(provider, urlBuilder)
        val url = urlBuilder.build()
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "Waifu Gallery/0.1 (search count)")
            .header("Accept", if (provider.name == "Danbooru" || provider.name == "Gelbooru") "application/json" else "application/xml")
            .build()
        apiClient().newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("HTTP ${response.code}")
            val body = response.body ?: throw IOException("Empty count response")
            if (provider.name == "Danbooru") {
                val json = JSONObject(body.string())
                val count = json.optJSONObject("counts")?.optInt("posts", -1)
                    ?.takeIf { it >= 0 } ?: throw IOException("Missing post count")
                countCache[cacheKey] = CachedCount(count, System.currentTimeMillis())
                return count
            }
            if (provider.name == "Gelbooru") {
                val attributes = JSONObject(body.string()).optJSONObject("@attributes")
                    ?: throw IOException("Gelbooru returned no post count")
                val count = attributes.optString("count").toIntOrNull()
                    ?: throw IOException("Gelbooru returned an invalid post count")
                countCache[cacheKey] = CachedCount(count, System.currentTimeMillis())
                return count
            }
            val parser = Xml.newPullParser()
            body.byteStream().use { input ->
                parser.setInput(input, null)
                while (parser.next() != org.xmlpull.v1.XmlPullParser.END_DOCUMENT) {
                    if (parser.eventType == org.xmlpull.v1.XmlPullParser.START_TAG && parser.name == "posts") {
                        val count = parser.getAttributeValue(null, "count")?.toIntOrNull()
                            ?: throw IOException("Missing post count")
                        countCache[cacheKey] = CachedCount(count, System.currentTimeMillis())
                        return count
                    }
                }
            }
            throw IOException("Missing post count")
        }
    }

    private suspend fun randomCandidates(provider: Provider, nsfw: Boolean, query: String): List<ImagePost> {
        val candidateQueries = searchTags(query).toMutableList()
        if (candidateQueries.isEmpty()) candidateQueries.add(emptyList())
        prefixFallback(query)?.let { if (it !in candidateQueries) candidateQueries += it }
        for (tags in candidateQueries) {
            val posts = mutableListOf<ImagePost>()
            val wantedRatings = if (nsfw) listOf("e") else listOf("s")
            for (rating in wantedRatings) {
                val params = mutableMapOf("tags" to (tags + "rating:${providerRatingTag(provider, rating)}").joinToString(" "), "limit" to "100")
                if (provider.yandere) {
                    params["api_version"] = "2"
                    params["page"] = Random.nextInt(1, 121).toString()
                } else if (provider.name == "Danbooru") {
                    params["random"] = "1"
                } else if (provider.name == "Gelbooru") {
                    params["page"] = Random.nextInt(1, 121).toString()
                }
                var result = requestPosts(provider, params)
                if (result.isEmpty() && params["page"] != null && params["page"] != "1") {
                    params["page"] = "1"
                    result = requestPosts(provider, params)
                }
                posts += result
                    .mapNotNull { parsePost(it, provider) }
                    .filter { it.rating == rating && (rating != "s" || safeForSfw(it)) }
            }
            val filtered = posts.filter(::acceptableGender)
            if (filtered.isNotEmpty()) return filtered
        }
        return emptyList()
    }

    private fun requestPosts(provider: Provider, params: Map<String, String>): List<JSONObject> {
        val urlBuilder = provider.endpoint.toHttpUrl().newBuilder()
        params.forEach { (key, value) ->
            val apiKey = if (provider.name == "Gelbooru" && key == "page") "pid" else key
            val apiValue = if (provider.name == "Gelbooru" && key == "page") {
                (value.toIntOrNull()?.minus(1) ?: 0).coerceAtLeast(0).toString()
            } else value
            urlBuilder.addQueryParameter(apiKey, apiValue)
        }
        if (provider.name == "Gelbooru") {
            urlBuilder.addQueryParameter("json", "1")
                .addQueryParameter("page", "dapi")
                .addQueryParameter("s", "post")
                .addQueryParameter("q", "index")
        }
        addGelbooruCredentials(provider, urlBuilder)
        val requestBuilder = Request.Builder()
            .url(urlBuilder.build())
            .header("User-Agent", "Waifu Gallery/0.1 (image viewer)")
            .header("Accept", "application/json")
        if (provider.name == "Danbooru") requestBuilder.header("Accept-Version", "v7")
        val request = requestBuilder.build()
        var lastError: Exception? = null
        repeat(3) { attempt ->
            try {
                apiClient().newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        val retryable = response.code == 408 || response.code == 429 || response.code >= 500
                        if (!retryable || attempt == 2) throw IOException("HTTP ${response.code}")
                        lastError = IOException("HTTP ${response.code}")
                        val retryAfter = response.header("Retry-After")?.toLongOrNull()?.coerceIn(1, 3)
                        Thread.sleep((retryAfter ?: (attempt + 1L)) * 500L)
                        return@repeat
                    }
                    val body = response.body?.string().orEmpty()
                    val array = try {
                        JSONArray(body)
                    } catch (_: Exception) {
                        val wrapped = JSONObject(body)
                        wrapped.optJSONArray("posts")
                            ?: wrapped.optJSONArray("post")
                            ?: wrapped.optJSONObject("post")?.let { JSONArray().put(it) }
                            ?: JSONArray()
                    }
                    return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
                }
            } catch (error: IOException) {
                lastError = error
                if (attempt == 2) throw error
                Thread.sleep((attempt + 1L) * 500L)
            }
        }
        throw lastError ?: IOException("Request failed")
    }

    private fun addGelbooruCredentials(provider: Provider, builder: okhttp3.HttpUrl.Builder) {
        if (provider.name != "Gelbooru") return
        val (userId, apiKey) = gelbooruCredentials()
        if (userId.isBlank() || apiKey.isBlank()) {
            throw IOException("Gelbooru is locked. Add your Gelbooru user ID and API key in Preferences.")
        }
        builder.addQueryParameter("user_id", userId)
            .addQueryParameter("api_key", apiKey)
    }

    private fun hasGelbooruCredentials(): Boolean = gelbooruCredentials().let { (userId, apiKey) ->
        userId.isNotBlank() && apiKey.isNotBlank()
    }

    private fun parsePost(post: JSONObject, provider: Provider): ImagePost? {
        val image = firstNonEmpty(post, "jpeg_url", "large_file_url", "sample_url", "file_url")
            ?: gelbooruImageUrl(post)
            ?: return null
        val thumbnails = listOf("preview_file_url", "preview_url", "sample_url", "jpeg_url", "large_file_url", "file_url")
            .mapNotNull { field -> post.optString(field).takeIf { it.isNotBlank() && it != "null" } }
            .distinct()
            .ifEmpty { listOf(image) }
        val thumbnail = thumbnails.first()
        val id = "${provider.name.lowercase()}_${post.optString("id").ifBlank { post.optString("md5", image) }}"
        val dedupeKey = post.optString("md5").takeIf { it.isNotBlank() } ?: image
        val allTags = listOf("tag_string", "tag_string_general", "tag_string_character", "tag_string_copyright", "tag_string_artist", "tags")
            .flatMap { field -> parseTags(post.opt(field)) }
            .map { it.lowercase() }
            .toSet()
        val ext = image.substringBefore('?').substringAfterLast('.', "jpg").lowercase()
        return ImagePost(
            id = id,
            dedupeKey = dedupeKey,
            provider = provider.name,
            imageUrl = image,
            thumbnailUrl = thumbnail,
            thumbnailCandidates = thumbnails,
            extension = ext,
            rating = normalizeRating(provider, post.optString("rating", "").lowercase()),
            tags = allTags,
            source = post.optString("source", ""),
            artists = post.optString("tag_string_artist", "").split(Regex("\\s+")).filter(String::isNotBlank),
        )
    }

    private fun gelbooruImageUrl(post: JSONObject): String? {
        val directory = post.optString("directory").takeIf(String::isNotBlank) ?: return null
        val filename = post.optString("image").takeIf(String::isNotBlank) ?: return null
        return "https://img3.gelbooru.com/images/$directory/$filename"
    }

    private fun normalizeRating(provider: Provider, rating: String): String =
        if (provider.name != "Gelbooru") rating else when (rating) {
            "general", "safe" -> "s"
            "sensitive", "questionable" -> "q"
            "explicit" -> "e"
            else -> rating
        }

    private fun parseTags(value: Any?): List<String> = when (value) {
        is String -> value.split(Regex("\\s+")).filter(String::isNotBlank)
        is JSONArray -> (0 until value.length()).mapNotNull { value.optString(it).takeIf(String::isNotBlank) }
        is JSONObject -> value.keys().asSequence().toList()
        else -> emptyList()
    }

    private fun firstNonEmpty(post: JSONObject, vararg fields: String): String? =
        fields.firstNotNullOfOrNull { field -> post.optString(field).takeIf { it.isNotBlank() && it != "null" } }

    private fun ratings(filter: RatingFilter): List<String?> = when (filter) {
        RatingFilter.ALL -> listOf(null)
        RatingFilter.SFW -> listOf("s")
        RatingFilter.NSFW -> listOf("e")
    }

    private fun providerRatingTag(provider: Provider, rating: String): String =
        if (provider.name != "Gelbooru") rating else when (rating) {
            "s" -> "general"
            "q" -> "questionable"
            "e" -> "explicit"
            else -> rating
        }

    private fun ratingMatches(post: ImagePost, filter: RatingFilter): Boolean = when (filter) {
        RatingFilter.ALL -> true
        RatingFilter.SFW -> post.rating == "s"
        RatingFilter.NSFW -> post.rating == "e"
    }

    private fun safeForSfw(post: ImagePost): Boolean = post.tags.none { it in SFW_BLOCK_TAGS }

    private fun acceptableGender(post: ImagePost): Boolean {
        val boys = setOf("1boy", "2boys", "3boys", "4boys", "5boys", "6+boys", "male_focus", "male_only")
        // Many yande.re posts omit gender tags; keep those instead of discarding valid results.
        return post.tags.none { it in boys }
    }

    private companion object {
        val SFW_BLOCK_TAGS = setOf(
            "anal", "blowjob", "cum", "cum_in_pussy", "cum_on_body", "cum_on_face",
            "cumshot", "ejaculation", "explicit", "fellatio", "genital", "hentai",
            "intercourse", "masturbation", "naked", "nipple", "nipples", "nudity",
            "nude", "oral", "penis", "pussy", "sex", "sex_toy", "uncensored",
            "vagina", "vaginal", "vaginal_penetration",
        )
    }

    private fun searchTags(query: String): List<List<String>> {
        val normalized = query.trim().let { if (' ' in it && '_' !in it) it.replace(' ', '_') else it }
        if (normalized.isBlank()) return emptyList()
        val tokens = normalized.split(Regex("\\s+")).toMutableList()
        if (tokens.size == 1) {
            val tag = tokens[0]
            if (tag.none { it in "*~()" } && ':' !in tag && !tag.startsWith('-')) tokens[0] = "$tag*"
        }
        return listOf(tokens)
    }

    private fun prefixFallback(query: String): List<String>? {
        val normalized = query.trim()
        if (normalized.isBlank() || '_' in normalized || normalized.any { it in "*~():" }) return null
        val first = normalized.substringBefore(' ').lowercase()
        return if (first.length >= 3) listOf("$first*") else null
    }
}
