# SentryBox

SentryBox is a Home Assistant custom integration that monitors an RTSP or RTSPS camera stream, captures frames with `ffmpeg`, sends them to a local Ollama vision model, and reports whether a configured event or object of interest is present in the camera view.

## Project Structure

- `custom_components/sentrybox/manifest.json`: Integration metadata.
- `custom_components/sentrybox/__init__.py`: Entry setup, teardown, and `reanalyze_now` service registration.
- `custom_components/sentrybox/config_flow.py`: UI setup flow and reloadable options flow.
- `custom_components/sentrybox/const.py`: Domain constants, defaults, prompt, and helpers.
- `custom_components/sentrybox/coordinator.py`: Frame capture, optional crop, profile-aware Ollama call, JSON parsing, and debounce logic.
- `custom_components/sentrybox/entity.py`: Shared entity metadata and state attributes.
- `custom_components/sentrybox/binary_sensor.py`: Profile-aware detected entity.
- `custom_components/sentrybox/sensor.py`: Confidence and summary entities.
- `custom_components/sentrybox/camera.py`: Preview camera for the exact frame sent to Ollama.
- `custom_components/sentrybox/services.yaml`: `sentrybox.reanalyze_now` service definition.
- `custom_components/sentrybox/strings.json` and `translations/en.json`: Config and options flow strings.

## Detection Profiles

SentryBox now supports multiple built-in detection profiles per config entry:

- `Package at door`: delivery package detection near the entryway
- `Garbage truck pickup`: garbage or recycling truck servicing bins at the end of the driveway or curb
- `Custom detection`: user-defined target label plus a prompt override if needed

You can create multiple SentryBox entries against the same camera stream as long as they use different detection profiles or a different custom label. This lets one camera watch for more than one kind of event.

## Installation

1. Copy `custom_components/sentrybox` into your Home Assistant configuration directory.
2. Ensure `ffmpeg` is installed and available on the Home Assistant host.
3. Ensure Ollama is running locally or on a reachable host, and that the chosen vision-capable model is already pulled.
4. Restart Home Assistant.
5. In Home Assistant, go to `Settings -> Devices & Services -> Add Integration`.
6. Search for `SentryBox`.

## Example Config Flow Usage

Use values similar to these during setup:

- `Name`: `SentryBox`
- `RTSP/RTSPS stream URL`: `rtsp://username:password@camera.local:554/stream1`
- `Ollama base URL`: `http://localhost:11434`
- `Ollama model name`: `gemma3:4b`
- `Detection profile`: `Package at door`

For a driveway trash-collection monitor, create another entry such as:

- `Name`: `Driveway Trash Watch`
- `RTSP/RTSPS stream URL`: `rtsp://username:password@camera.local:554/stream1`
- `Ollama base URL`: `http://localhost:11434`
- `Ollama model name`: `gemma3:4b`
- `Detection profile`: `Garbage truck pickup`

After the integration is created, open the entry options to tune:

- detection profile
- custom detection label
- polling interval in seconds
- frame capture timeout and Ollama timeout
- confidence threshold
- prompt override
- large multiline prompt editing
- optional crop region
- snapshot retention
- positive and negative debounce counts

## Dependencies And Assumptions

- Home Assistant with support for custom integrations and config flows
- `ffmpeg` installed on the same host where Home Assistant runs
- Ollama reachable at the configured base URL
- A vision-capable Ollama model already available locally
- No additional Python packages beyond Home Assistant dependencies

## Detection Pipeline

Each coordinator refresh performs the same pipeline:

1. Run `ffmpeg` against the configured RTSP or RTSPS URL and extract one JPEG frame.
2. Apply an `ffmpeg` crop filter if the normalized crop region is configured.
3. Base64-encode the frame and send it to Ollama `POST /api/chat`.
4. Ask Ollama for structured JSON with `event_detected`, `confidence`, and `summary`.
5. Parse the response, clamp invalid values, and treat malformed or uncertain output as `not detected`.
6. Apply the consecutive positive/negative debounce rules to avoid noisy state flips.
7. Update:
   - `binary_sensor.<name>_detected`
   - `sensor.<name>_confidence`
   - `sensor.<name>_summary`
   - `camera.<name>_last_analysis_frame`

## Service

Call `sentrybox.reanalyze_now` to trigger an immediate analysis. You can optionally pass an `entry_id` to refresh only one SentryBox entry.

## Local Testing

1. Run `python3 -m compileall custom_components/sentrybox` from the repository root for a syntax check.
2. Copy the integration into a Home Assistant test instance.
3. Add the integration through the UI.
4. Confirm the four entities are created, including the last analysis camera preview.
5. Use Developer Tools -> Actions and call `sentrybox.reanalyze_now`.
6. Watch the entity states and attributes update after each refresh.
7. Test the configured profile with a known-positive frame and a known-negative frame.
8. If you use one camera for multiple scenarios, create multiple SentryBox entries with different profile selections and verify each binary sensor responds only to its own target.

## Notes

- The built-in prompts are conservative and prefer `not detected` when confidence is low.
- Leaving the prompt blank in options resets it to the built-in prompt for the selected detection profile.
- The camera preview entity always shows the latest analyzed frame; snapshot retention controls whether that on-disk path is exposed as a retained debug snapshot.
- Credentials in the stream URL are redacted in logs.

## License

Copyright 2026 Esau Engineering LLC.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
