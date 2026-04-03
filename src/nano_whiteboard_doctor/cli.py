#!/usr/bin/env python3
"""CLI for Nano Whiteboard Doctor - process whiteboard images from the command line."""

import argparse
import sys
from pathlib import Path

import requests

from .app import (
    DEFAULT_PROMPT, FAL_SUBMIT_URL, image_to_data_url, load_config, save_config,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def collect_images(paths: list[str]) -> list[Path]:
    images = []
    for p in paths:
        path = Path(p).resolve()
        if path.is_dir():
            for f in sorted(path.iterdir()):
                if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                    images.append(f)
        elif path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            images.append(path)
        else:
            print(f"Skipping: {p}", file=sys.stderr)
    return images


def process_image(img_path: Path, api_key: str, prompt: str,
                  output_format: str, resolution: str) -> Path | None:
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    data_url = image_to_data_url(str(img_path))
    payload = {
        "prompt": prompt,
        "image_urls": [data_url],
        "output_format": output_format,
        "resolution": resolution,
        "sync_mode": True,
    }

    resp = requests.post(FAL_SUBMIT_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    images = result.get("images", [])
    if not images:
        return None

    img_resp = requests.get(images[0]["url"], timeout=60)
    img_resp.raise_for_status()

    out_path = img_path.parent / f"{img_path.stem}_edited.{output_format}"
    with open(out_path, "wb") as f:
        f.write(img_resp.content)
    return out_path


def cli_main():
    parser = argparse.ArgumentParser(
        prog="nano-whiteboard-doctor",
        description="Clean up whiteboard photos using Fal AI Nano Banana 2",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="Image files or folders to process (launches GUI if none given)",
    )
    parser.add_argument(
        "--api-key", help="Fal AI API key (saved for future use)",
    )
    parser.add_argument(
        "--format", choices=["png", "jpeg", "webp"], default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--resolution", choices=["0.5K", "1K", "2K", "4K"], default="1K",
        help="Output resolution (default: 1K)",
    )
    parser.add_argument(
        "--prompt", default=None,
        help="Custom prompt (uses default whiteboard cleanup prompt if not set)",
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Force launch the GUI",
    )

    args = parser.parse_args()

    # No paths and no --gui flag: launch GUI
    if not args.paths and not args.gui:
        from .app import main as gui_main
        gui_main()
        return

    if args.gui:
        from .app import main as gui_main
        gui_main()
        return

    # CLI mode
    config = load_config()

    if args.api_key:
        config["api_key"] = args.api_key
        save_config(config)

    api_key = config.get("api_key")
    if not api_key:
        print("Error: No API key configured.", file=sys.stderr)
        print("Run with --api-key YOUR_KEY or launch the GUI to set it.", file=sys.stderr)
        sys.exit(1)

    prompt = args.prompt or config.get("prompt", DEFAULT_PROMPT)
    images = collect_images(args.paths)

    if not images:
        print("No images found in the given paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(images)} image(s)...")

    for i, img_path in enumerate(images, 1):
        print(f"  [{i}/{len(images)}] {img_path.name} ... ", end="", flush=True)
        try:
            out = process_image(img_path, api_key, prompt, args.format, args.resolution)
            if out:
                print(f"-> {out.name}")
            else:
                print("FAILED (no output)")
        except requests.exceptions.HTTPError as e:
            detail = ""
            if e.response is not None:
                try:
                    detail = e.response.json().get("detail", e.response.text[:200])
                except Exception:
                    detail = e.response.text[:200]
            print(f"ERROR: {detail}", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    cli_main()
