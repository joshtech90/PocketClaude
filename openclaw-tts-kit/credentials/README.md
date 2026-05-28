# Google Cloud TTS — Service-Account-Setup für OpenClaw

Dieses Verzeichnis erwartet ein Service-Account-JSON mit Cloud-TTS-Zugriff:

```
credentials/google_tts_credentials.json
```

Alternativ kann der Pfad per Env-Var überschrieben werden:

```bash
export OPENCLAW_TTS_CREDENTIALS=/anderer/pfad/zu/creds.json
```

## Service-Account aufsetzen (einmalig)

1. **Google Cloud Console öffnen** → Projekt anlegen (oder bestehendes wählen).
2. **APIs aktivieren** (Library):
   - `Cloud Text-to-Speech API` (für Chirp 3 HD — die kostenlose Default-Option)
   - `Vertex AI / Agent Platform API` (`aiplatform.googleapis.com`) —
     **zusätzlich nötig für die Gemini-2.5-Flash und Gemini-3.1-Flash-Modelle**.
     Ohne diese API kommt `SERVICE_DISABLED` beim Versuch, ein Gemini-TTS-
     Modell zu nutzen.
3. **Billing aktivieren** — das Cloud-Projekt mit einem Billing-Account
   verknüpfen. Chirp läuft 1 Mio Zeichen/Monat im Free-Tier, danach $30/M Zeichen.
   Gemini-Voices sind komplett kostenpflichtig.
4. **Service-Account anlegen** (IAM & Admin → Service Accounts):
   - Rolle `Cloud Text-to-Speech User` (`roles/texttospeech.user`)
   - Bei Gemini-Voices zusätzlich `Vertex AI User` (`roles/aiplatform.user`)
5. **JSON-Key herunterladen** → unter dem oben genannten Pfad ablegen,
   `chmod 600` setzen.

## Schnell-Test

```bash
python -c "
from tts_engine import synthesize, is_configured
assert is_configured(), 'creds fehlen'
audio = synthesize('Hallo OpenClaw, das hier ist Chirp drei HD.',
                   model_id='chirp3hd-Algenib')
open('/tmp/test.mp3', 'wb').write(audio)
print('Audio geschrieben:', len(audio), 'Bytes')
"
```

## Welche Konten sich aufs $10-Cloud-Credit anrechnen lassen

Das `Google Developer Program premium benefit`-Credit ($10/Monat des AI-Pro-Abos)
gilt **NUR** für Spend über Cloud TTS / Vertex AI auf einem mit Billing
verknüpften Projekt — NICHT für die separate `generativelanguage.googleapis.com`-
Direct-API. Das Kit nutzt ausschließlich den Cloud-TTS-Pfad, das Credit wird also
automatisch angerechnet.
