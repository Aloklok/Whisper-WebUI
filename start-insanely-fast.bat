@echo off

set WHISPER_TYPE=insanely_fast_whisper

echo Starting Whisper-WebUI with GPU acceleration (Speculative Decoding)...
echo Selected Engine: %WHISPER_TYPE%

call venv\scripts\activate
python app.py --whisper_type %WHISPER_TYPE% %*

echo "App terminated."
pause
