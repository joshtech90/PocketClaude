package de.smartzone.pocketclaude.data

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

/**
 * Komprimiert Bilder vor dem Upload, analog zu dem, was ChatGPT, Claude und
 * Gemini auf ihrer Client-Seite machen.
 *
 * Es gibt zwei Stufen, weil ein Bild zum ANSEHEN und ein Bild zum BEARBEITEN
 * unterschiedlich viel Auflösung brauchen:
 *
 *  - [Purpose.VISION] für Anhänge, die ein Modell nur lesen soll. 1568 px
 *    ist die Empfehlung für Vision-Eingaben; mehr Pixel liefern dort messbar
 *    keine besseren Antworten, kosten aber Tokens und Wartezeit.
 *  - [Purpose.EDIT] für Bilder, die als Vorlage bearbeitet werden. Hier ist
 *    die Vorlage die Obergrenze für das Ergebnis: was hier wegkomprimiert
 *    wird, kann kein Modell zurückholen.
 *
 * An einem 34-Megapixel-Foto (4912x6879, 3,9 MB) gemessen:
 * VISION ergibt 0,45 MB (89 Prozent kleiner), EDIT ergibt 1,14 MB
 * (71 Prozent kleiner) bei 2,6-mal so vielen Bildpunkten. Der Sprung von
 * Qualität 85 auf 92 kostet dabei nur rund 60 KB, ist also fast geschenkt.
 *
 * Weiterhin gilt: EXIF-Orientierung wird vor dem Encode angewandt, sonst
 * landet das Bild seitlich, wenn das Telefon im Hochformat geschossen hat.
 * Nicht-Bilder (PDF, txt, …) werden unverändert durchgereicht.
 */
object ImageCompressor {

    /**
     * Obergrenze für die Fläche, die beim Decodieren im Speicher landet.
     * 16 Megapixel entsprechen als ARGB-Bitmap rund 64 MB; darüber wird das
     * Zwischenbild auf schwachen Geräten zum Problem.
     */
    private const val MAX_DECODED_PIXELS = 16_000_000L

    /** Wofür das Bild gedacht ist. Bestimmt Kantenlänge und Qualität. */
    enum class Purpose(
        val maxEdgePx: Int,
        val jpegQuality: Int,
        /** Unterhalb dieser Größe lohnt das Neucodieren nicht. */
        val skipBelowBytes: Int,
        /** Bis zu dieser Größe bleibt ein ohnehin kleines Bild im Original. */
        val keepOriginalBelowBytes: Int,
    ) {
        VISION(1568, 85, 200 * 1024, 1_500_000),
        EDIT(2560, 92, 400 * 1024, 2_500_000),
    }

    data class Result(val filename: String, val mime: String, val bytes: ByteArray)

    operator fun Result.component1() = filename
    operator fun Result.component2() = mime
    operator fun Result.component3() = bytes

    /** Hauptaufruf. Bei Nicht-Bild oder schon-klein-genug: 1:1 zurück. */
    fun maybeCompress(
        filename: String,
        mime: String,
        bytes: ByteArray,
        purpose: Purpose = Purpose.VISION,
    ): Result {
        val isImage = mime.startsWith("image/")
        if (!isImage) return Result(filename, mime, bytes)
        // Animated GIFs/WebP würden durch das Recodieren ihre Animation verlieren.
        if (mime == "image/gif") return Result(filename, mime, bytes)
        if (bytes.size <= purpose.skipBelowBytes) return Result(filename, mime, bytes)

        return try {
            compress(filename, bytes, purpose) ?: Result(filename, mime, bytes)
        } catch (_: Throwable) {
            // Bei jedem Fehler: Original durchreichen, lieber großer Upload als gar keiner.
            Result(filename, mime, bytes)
        }
    }

