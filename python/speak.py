#!/usr/bin/env python3
"""
TTS helper for JarvisLab.
edge-tts (neural) + Windows SAPI fallback.

Usage: python speak.py "text" [language_code]
Exit 0 + prints OK on success.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time

VOICE_MAP = {
    # Vietnamese
    "vi-VN": "vi-VN-HoaiMyNeural",
    "vi": "vi-VN-HoaiMyNeural",
    # English
    "en-US": "en-US-AriaNeural",
    "en": "en-US-AriaNeural",
    "en-GB": "en-GB-SoniaNeural",
    "en-AU": "en-AU-NatashaNeural",
    "en-CA": "en-CA-ClaraNeural",
    "en-IN": "en-IN-NeerjaNeural",
    "en-IE": "en-IE-EmilyNeural",
    "en-ZA": "en-ZA-LeahNeural",
    "en-NZ": "en-NZ-MollyNeural",
    "en-PH": "en-PH-RosaNeural",
    "en-SG": "en-SG-LunaNeural",
    # Chinese
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "zh-TW": "zh-TW-HsiaoChenNeural",
    "zh-HK": "zh-HK-HiuMaanNeural",
    # Japanese / Korean
    "ja-JP": "ja-JP-NanamiNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "ko": "ko-KR-SunHiNeural",
    # French
    "fr-FR": "fr-FR-DeniseNeural",
    "fr": "fr-FR-DeniseNeural",
    "fr-CA": "fr-CA-SylvieNeural",
    "fr-CH": "fr-CH-AurelieNeural",
    "fr-BE": "fr-BE-CharlineNeural",
    # German
    "de-DE": "de-DE-KatjaNeural",
    "de": "de-DE-KatjaNeural",
    "de-AT": "de-AT-IngridNeural",
    "de-CH": "de-CH-LeniNeural",
    # Spanish
    "es-ES": "es-ES-ElviraNeural",
    "es": "es-ES-ElviraNeural",
    "es-MX": "es-MX-DaliaNeural",
    "es-US": "es-US-PalomaNeural",
    "es-AR": "es-AR-ElenaNeural",
    "es-CO": "es-CO-SalomeNeural",
    "es-CL": "es-CL-CatalinaNeural",
    "es-PE": "es-PE-CamilaNeural",
    "es-VE": "es-VE-PaolaNeural",
    "es-UY": "es-UY-ValentinaNeural",
    "es-PR": "es-PR-KarinaNeural",
    "es-DO": "es-DO-RamonaNeural",
    "es-EC": "es-EC-AndreaNeural",
    "es-GT": "es-GT-MartaNeural",
    "es-BO": "es-BO-MarcelaNeural",
    "es-PY": "es-PY-TaniaNeural",
    "es-CR": "es-CR-MariaNeural",
    "es-PA": "es-PA-MargaritaNeural",
    "es-HN": "es-HN-KarlaNeural",
    "es-NI": "es-NI-YolandaNeural",
    "es-SV": "es-SV-LorenaNeural",
    # Italian / Portuguese / Russian
    "it-IT": "it-IT-ElsaNeural",
    "it": "it-IT-ElsaNeural",
    "pt-PT": "pt-PT-RaquelNeural",
    "pt": "pt-PT-RaquelNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    # Dutch / Polish / Nordic
    "nl-NL": "nl-NL-ColetteNeural",
    "nl": "nl-NL-ColetteNeural",
    "nl-BE": "nl-BE-ArnaudNeural",
    "pl-PL": "pl-PL-ZofiaNeural",
    "pl": "pl-PL-ZofiaNeural",
    "sv-SE": "sv-SE-SofieNeural",
    "sv": "sv-SE-SofieNeural",
    "nb-NO": "nb-NO-PernilleNeural",
    "no": "nb-NO-PernilleNeural",
    "da-DK": "da-DK-ChristelNeural",
    "da": "da-DK-ChristelNeural",
    "fi-FI": "fi-FI-SelmaNeural",
    "fi": "fi-FI-SelmaNeural",
    # Eastern Europe
    "cs-CZ": "cs-CZ-VlastaNeural",
    "cs": "cs-CZ-VlastaNeural",
    "el-GR": "el-GR-AthinaNeural",
    "el": "el-GR-AthinaNeural",
    "uk-UA": "uk-UA-PolinaNeural",
    "uk": "uk-UA-PolinaNeural",
    "ro-RO": "ro-RO-AlinaNeural",
    "ro": "ro-RO-AlinaNeural",
    "hu-HU": "hu-HU-NoemiNeural",
    "hu": "hu-HU-NoemiNeural",
    "sk-SK": "sk-SK-ViktoriaNeural",
    "sk": "sk-SK-ViktoriaNeural",
    "bg-BG": "bg-BG-KalinaNeural",
    "bg": "bg-BG-KalinaNeural",
    "hr-HR": "hr-HR-GabrijelaNeural",
    "hr": "hr-HR-GabrijelaNeural",
    "ca-ES": "ca-ES-JoanaNeural",
    "ca": "ca-ES-JoanaNeural",
    # Arabic / Hebrew / Turkish
    "tr-TR": "tr-TR-EmelNeural",
    "tr": "tr-TR-EmelNeural",
    "ar-SA": "ar-SA-ZariyahNeural",
    "ar": "ar-SA-ZariyahNeural",
    "ar-EG": "ar-EG-SalmaNeural",
    "ar-AE": "ar-AE-FatimaNeural",
    "he-IL": "he-IL-HilaNeural",
    "he": "he-IL-HilaNeural",
    # Indian
    "hi-IN": "hi-IN-SwaraNeural",
    "hi": "hi-IN-SwaraNeural",
    "bn-IN": "bn-IN-TanishaaNeural",
    "bn": "bn-IN-TanishaaNeural",
    "ta-IN": "ta-IN-PallaviNeural",
    "ta": "ta-IN-PallaviNeural",
    "te-IN": "te-IN-ShrutiNeural",
    "te": "te-IN-ShrutiNeural",
    # SEA
    "th-TH": "th-TH-PremwadeeNeural",
    "th": "th-TH-PremwadeeNeural",
    "id-ID": "id-ID-GadisNeural",
    "id": "id-ID-GadisNeural",
    "ms-MY": "ms-MY-YasminNeural",
    "ms": "ms-MY-YasminNeural",
    "fil-PH": "fil-PH-BlessicaNeural",
    "fil": "fil-PH-BlessicaNeural",
}


def resolve_voice(lang: str) -> str:
    override = os.environ.get("VOICE_TTS_VOICE") or os.environ.get("JARVIS_TTS_VOICE")
    if override:
        return override
    return VOICE_MAP.get(lang, VOICE_MAP.get(lang.split("-")[0], lang))


def play_mp3_windows(path: str) -> bool:
    """Play MP3 synchronously on Windows via WPF MediaPlayer."""
    abs_path = os.path.abspath(path).replace("\\", "/")
    ps_script = f"""
