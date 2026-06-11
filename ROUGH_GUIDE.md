Install these on the processing workers. This is enough for Fable to plan the buildout.

## Required

| Tool                       | Purpose                                                                                                                                                                                                                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FFmpeg** and **ffprobe** | Core media engine: inspect files, extract audio, trim clips, crop, resize, overlay logos, render subtitles, normalize audio, and export MP4s. ([ffmpeg.org](https://ffmpeg.org/download.html))                                                                                  |
| **WhisperX**               | Transcription with word-level timestamps. Use this as the main transcription package because accurate word timing matters for subtitles and clip boundaries. WhisperX uses `faster-whisper` internally and supports speaker diarization through `pyannote.audio`. ([GitHub][1]) |
| **PySceneDetect**          | Detect visual scene boundaries so clips start and end at sensible moments. ([scenedetect.com][2])                                                                                                                                                                               |
| **Python 3.11 or 3.12**    | Runtime for the AI and media-processing services.                                                                                                                                                                                                                               |
| **Node.js LTS**            | Useful for your application layer and job orchestration if the platform is TypeScript-based.                                                                                                                                                                                    |
| **Docker**                 | Package the media workers consistently.                                                                                                                                                                                                                                         |

Basic install shape:

```bash
# System-level
ffmpeg
python
node
docker

# Python
pip install whisperx scenedetect[opencv]
```

WhisperX currently documents `pip install whisperx` as the recommended production installation path. ([GitHub][1])

## Required for Good Conference Footage Results

| Tool                    | Purpose                                                                                                                                                                       |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **pyannote.audio**      | Speaker diarization: identify when different people are speaking. Useful for interviews, conference booths, and panel discussions. WhisperX integrates with it. ([GitHub][1]) |
| **OpenCV**              | Frame extraction and basic computer-vision processing. PySceneDetect can use it, and it is useful for thumbnail generation and crop analysis.                                 |
| **NVIDIA CUDA Toolkit** | GPU acceleration for transcription workers. WhisperX currently documents CUDA Toolkit **12.8** for GPU acceleration; CPU-only operation is possible but slower. ([GitHub][1]) |

Python packages:

```bash
pip install pyannote.audio opencv-python
```

You may also need a Hugging Face token to download and use the relevant pyannote diarization models.

## Recommended for Automatic Vertical Cropping

| Tool          | Purpose                                                                                                                                                                                            |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MediaPipe** | Detect faces and track the subject so horizontal conference footage can be reframed into 9:16 clips. Its repository provides cross-platform ML tooling for live and streaming media. ([GitHub][3]) |

```bash
pip install mediapipe
```

This is optional for the first iteration. A simpler MVP can center-crop footage or place the original horizontal frame inside a branded vertical canvas.

## Recommended for Highlight Selection

You need an LLM provider or a locally hosted model. This is not a special video package. The LLM receives:

* Transcript segments
* Speaker turns
* Event context
* Desired clip duration
* Target audience
* Brand or product notes

It returns suggested highlight ranges and rationales.

Choose one:

| Option                                                     | When to use it                          |
| ---------------------------------------------------------- | --------------------------------------- |
| **OpenAI API**, **Anthropic API**, or another hosted model | Fastest initial implementation          |
| **Ollama**                                                 | Simple local model hosting              |
| **vLLM**                                                   | Higher-throughput self-hosted inference |

For an internal MVP, a hosted API is usually simpler. Keep the LLM behind an abstraction so it can be replaced later.

## Useful but Optional

| Tool                                    | Purpose                                                                       |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| **auto-editor**                         | Automatically tighten pauses and dead air in talking-head footage             |
| **ImageMagick**                         | Generate thumbnails, title cards, and static image assets                     |
| **Redis**                               | Queue backend for media-processing jobs                                       |
| **PostgreSQL**                          | Store uploads, transcripts, clip candidates, render states, and brand presets |
| **S3-compatible storage**               | Store originals, intermediate files, and final exports                        |
| **MinIO**                               | Local or self-hosted S3-compatible storage                                    |
| **Temporal**, **BullMQ**, or **Celery** | Orchestrate long-running and retryable processing stages                      |

## Branding: Use FFmpeg First

You do **not** need Remotion for the initial version.

FFmpeg can handle:

* Logo overlays
* Brand-color backgrounds
* Intro and outro assets
* Lower thirds
* Static text
* Burned-in subtitles
* Cropping and scaling
* Audio normalization
* MP4 encoding

Add Remotion later only when you need complex animated templates, sophisticated caption animations, or React-based preview rendering.

## Do Not Install These Initially

Skip:

* OpenCut
* Kdenlive
* LosslessCut
* CapCut-like editors
* Small “AI clipping platform” GitHub repositories
* Generative video tools

Those are user-facing editing applications or experimental end-to-end projects. Your internal platform needs composable processing dependencies.

## Minimal Final Checklist

```text
System:
- FFmpeg + ffprobe
- Python 3.11 or 3.12
- Node.js LTS
- Docker
- NVIDIA CUDA Toolkit 12.8 on GPU workers

Python:
- whisperx
- pyannote.audio
- scenedetect[opencv]
- opencv-python
- mediapipe

Infrastructure:
- PostgreSQL
- Redis
- S3-compatible storage
- A job runner: BullMQ, Temporal, or Celery

External or self-hosted AI:
- One LLM provider for transcript-based highlight selection
```

That is the correct dependency list for the build plan. Fable should treat FFmpeg as the rendering core, WhisperX as the transcript layer, pyannote as the speaker layer, PySceneDetect as the scene-boundary layer, MediaPipe as the crop layer, and the LLM as the highlight-selection layer.

[1]: https://github.com/m-bain/whisperX "GitHub - m-bain/whisperX: WhisperX:  Automatic Speech Recognition with Word-level Timestamps (& Diarization) · GitHub"
[2]: https://www.scenedetect.com/docs/latest/ "PySceneDetect Documentation — PySceneDetect 0.7 documentation"
[3]: https://github.com/google-ai-edge/mediapipe "GitHub - google-ai-edge/mediapipe: Cross-platform, customizable ML solutions for live and streaming media. · GitHub"
