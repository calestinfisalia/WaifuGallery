package com.fisalia.waifugallery.data

import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.dnsoverhttps.DnsOverHttps
import org.json.JSONArray
import org.json.JSONObject
import java.net.InetAddress
import java.io.IOException
import java.io.StringReader
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
    private val rule34Credentials: () -> Pair<String, String> = { "" to "" },
    private val dohProvider: () -> String = { "Cloudflare" },
    private val customDohEndpoint: () -> String = { "" },
    private val filterGore: () -> Boolean = { true },
    private val excludeMale: () -> Boolean = { true },
    private val customBlockTags: () -> String = { "" },
    private val mediaFilter: () -> String = { "image" },
) {
    private data class Provider(val name: String, val endpoint: String, val yandere: Boolean = false)
    private data class ProviderSearchResult(
        val posts: List<ImagePost>,
        val totalCount: Int?,
        val hasMore: Boolean = false,
    )
    private data class CachedCount(val value: Int, val storedAt: Long)

    private val danbooru = Provider("Danbooru", "https://danbooru.donmai.us/posts.json")
    private val yandere = Provider("yande.re", "https://yande.re/post.json", true)
    private val gelbooru = Provider("Gelbooru", "https://gelbooru.com/index.php")
    private val rule34 = Provider("Rule34.xxx", "https://api.rule34.xxx/index.php")
    private val countCache = ConcurrentHashMap<String, CachedCount>()
    private val randomHistory = mutableMapOf<String, ArrayDeque<String>>()
    private val randomHistoryLock = Any()

    private val standardClient: OkHttpClient by lazy { baseClient(readSeconds = 30, callSeconds = 45).build() }
    private val standardImageClient: OkHttpClient by lazy { imageClientBuilder().build() }
    private val dohClients = ConcurrentHashMap<String, OkHttpClient>()
    private val dohClient: OkHttpClient get() = createDohClient("api", baseClient(30, 45).build())
    private val dohImageClient: OkHttpClient get() = createDohClient("image", imageClientBuilder().build())

    private fun dohUrl(): String = when (dohProvider()) {
        "Cloudflare Security" -> "https://security.cloudflare-dns.com/dns-query"
        "Cloudflare Family" -> "https://family.cloudflare-dns.com/dns-query"
        "Google Public DNS" -> "https://dns.google/dns-query"
        "AdGuard DNS" -> "https://dns.adguard-dns.com/dns-query"
        "Custom" -> customDohEndpoint().ifBlank { "https://cloudflare-dns.com/dns-query" }
        else -> "https://cloudflare-dns.com/dns-query"
    }

    private fun dohBootstrapAddresses(): Array<InetAddress> = when (dohProvider()) {
        "Google Public DNS" -> arrayOf(InetAddress.getByName("8.8.8.8"), InetAddress.getByName("8.8.4.4"))
        "AdGuard DNS" -> arrayOf(InetAddress.getByName("94.140.14.14"), InetAddress.getByName("94.140.15.15"))
        else -> arrayOf(InetAddress.getByName("1.1.1.1"), InetAddress.getByName("1.0.0.1"))
    }

    private fun createDohClient(kind: String, bootstrap: OkHttpClient): OkHttpClient {
        val endpoint = dohUrl()
        val key = "$kind|$endpoint"
        return dohClients.getOrPut(key) {
            val dns = DnsOverHttps.Builder()
                .client(bootstrap)
                .url(endpoint.toHttpUrl())
                .bootstrapDnsHosts(*dohBootstrapAddresses())
                .build()
            bootstrap.newBuilder().dns(dns).build()
        }
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
            if (request.header("Referer") == null && (host.contains("gelbooru") || host.contains("rule34"))) {
                val referer = if (host.contains("rule34")) "https://rule34.xxx/" else "https://gelbooru.com/"
                chain.proceed(request.newBuilder().header("Referer", referer).build())
            } else {
                chain.proceed(request)
            }
        }

    fun imageClient(): OkHttpClient = if (useDoh()) dohImageClient else standardImageClient
    private fun apiClient(): OkHttpClient = if (useDoh()) dohClient else standardClient

    suspend fun randomImage(nsfw: Boolean, searchTerm: String, selectedProvider: String): ImagePost =
        withContext(Dispatchers.IO) {
            val videoOnly = mediaFilter() == "video"
            val providers = when (selectedProvider) {
                "Danbooru" -> listOf(danbooru)
                "yande.re" -> if (videoOnly) emptyList() else listOf(yandere)
                "Gelbooru" -> listOf(gelbooru)
                "Rule34.xxx" -> listOf(rule34)
                else -> buildList {
                    if (!videoOnly) add(yandere)
                    if (hasGelbooruCredentials()) add(gelbooru)
                    if (hasRule34Credentials()) add(rule34)
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
            "Rule34.xxx" -> listOf(rule34)
            else -> buildList {
                add(yandere)
                if (hasGelbooruCredentials()) add(gelbooru)
                if (hasRule34Credentials()) add(rule34)
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
        val providerHasMore = results.any { (_, result) -> result.getOrNull()?.hasMore == true }
        SearchPage(
            posts = posts,
            totalPages = totalCount?.let { ((it + limit - 1) / limit).coerceAtLeast(1) },
            totalResults = totalCount,
            hasMore = totalCount?.let { page * limit < it } ?: (posts.size >= limit || providerHasMore),
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
        if (mediaFilter() == "video" && provider.yandere) {
            return ProviderSearchResult(emptyList(), 0)
        }
        val tagsQueries = searchTags(query).toMutableList()
        prefixFallback(query)?.let { if (it !in tagsQueries) tagsQueries += it }
        var knownTotal: Int? = null
        for (tags in tagsQueries) {
            val posts = mutableListOf<ImagePost>()
            var hasMore = false
            for (ratingTag in ratings(rating)) {
                val queryRating = ratingTag?.let { providerRatingTag(provider, it) }
                val requestTags = tags + listOfNotNull(
                    if (mediaFilter() == "video") "video" else null,
                    queryRating?.let { "rating:$it" },
                )
                val params = mutableMapOf(
                    "tags" to requestTags.joinToString(" "),
                    "limit" to minOf(limit + 1, 100).toString(),
                    "page" to page.toString(),
                )
                if (provider.yandere) params["api_version"] = "2"
                val result = requestPosts(provider, params)
                hasMore = hasMore || result.size > limit
                posts += result.take(limit).mapNotNull { parsePost(it, provider) }
            }
            val filtered = posts.filter {
                    ratingMatches(it, rating) && (!excludeMale() || acceptableGender(it)) &&
                    (rating != RatingFilter.SFW || safeForSfw(it)) && acceptedPost(it)
            }
            val count = countMatches(
                provider,
                tags + listOfNotNull(if (mediaFilter() == "video") "video" else null),
                rating,
            )
            if (count != null && knownTotal == null) knownTotal = count
            if (filtered.isNotEmpty()) return ProviderSearchResult(filtered.distinctBy { it.id }.take(limit), count, hasMore)
            if (count != null && count > 0) return ProviderSearchResult(emptyList(), count, hasMore)
        }
        return ProviderSearchResult(emptyList(), knownTotal ?: 0)
    }

    private fun countMatches(provider: Provider, tags: List<String>, rating: RatingFilter): Int? {
        if (provider.name == "Rule34.xxx") return null
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
            "Gelbooru", "Rule34.xxx" -> provider.endpoint
            else -> provider.endpoint.replace("/post.json", "/post.xml")
        }
        val urlBuilder = endpoint.toHttpUrl().newBuilder()
            .addQueryParameter("tags", tags)
            .addQueryParameter("limit", "1")
        if (provider.name == "Gelbooru" || provider.name == "Rule34.xxx") urlBuilder.addQueryParameter("json", "1")
        if (provider.name == "Gelbooru" || provider.name == "Rule34.xxx") {
            urlBuilder.addQueryParameter("page", "dapi")
                .addQueryParameter("s", "post")
                .addQueryParameter("q", "index")
        }
        addGelbooruCredentials(provider, urlBuilder)
        addRule34Credentials(provider, urlBuilder)
        val url = urlBuilder.build()
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "Waifu Gallery/0.1 (search count)")
            .header("Accept", if (provider.name == "Danbooru" || provider.name == "Gelbooru" || provider.name == "Rule34.xxx") "application/json" else "application/xml")
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
                val requestTags = tags + listOfNotNull(
                    if (mediaFilter() == "video") "video" else null,
                    "rating:${providerRatingTag(provider, rating)}",
                )
                val params = mutableMapOf("tags" to requestTags.joinToString(" "), "limit" to "100")
                if (provider.yandere) {
                    params["api_version"] = "2"
                    params["page"] = Random.nextInt(1, 121).toString()
                } else if (provider.name == "Danbooru") {
                    params["random"] = "1"
                } else if (provider.name == "Gelbooru" || provider.name == "Rule34.xxx") {
                    params["page"] = Random.nextInt(1, 121).toString()
                }
                var result = requestPosts(provider, params)
                if (result.isEmpty() && params["page"] != null && params["page"] != "1") {
                    params["page"] = "1"
                    result = requestPosts(provider, params)
                }
                posts += result
                    .mapNotNull { parsePost(it, provider) }
                    .filter { it.rating == rating && (rating != "s" || safeForSfw(it)) && acceptedPost(it) }
            }
            val filtered = if (excludeMale()) posts.filter(::acceptableGender) else posts
            if (filtered.isNotEmpty()) return filtered
        }
        return emptyList()
    }

    private fun requestPosts(provider: Provider, params: Map<String, String>): List<JSONObject> {
        val urlBuilder = provider.endpoint.toHttpUrl().newBuilder()
        params.forEach { (key, value) ->
            val apiKey = if (provider.name in setOf("Gelbooru", "Rule34.xxx") && key == "page") "pid" else key
            val apiValue = if (provider.name in setOf("Gelbooru", "Rule34.xxx") && key == "page") {
                (value.toIntOrNull()?.minus(1) ?: 0).coerceAtLeast(0).toString()
            } else value
            urlBuilder.addQueryParameter(apiKey, apiValue)
        }
        if (provider.name == "Gelbooru" || provider.name == "Rule34.xxx") {
            urlBuilder.addQueryParameter("json", "1")
                .addQueryParameter("page", "dapi")
                .addQueryParameter("s", "post")
                .addQueryParameter("q", "index")
        }
        addGelbooruCredentials(provider, urlBuilder)
        addRule34Credentials(provider, urlBuilder)
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
                    var body = response.body?.string().orEmpty()
                    if (provider.name == "Rule34.xxx" && body.isBlank()) {
                        // Some DAPI responses are empty in JSON mode. Retry the
                        // same query as the legacy XML response before failing.
                        val xmlRequest = request.newBuilder()
                            .url(request.url.newBuilder().removeAllQueryParameters("json").build())
                            .header("Accept", "application/xml")
                            .build()
                        apiClient().newCall(xmlRequest).execute().use { xmlResponse ->
                            if (xmlResponse.isSuccessful) body = xmlResponse.body?.string().orEmpty()
                        }
                    }
                    return parsePostsResponse(provider, body)
                }
            } catch (error: IOException) {
                lastError = error
                if (attempt == 2) throw error
                Thread.sleep((attempt + 1L) * 500L)
            }
        }
        throw lastError ?: IOException("Request failed")
    }

    private fun parsePostsResponse(provider: Provider, rawBody: String): List<JSONObject> {
        val body = rawBody.trim()
        if (body.isEmpty()) {
            if (provider.name == "Rule34.xxx") {
                throw IOException("Rule34.xxx returned an empty response. Sign out and sign in again with the user ID and API key from your account settings, then retry.")
            }
            throw IOException("${provider.name} returned an empty response")
        }

        if (provider.name == "Rule34.xxx") {
            val lower = body.lowercase()
            if (lower.contains("missing authentication") || lower.contains("invalid api key") || lower.contains("invalid user_id")) {
                throw IOException("Rule34.xxx rejected the credentials. Re-enter the user ID and API key from your account settings.")
            }
            if (body.startsWith("<")) return parseRule34Xml(body)
        }

        val payload = try {
            JSONArray(body)
        } catch (_: Exception) {
            try {
                JSONObject(body)
            } catch (error: Exception) {
                val hint = if (provider.name == "Rule34.xxx") {
                    "Rule34.xxx returned neither JSON nor DAPI XML. Verify the account credentials and retry later."
                } else {
                    "${provider.name} returned an unreadable response"
                }
                throw IOException(hint, error)
            }
        }

        val array = when (payload) {
            is JSONArray -> payload
            is JSONObject -> payload.optJSONArray("posts")
                ?: payload.optJSONArray("post")
                ?: payload.optJSONObject("post")?.let { JSONArray().put(it) }
                ?: JSONArray()
            else -> JSONArray()
        }
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
    }

    private fun parseRule34Xml(body: String): List<JSONObject> {
        try {
            val parser = Xml.newPullParser().apply {
                setInput(StringReader(body))
            }
            val posts = mutableListOf<JSONObject>()
            var foundRoot = false
            while (parser.next() != org.xmlpull.v1.XmlPullParser.END_DOCUMENT) {
                if (parser.eventType != org.xmlpull.v1.XmlPullParser.START_TAG) continue
                when (parser.name.lowercase()) {
                    "posts" -> {
                        foundRoot = true
                        val success = parser.getAttributeValue(null, "success")?.lowercase()
                        if (success == "false" || success == "0") {
                            throw IOException("Rule34.xxx search is temporarily unavailable. Retry later.")
                        }
                    }
                    "post" -> {
                        val item = JSONObject()
                        for (index in 0 until parser.attributeCount) {
                            item.put(parser.getAttributeName(index), parser.getAttributeValue(index))
                        }
                        posts += item
                    }
                }
            }
            if (!foundRoot) throw IOException("Rule34.xxx returned malformed DAPI XML")
            return posts
        } catch (error: IOException) {
            throw error
        } catch (error: Exception) {
            throw IOException("Rule34.xxx returned malformed DAPI XML", error)
        }
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

    private fun addRule34Credentials(provider: Provider, builder: okhttp3.HttpUrl.Builder) {
        if (provider.name != "Rule34.xxx") return
        val (userId, apiKey) = rule34Credentials()
        if (userId.isBlank() || apiKey.isBlank()) throw IOException("Rule34.xxx is locked. Add your user ID and API key in Preferences.")
        builder.addQueryParameter("user_id", userId).addQueryParameter("api_key", apiKey)
    }

    private fun hasGelbooruCredentials(): Boolean = gelbooruCredentials().let { (userId, apiKey) ->
        userId.isNotBlank() && apiKey.isNotBlank()
    }
    private fun hasRule34Credentials(): Boolean = rule34Credentials().let { (userId, apiKey) -> userId.isNotBlank() && apiKey.isNotBlank() }

    private fun parsePost(post: JSONObject, provider: Provider): ImagePost? {
        val fileUrl = firstNonEmpty(post, "file_url")
        val rawFile = fileUrl ?: firstNonEmpty(post, "source_url")
        val isVideo = post.optString("file_ext").lowercase() in VIDEO_EXTENSIONS ||
            rawFile?.substringBefore('?')?.substringAfterLast('.', "")?.lowercase() in VIDEO_EXTENSIONS
        val image = if (isVideo) {
            rawFile
        } else {
            fileUrl
                ?: gelbooruImageUrl(post)
                ?: rule34ImageUrl(post)
                ?: firstNonEmpty(post, "large_file_url", "jpeg_url", "sample_url", "source_url")
        } ?: return null
        val thumbnails = listOf("preview_file_url", "preview_url", "sample_url", "jpeg_url", "large_file_url")
            .mapNotNull { field -> post.optString(field).takeIf { it.isNotBlank() && it != "null" } }
            .filterNot { it.substringBefore('?').substringAfterLast('.', "").lowercase() in VIDEO_EXTENSIONS }
            .distinct()
            .ifEmpty { listOf(image) }
        val thumbnail = thumbnails.first()
        val id = "${provider.name.lowercase()}_${post.optString("id").ifBlank { post.optString("md5", image) }}"
        val dedupeKey = post.optString("md5").takeIf { it.isNotBlank() } ?: image
        val allTags = listOf("tag_string", "tag_string_general", "tag_string_character", "tag_string_copyright", "tag_string_artist", "tags")
            .flatMap { field -> parseTags(post.opt(field)) }
            .map { it.lowercase() }
            .toSet()
        val ext = (post.optString("file_ext").takeIf { it.isNotBlank() } ?: image.substringBefore('?').substringAfterLast('.', "jpg")).lowercase()
        val rating = normalizeRating(provider, post.optString("rating", "").lowercase())
        val width = post.optInt("width", 0).coerceAtLeast(0)
        val height = post.optInt("height", 0).coerceAtLeast(0)
        val variantDimensions = listOf(
            "file_url" to (width to height),
            "large_file_url" to (post.optInt("large_width", width).coerceAtLeast(0) to post.optInt("large_height", height).coerceAtLeast(0)),
            "sample_url" to (post.optInt("sample_width", 0).coerceAtLeast(0) to post.optInt("sample_height", 0).coerceAtLeast(0)),
            "jpeg_url" to (post.optInt("jpeg_width", 0).coerceAtLeast(0) to post.optInt("jpeg_height", 0).coerceAtLeast(0)),
        )
        val videoVariants = variantDimensions.mapNotNull { (field, dimensions) ->
            val variantUrl = post.optString(field).takeIf { it.isNotBlank() && it != "null" } ?: return@mapNotNull null
            val suffix = variantUrl.substringBefore('?').substringAfterLast('.', "").lowercase()
            if (suffix !in VIDEO_EXTENSIONS) return@mapNotNull null
            VideoVariant(variantUrl, dimensions.first, dimensions.second)
        }.distinctBy { it.url }.ifEmpty {
            if (isVideo) listOf(VideoVariant(image, width, height)) else emptyList()
        }
        return ImagePost(
            id = id,
            dedupeKey = dedupeKey,
            provider = provider.name,
            imageUrl = image,
            thumbnailUrl = thumbnail,
            thumbnailCandidates = thumbnails,
            extension = ext,
            rating = rating,
            tags = allTags,
            source = post.optString("source", ""),
            artists = post.optString("tag_string_artist", "").split(Regex("\\s+")).filter(String::isNotBlank),
            mediaType = if (isVideo) "video" else "image",
            title = post.optString("title", post.optString("name", "")),
            width = width,
            height = height,
            videoVariants = videoVariants,
        )
    }

    private fun gelbooruImageUrl(post: JSONObject): String? {
        val directory = post.optString("directory").takeIf(String::isNotBlank) ?: return null
        val filename = post.optString("image").takeIf(String::isNotBlank) ?: return null
        return "https://img3.gelbooru.com/images/$directory/$filename"
    }

    private fun rule34ImageUrl(post: JSONObject): String? {
        val directory = post.optString("directory").takeIf(String::isNotBlank) ?: return null
        val filename = post.optString("image").takeIf(String::isNotBlank) ?: return null
        return "https://img.rule34.xxx/images/$directory/$filename"
    }

    private fun normalizeRating(provider: Provider, rating: String): String =
        if (provider.name != "Gelbooru" && provider.name != "Rule34.xxx") rating else when (rating) {
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
        if (provider.name != "Gelbooru" && provider.name != "Rule34.xxx") rating else when (rating) {
            "s" -> if (provider.name == "Rule34.xxx") "safe" else "general"
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

    private fun acceptedPost(post: ImagePost): Boolean {
        val custom = customBlockTags().split(Regex("[,\\s]+")).filter(String::isNotBlank).map { it.lowercase().replace(' ', '_') }.toSet()
        val blocked = post.tags.any { it in custom }
        return !blocked && (!filterGore() || post.tags.none { it in GORE_BLOCK_TAGS }) &&
            (mediaFilter() == "all" || post.mediaType == mediaFilter())
    }

    private fun acceptableGender(post: ImagePost): Boolean {
        val boys = setOf("1boy", "2boys", "3boys", "4boys", "5boys", "6+boys", "male_focus", "male_only")
        // Many yande.re posts omit gender tags; keep those instead of discarding valid results.
        return post.tags.none { it in boys }
    }

    private companion object {
        val VIDEO_EXTENSIONS = setOf("mp4", "m4v", "webm", "mov", "mkv", "avi")
        val GORE_BLOCK_TAGS = setOf("amputation", "blood", "blood_splatter", "body_horror", "decapitation", "dismemberment", "disembowelment", "exposed_organs", "gore", "guro", "intestines", "mutilation", "open_wound", "severed_head", "wound")
        val SFW_BLOCK_TAGS = setOf(
            "anal", "blowjob", "cum", "cum_in_pussy", "cum_on_body", "cum_on_face",
            "cumshot", "ejaculation", "explicit", "fellatio", "genital", "hentai",
            "intercourse", "masturbation", "naked", "nipple", "nipples", "nudity",
            "nude", "oral", "penis", "pussy", "sex", "sex_toy", "uncensored",
            "vagina", "vaginal", "vaginal_penetration",
        )
    }

    private fun searchTags(query: String): List<List<String>> {
        val tags = mutableListOf<String>()
        for (chunk in query.split(",")) {
            var value = chunk.trim()
            if (value.isBlank()) continue
            if (' ' in value && '_' !in value) value = value.replace(' ', '_')
            val chunkTags = value.split(Regex("\\s+")).toMutableList()
            if (chunkTags.size == 1) {
                val tag = chunkTags[0]
                if (tag.isNotEmpty() && tag.none { it in "*~()" } && ':' !in tag && !tag.startsWith("-")) {
                    chunkTags[0] = "$tag*"
                }
            }
            tags += chunkTags
        }
        return if (tags.isEmpty()) emptyList() else listOf(tags)
    }

    private fun prefixFallback(query: String): List<String>? {
        val value = query.trim().substringBefore(",").trim()
        if (value.isBlank() || '_' in value || value.any { it in "*~():" }) return null
        val firstChunk = value.split(Regex("\\s+"))
        if (firstChunk.size != 1) return null
        val first = firstChunk[0].lowercase()
        return if (first.length >= 3) listOf("$first*") else null
    }
}