$ErrorActionPreference = 'Stop'
try {{
    Add-Type -AssemblyName PresentationCore
    $player = New-Object System.Windows.Media.MediaPlayer
    $player.Open([Uri]"file:///{abs_path}")
    $player.Volume = 1.0
    $player.Play()
    $deadline = (Get-Date).AddSeconds(8)
    while (-not $player.NaturalDuration.HasTimeSpan) {{
        if ((Get-Date) -gt $deadline) {{ break }}
        Start-Sleep -Milliseconds 100
    }}
    if ($player.NaturalDuration.HasTimeSpan) {{
        Start-Sleep -Milliseconds ([int]$player.NaturalDuration.TimeSpan.TotalMilliseconds + 350)
    }} else {{
        Start-Sleep -Seconds 5
    }}
    $player.Stop()
    $player.Close()
    exit 0
}} catch {{
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}}
"""
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"play_mp3 error: {e}", file=sys.stderr)
        return False


def speak_sapi(text: str) -> None:
    safe = (
        text.replace('"', "'")
        .replace("`", "")
        .replace("$", "")
        .replace("\n", " ")
    )
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f'$s.Speak("{safe}")'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        timeout=120,
    )


async def speak_edge_tts(text: str, voice: str) -> bool:
    try:
        import edge_tts
    except ImportError:
        print("edge-tts not installed, falling back to SAPI", file=sys.stderr)
        return False

    fd, output = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        if not os.path.exists(output) or os.path.getsize(output) < 32:
            print("edge-tts produced empty audio", file=sys.stderr)
            return False
        success = play_mp3_windows(output)
        if not success:
            # last-resort open
            try:
                os.startfile(os.path.abspath(output))  # type: ignore[attr-defined]
                wait_sec = max(3.0, os.path.getsize(output) / 8000.0)
                time.sleep(wait_sec)
                return True
            except Exception:
                return False
        return True
    except Exception as e:
        print(f"edge-tts error: {e}", file=sys.stderr)
        return False
    finally:
        try:
            if os.path.exists(output):
                os.unlink(output)
        except Exception:
            pass


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: speak.py <text> [language]", file=sys.stderr)
        sys.exit(1)

    text = sys.argv[1].strip()
    if not text:
        print("Empty text", file=sys.stderr)
        sys.exit(1)

    lang = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("VOICE_LANGUAGE", "vi-VN")
    voice = resolve_voice(lang)

    success = asyncio.run(speak_edge_tts(text, voice))
    if not success:
        print("Using SAPI fallback", file=sys.stderr)
        speak_sapi(text)

    print("OK")


if __name__ == "__main__":
    main()
