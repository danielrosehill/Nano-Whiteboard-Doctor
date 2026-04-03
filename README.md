# Nano Whiteboard Doctor

A desktop GUI tool that transforms messy whiteboard photos into clean, polished graphics using [Fal AI's Nano Banana 2](https://fal.ai/models/fal-ai/nano-banana-2/edit) image-to-image model.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52)

## What It Does

Take a photo of your messy whiteboard and Nano Whiteboard Doctor will:
- Clean up handwriting and sketches
- Add polished labels and icons
- Produce a professional-looking diagram

Supports **single image** or **batch processing** of multiple whiteboard photos at once.

## Install

### Option A: Debian package (.deb)

Download the `.deb` from [Releases](https://github.com/danielrosehill/Nano-Whiteboard-Doctor/releases) and install:

```bash
sudo dpkg -i nano-whiteboard-doctor_0.1.0_all.deb
nano-whiteboard-doctor
```

### Option B: Run from source with uv

```bash
git clone https://github.com/danielrosehill/Nano-Whiteboard-Doctor.git
cd Nano-Whiteboard-Doctor
uv sync
uv run nano-whiteboard-doctor
```

### Get a Fal AI API key

Sign up at [fal.ai](https://fal.ai) and grab your API key from the dashboard. On first run, you'll be prompted to enter it. The key is saved locally in `~/.config/nano-whiteboard-doctor/config.json`.

## Usage

1. Click **Add Images** to select one or more whiteboard photos
2. (Optional) Adjust the prompt or output settings
3. Click **Process** to send them through the AI
4. Cleaned images are saved to your chosen output directory

## Configuration

- **API Key**: Stored in `~/.config/nano-whiteboard-doctor/config.json`
- **Output Format**: PNG (default), JPEG, or WebP
- **Resolution**: 0.5K, 1K (default), 2K, or 4K

## Building the .deb

```bash
./build-deb.sh
```

Requires `uv`, `dpkg-deb`, and `fakeroot`.

## License

MIT