    private fun compress(filename: String, bytes: ByteArray, purpose: Purpose): Result? {
        // 1) Größen rausfinden ohne den ganzen Bitmap zu laden.
        val sizeOpts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, sizeOpts)
        val srcW = sizeOpts.outWidth
        val srcH = sizeOpts.outHeight
        if (srcW <= 0 || srcH <= 0) return null

        val longest = maxOf(srcW, srcH)
        if (longest <= purpose.maxEdgePx && bytes.size <= purpose.keepOriginalBelowBytes) {
            // Schon klein genug — Original (mit originalem MIME) behalten.
            return Result(filename, sizeOpts.outMimeType ?: "image/jpeg", bytes)
        }

        // 2) inSampleSize berechnen (Power of 2). Beispiel: 4032 → 1568 → factor ~2.57,
        //    wir nehmen 2 (= 2016px Edge), und resizen danach präzise mit Matrix.
        var inSample = 1
        while (longest / (inSample * 2) >= purpose.maxEdgePx) inSample *= 2

        // Der Schritt oben decodiert bewusst großzügig, damit beim präzisen
        // Skalieren danach noch Reserve da ist. Bei EDIT mit 2560 px kann das
        // aber bis zu 5120 px bedeuten, und ein quadratisches Bild dieser Größe
        // belegt als ARGB-Bitmap rund 100 MB. Das kippt ein Gerät mit kleinem
        // Heap, bevor überhaupt komprimiert wird. Deshalb hier eine Obergrenze
        // für die decodierte Fläche: Wo sie greift, wird exakt auf Zielgröße
        // decodiert, was praktisch keine Qualität kostet.
        while (
            inSample < 16 &&
            (srcW.toLong() / inSample) * (srcH.toLong() / inSample) > MAX_DECODED_PIXELS
        ) inSample *= 2

        val opts = BitmapFactory.Options().apply { inSampleSize = inSample }
        val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
            ?: return null

        // 3) Auf MAX_EDGE_PX skalieren, EXIF-Rotation berücksichtigen.
        // WICHTIG: jedes Zwischen-Bitmap recyceln, sobald wir sein Output haben —
        // sonst Memory-Leak bei großen Eingaben (Original-Foto kann 4 MB sein,
        // bleibt sonst zusammen mit der gedrehten + skalierten Variante im Heap).
        val rotation = readExifRotation(bytes)
        val rotatedFirst = applyRotation(decoded, rotation)
        if (rotatedFirst !== decoded) decoded.recycle()

        val w = rotatedFirst.width
        val h = rotatedFirst.height
        val scale = purpose.maxEdgePx.toFloat() / maxOf(w, h).toFloat()
        val scaled = if (scale < 1.0f) {
            Bitmap.createScaledBitmap(
                rotatedFirst,
                (w * scale).toInt(), (h * scale).toInt(),
                /* filter = */ true,
            )
        } else {
            rotatedFirst
        }
        if (scaled !== rotatedFirst) rotatedFirst.recycle()

        // 4) JPEG encoden
        val out = ByteArrayOutputStream(64 * 1024)
        scaled.compress(Bitmap.CompressFormat.JPEG, purpose.jpegQuality, out)
        scaled.recycle()

        val newName = renameToJpg(filename)
        return Result(newName, "image/jpeg", out.toByteArray())
    }

    private fun readExifRotation(bytes: ByteArray): Int = try {
        ByteArrayInputStream(bytes).use { stream ->
            val exif = ExifInterface(stream)
            when (exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90
                ExifInterface.ORIENTATION_ROTATE_180 -> 180
                ExifInterface.ORIENTATION_ROTATE_270 -> 270
                else -> 0
            }
        }
    } catch (_: Throwable) { 0 }

    private fun applyRotation(bitmap: Bitmap, degrees: Int): Bitmap {
        if (degrees == 0) return bitmap
        val m = Matrix().apply { postRotate(degrees.toFloat()) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, m, true)
    }

    private fun renameToJpg(name: String): String {
        val base = name.substringBeforeLast('.', name)
        return "$base.jpg"
    }
}
