# Voice Intake Demo

## Purpose

The Test Console now includes a browser-based voice intake demo. Operators can speak a CMMS request, review and edit the transcript, then submit the transcript to the existing `cmms-intake` API with the selected `environment_code`.

## Browser Speech API

The demo uses the browser Web Speech API only:

```javascript
window.SpeechRecognition || window.webkitSpeechRecognition
```

No backend audio upload route was added. The FastAPI backend receives only the edited transcript text and optional metadata:

```json
{
  "environment_code": "DEFAULT",
  "text": "There is a water leak in ARC room 205. It looks urgent.",
  "source": "voice_transcript"
}
```

## Supported Languages

- English - Canada: `en-CA`
- English - US: `en-US`
- Chinese - Simplified Mandarin: `zh-CN`
- Chinese - Traditional Mandarin: `zh-TW`
- French - Canada: `fr-CA`
- Spanish - Spain: `es-ES`
- Japanese: `ja-JP`
- Korean: `ko-KR`

The selected value is assigned to `recognition.lang`.

## Privacy Note

Speech recognition is handled by the browser. This app does not store audio. Operators should review the transcript before sending it to the API.

## Why No Backend Audio Upload

This is Option A: a lightweight demo that keeps the existing local advisory API boundary intact. Avoiding audio uploads also avoids storing raw audio, adding audio retention rules, adding a transcription service, or expanding the backend attack surface.

## Known Limitations

- Browser support varies by vendor and OS.
- Speech recognition may use browser/vendor services and should not be described as fully local or offline.
- Microphone permission errors are controlled by the browser.
- Accuracy depends on browser speech recognition quality, microphone quality, language choice, and background noise.
- The backend validates the transcript output after LLM extraction; it does not validate the audio itself.

## Future Upgrade Path

- Local Whisper transcription.
- Cloud STT provider integration.
- Streaming speech transcription.
- Mobile technician workflow with push-to-talk and offline-friendly review.
