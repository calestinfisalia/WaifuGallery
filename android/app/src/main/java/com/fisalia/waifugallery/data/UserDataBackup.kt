package com.fisalia.waifugallery.data

import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import java.net.URI
import java.security.GeneralSecurityException
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

data class UserDataBackup(
    val favorites: List<ImagePost>,
    val gelbooruUserId: String,
    val gelbooruApiKey: String,
    val rule34UserId: String,
    val rule34ApiKey: String,
    val provider: String,
    val rating: String,
    val allowNsfw: Boolean,
    val customTerms: List<String>,
    val excludeMale: Boolean,
    val filterGore: Boolean,
    val customBlockTags: String,
    val mediaFilter: String,
    val useDoh: Boolean,
    val dohProvider: String,
    val customDohEndpoint: String,
    val ambientMode: Boolean,
    val videoMaxHeight: Int,
)

object UserDataBackupCodec {
    private const val SCHEMA = "waifu-gallery-user-data"
    private const val VERSION = 1
    private const val ITERATIONS = 600_000
    private const val MAX_BACKUP_BYTES = 32 * 1024 * 1024
    private val aad = "waifu-gallery-backup:v1".toByteArray(StandardCharsets.UTF_8)
    private val random = SecureRandom()

    fun create(
        favorites: List<ImagePost>,
        gelbooruUserId: String,
        gelbooruApiKey: String,
        rule34UserId: String,
        rule34ApiKey: String,
        provider: String,
        rating: String,
        allowNsfw: Boolean,
        customTerms: List<String>,
        excludeMale: Boolean,
        filterGore: Boolean,
        customBlockTags: String,
        mediaFilter: String,
        useDoh: Boolean,
        dohProvider: String,
        customDohEndpoint: String,
        ambientMode: Boolean,
        videoMaxHeight: Int,
    ): UserDataBackup = UserDataBackup(
        favorites = favorites,
        gelbooruUserId = gelbooruUserId,
        gelbooruApiKey = gelbooruApiKey,
        rule34UserId = rule34UserId,
        rule34ApiKey = rule34ApiKey,
        provider = provider,
        rating = rating,
        allowNsfw = allowNsfw,
        customTerms = customTerms,
        excludeMale = excludeMale,
        filterGore = filterGore,
        customBlockTags = customBlockTags,
        mediaFilter = mediaFilter,
        useDoh = useDoh,
        dohProvider = dohProvider,
        customDohEndpoint = customDohEndpoint,
        ambientMode = ambientMode,
        videoMaxHeight = videoMaxHeight,
    ).also(::validate)

