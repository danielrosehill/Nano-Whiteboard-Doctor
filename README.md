# Nano Whiteboard Doctor

A desktop GUI tool that transforms messy whiteboard photos into clean, polished graphics using [Fal AI's Nano Banana 2](https://fal.ai/models/fal-ai/nano-banana-2/edit) image-to-image model.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## What It Does

Take a photo of your messy whiteboard and Nano Whiteboard Doctor will:
- Clean up handwriting and sketches
- Add polished labels and icons
- Produce a professional-looking diagram

Supports **single image** or **batch processing** of multiple whiteboard photos at once.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Fal AI API key

Sign up at [fal.ai](https://fal.ai) and grab your API key from the dashboard.

### 3. Run

```bash
python app.py
```

On first run, you'll be prompted to enter your Fal API key. It's saved locally in `~/.config/nano-whiteboard-doctor/config.json` for future use.

## Usage

1. Click **Add Images** to select one or more whiteboard photos
2. (Optional) Adjust the prompt or output settings
3. Click **Process** to send them through the AI
4. Cleaned images are saved to your chosen output directory

## Configuration

- **API Key**: Stored in `~/.config/nano-whiteboard-doctor/config.json`
- **Output Format**: PNG (default), JPEG, or WebP
- **Resolution**: 0.5K, 1K (default), 2K, or 4K

## License

MIT