    fun encrypt(data: UserDataBackup, passphrase: String): String {
        validatePassphrase(passphrase)
        validate(data)
        val salt = ByteArray(16).also(random::nextBytes)
        val nonce = ByteArray(12).also(random::nextBytes)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, deriveKey(passphrase, salt), GCMParameterSpec(128, nonce))
        cipher.updateAAD(aad)
        val encrypted = cipher.doFinal(payloadJson(data).toByteArray(StandardCharsets.UTF_8))
        val envelope = JSONObject().apply {
            put("format", SCHEMA)
            put("version", VERSION)
            put("kdf", "PBKDF2-HMAC-SHA256")
            put("iterations", ITERATIONS)
            put("cipher", "AES-256-GCM")
            put("salt", Base64.encodeToString(salt, Base64.NO_WRAP))
            put("nonce", Base64.encodeToString(nonce, Base64.NO_WRAP))
            put("ciphertext", Base64.encodeToString(encrypted, Base64.NO_WRAP))
        }.toString()
        require(envelope.toByteArray(StandardCharsets.UTF_8).size <= MAX_BACKUP_BYTES) {
            "The user data is too large to fit in a backup file."
        }
        return envelope
    }

    fun decrypt(contents: String, passphrase: String): UserDataBackup {
        validatePassphrase(passphrase)
        require(contents.toByteArray(StandardCharsets.UTF_8).size <= MAX_BACKUP_BYTES) {
            "The backup file is too large or invalid."
        }
        val envelope = try {
            JSONObject(contents)
        } catch (error: Exception) {
            throw IllegalArgumentException("The selected file is not a valid backup.", error)
        }
        require(
            envelope.requiredString("format") == SCHEMA &&
                envelope.requiredInt("version") == VERSION &&
                envelope.requiredString("kdf") == "PBKDF2-HMAC-SHA256" &&
                envelope.requiredInt("iterations") == ITERATIONS &&
                envelope.requiredString("cipher") == "AES-256-GCM"
        ) { "This backup format or encryption configuration is unsupported." }
        try {
            val salt = Base64.decode(envelope.requiredString("salt"), Base64.DEFAULT)
            val nonce = Base64.decode(envelope.requiredString("nonce"), Base64.DEFAULT)
            val encrypted = Base64.decode(envelope.requiredString("ciphertext"), Base64.DEFAULT)
            require(salt.size == 16 && nonce.size == 12 && encrypted.isNotEmpty()) {
                "The backup file is incomplete."
            }
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, deriveKey(passphrase, salt), GCMParameterSpec(128, nonce))
            cipher.updateAAD(aad)
            val plaintext = cipher.doFinal(encrypted).toString(StandardCharsets.UTF_8)
            return parsePayload(JSONObject(plaintext)).also(::validate)
        } catch (error: IllegalArgumentException) {
            throw error
        } catch (error: Exception) {
            if (error is GeneralSecurityException) {
                throw IllegalArgumentException(
                    "The passphrase is incorrect or the backup file is damaged.",
                    error,
                )
            }
            throw IllegalArgumentException("The backup file is incomplete or invalid.", error)
        }
    }

    private fun deriveKey(passphrase: String, salt: ByteArray): SecretKeySpec {
        val spec = PBEKeySpec(passphrase.toCharArray(), salt, ITERATIONS, 256)
        return try {
            val bytes = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
                .generateSecret(spec)
                .encoded
            SecretKeySpec(bytes, "AES")
        } finally {
            spec.clearPassword()
        }
    }

    private fun payloadJson(data: UserDataBackup): String = JSONObject().apply {
        put("schema", SCHEMA)
        put("version", VERSION)
        put("favorites", JSONArray().apply { data.favorites.forEach { put(favoriteJson(it)) } })
        put("providers", JSONObject().apply {
            put("gelbooru", credentialJson(data.gelbooruUserId, data.gelbooruApiKey))
            put("rule34", credentialJson(data.rule34UserId, data.rule34ApiKey))
        })
        put("settings", JSONObject().apply {
            put("provider", if (data.provider == "Auto") "All" else data.provider)
            put("rating", data.rating)
            put("allow_nsfw", data.allowNsfw)
            put("custom_terms", JSONArray(data.customTerms))
            put("exclude_male", data.excludeMale)
            put("filter_gore", data.filterGore)
            put("custom_block_tags", JSONArray(data.customBlockTags.replace(",", " ").split(Regex("\\s+")).filter(String::isNotBlank)))
            put("media_filter", data.mediaFilter)
            put("use_doh", data.useDoh)
            put("doh_provider", data.dohProvider)
            put("doh_custom_endpoint", data.customDohEndpoint)
            put("ambient_mode", data.ambientMode)
            put("video_max_height", data.videoMaxHeight)
        })
    }.toString()

    private fun favoriteJson(post: ImagePost): JSONObject = JSONObject().apply {
        put("post_id", post.id)
        put("provider", post.provider)
        put("image_url", post.imageUrl)
        put("preview_urls", JSONArray(post.thumbnailCandidates.ifEmpty { listOf(post.thumbnailUrl) }))
        put("rating", post.rating)
        put("tags", JSONArray(post.tags.sorted()))
        put("artists", JSONArray(post.artists))
        put("source", post.source)
        put("checksum", "")
        put("title", post.title)
        put("media_type", post.mediaType)
        put("width", post.width)
        put("height", post.height)
        put("video_variants", JSONArray().apply {
            post.videoVariants.forEach { variant ->
                put(JSONArray().put(variant.url).put(variant.width).put(variant.height))
            }
        })
        put("thumbnail_url", post.thumbnailUrl)
        put("extension", post.extension)
        put("dedupe_key", post.dedupeKey)
    }

    private fun credentialJson(userId: String, apiKey: String) = JSONObject().apply {
        put("user_id", userId.trim())
        put("api_key", apiKey.trim())
    }

    private fun parsePayload(payload: JSONObject): UserDataBackup {
        require(payload.requiredString("schema") == SCHEMA && payload.requiredInt("version") == VERSION) {
            "This backup format is unsupported."
        }
        val providers = payload.getJSONObject("providers")
        val gelbooru = providers.getJSONObject("gelbooru")
        val rule34 = providers.getJSONObject("rule34")
        val settings = payload.getJSONObject("settings")
        val favoritesJson = payload.getJSONArray("favorites")
        val favorites = (0 until favoritesJson.length()).map { index ->
            val item = favoritesJson.getJSONObject(index)
            val previewUrls = item.stringList("preview_urls").filter(String::isNotBlank)
            val variantsJson = item.optJSONArray("video_variants") ?: JSONArray()
            val variants = (0 until variantsJson.length()).map { variantIndex ->
                val variant = variantsJson.getJSONArray(variantIndex)
                require(variant.length() == 3) { "A favorite has invalid video variants." }
                VideoVariant(variant.requiredString(0), variant.requiredInt(1), variant.requiredInt(2))
            }
            val imageUrl = item.requiredString("image_url")
            val thumbnail = item.optionalString("thumbnail_url", "").ifBlank { previewUrls.firstOrNull() ?: imageUrl }
            ImagePost(
                id = item.requiredString("post_id"),
                dedupeKey = item.optionalString("dedupe_key", "").ifBlank {
                    "${item.requiredString("provider")}:${item.requiredString("post_id")}"
                },
                provider = item.requiredString("provider"),
                imageUrl = imageUrl,
                thumbnailUrl = thumbnail,
                thumbnailCandidates = previewUrls.ifEmpty { listOf(thumbnail) },
                extension = item.optionalString("extension", "").ifBlank {
                    imageUrl.substringBefore('?').substringAfterLast('.', "jpg").ifBlank { "jpg" }
                },
                rating = item.optionalString("rating", "q"),
                tags = item.stringList("tags").toSet(),
                source = item.optionalString("source", ""),
                artists = item.stringList("artists"),
                mediaType = item.optionalString("media_type", "image"),
                title = item.optionalString("title", ""),
                width = item.optionalInt("width", 0),
                height = item.optionalInt("height", 0),
                videoVariants = variants,
            )
        }
        return UserDataBackup(
            favorites = favorites,
            gelbooruUserId = gelbooru.requiredString("user_id"),
            gelbooruApiKey = gelbooru.requiredString("api_key"),
            rule34UserId = rule34.requiredString("user_id"),
            rule34ApiKey = rule34.requiredString("api_key"),
            provider = settings.requiredString("provider"),
            rating = settings.requiredString("rating"),
            allowNsfw = settings.requiredBoolean("allow_nsfw"),
            customTerms = settings.stringList("custom_terms"),
            excludeMale = settings.requiredBoolean("exclude_male"),
            filterGore = settings.requiredBoolean("filter_gore"),
            customBlockTags = settings.stringList("custom_block_tags").joinToString(", "),
            mediaFilter = settings.requiredString("media_filter"),
            useDoh = settings.requiredBoolean("use_doh"),
            dohProvider = settings.requiredString("doh_provider"),
            customDohEndpoint = settings.optionalString("doh_custom_endpoint", ""),
            ambientMode = settings.requiredBoolean("ambient_mode"),
            videoMaxHeight = settings.requiredInt("video_max_height"),
        )
    }

    private fun JSONObject.stringList(key: String): List<String> {
        val values = getJSONArray(key)
        return (0 until values.length()).map { index -> values.requiredString(index) }
    }

    private fun JSONObject.requiredString(key: String): String {
        val value = get(key)
        require(value is String) { "Backup field '$key' must be text." }
        return value
    }

    private fun JSONObject.optionalString(key: String, default: String): String =
        if (has(key)) requiredString(key) else default

    private fun JSONObject.requiredBoolean(key: String): Boolean {
        val value = get(key)
        require(value is Boolean) { "Backup field '$key' must be a boolean." }
        return value
    }

    private fun JSONObject.requiredInt(key: String): Int {
        val value = get(key)
        require(value is Int) { "Backup field '$key' must be an integer." }
        return value
    }

    private fun JSONObject.optionalInt(key: String, default: Int): Int =
        if (has(key)) requiredInt(key) else default

    private fun JSONArray.requiredString(index: Int): String {
        val value = get(index)
        require(value is String) { "Backup lists may contain only text values." }
        return value
    }

    private fun JSONArray.requiredInt(index: Int): Int {
        val value = get(index)
        require(value is Int) { "Backup numeric values must be integers." }
        return value
    }

    private fun validate(data: UserDataBackup) {
        require(data.provider in setOf("All", "Auto", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx")) {
            "The backup contains an unsupported provider setting."
        }
        require(data.rating in setOf("sfw", "nsfw", "all")) {
            "The backup contains an unsupported rating setting."
        }
        require(data.mediaFilter in setOf("image", "video", "all")) {
            "The backup contains an unsupported media filter."
        }
        require(data.dohProvider in setOf(
            "Cloudflare", "Cloudflare Security", "Cloudflare Family", "Google Public DNS", "AdGuard DNS", "Custom",
        )) { "The backup contains an unsupported DNS provider." }
        if (data.useDoh && data.dohProvider == "Custom") {
            val endpoint = runCatching { URI(data.customDohEndpoint) }.getOrNull()
            require(
                endpoint != null &&
                    endpoint.scheme.equals("https", ignoreCase = true) &&
                    !endpoint.host.isNullOrBlank() &&
                    endpoint.rawUserInfo == null &&
                    endpoint.rawFragment == null
            ) { "The backup contains an invalid custom DNS-over-HTTPS URL." }
        }
        require(data.videoMaxHeight in setOf(0, 480, 720, 1080, 2160)) {
            "The backup contains an unsupported video resolution."
        }
        require(data.gelbooruUserId.isNotBlank() == data.gelbooruApiKey.isNotBlank()) {
            "Backup credentials for Gelbooru are incomplete."
        }
        require(data.rule34UserId.isNotBlank() == data.rule34ApiKey.isNotBlank()) {
            "Backup credentials for Rule34.xxx are incomplete."
        }
        require(data.provider != "Gelbooru" || data.gelbooruUserId.isNotBlank()) {
            "The selected provider is missing its backup credentials."
        }
        require(data.provider != "Rule34.xxx" || data.rule34UserId.isNotBlank()) {
            "The selected provider is missing its backup credentials."
        }
        require(data.favorites.all { it.id.isNotBlank() && it.provider.isNotBlank() && it.imageUrl.isNotBlank() }) {
            "A favorite is missing its ID, provider, or image URL."
        }
        require(data.favorites.all {
            it.mediaType in setOf("image", "video") && it.width >= 0 && it.height >= 0 &&
                it.videoVariants.all { variant -> variant.url.isNotBlank() && variant.width >= 0 && variant.height >= 0 }
        }) { "A favorite contains unsupported media details." }
    }

    private fun validatePassphrase(passphrase: String) {
        require(passphrase.codePointCount(0, passphrase.length) >= 8) {
            "Use a backup passphrase with at least 8 characters."
        }
    }
}
