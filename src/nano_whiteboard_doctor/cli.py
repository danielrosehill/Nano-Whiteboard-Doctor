#!/usr/bin/env python3
"""CLI for Nano Whiteboard Doctor - process whiteboard images from the command line."""

import argparse
import sys
from pathlib import Path

import requests

from .app import (
    DEFAULT_PROMPT, IMAGE_EXTS, build_prompt, call_fal_api, load_config, save_config,
)


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


def cli_main():
    parser = argparse.ArgumentParser(
        prog="nano-whiteboard-doctor",
        description="Clean up whiteboard photos using Fal AI Nano Banana 2",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="Image files or folders to process (launches GUI if none given)",
    )
    parser.add_argument("--api-key", help="Fal AI API key (saved for future use)")
    parser.add_argument("--format", choices=["png", "jpeg", "webp"], default="png",
                        help="Output format (default: png)")
    parser.add_argument("--resolution", choices=["0.5K", "1K", "2K", "4K"], default="1K",
                        help="Output resolution (default: 1K)")
    parser.add_argument("--num-images", type=int, choices=[1, 2, 3, 4], default=1,
                        help="Number of variant outputs per image (default: 1)")
    parser.add_argument("--prompt", default=None,
                        help="Custom prompt (uses saved/default prompt if not set)")
    parser.add_argument("--color", action="store_true", help="Convert to color")
    parser.add_argument("--bw", action="store_true", help="Convert to black & white")
    parser.add_argument("--handwritten", action="store_true", help="Preserve handwritten style")
    parser.add_argument("--gui", action="store_true", help="Force launch the GUI")

    args = parser.parse_args()

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

    base_prompt = args.prompt or config.get("prompt", DEFAULT_PROMPT)
    prompt = build_prompt(base_prompt, args.color, args.bw, args.handwritten)
    images = collect_images(args.paths)

    if not images:
        print("No images found in the given paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(images)} image(s)...")

    for i, img_path in enumerate(images, 1):
        print(f"  [{i}/{len(images)}] {img_path.name} ... ", end="", flush=True)
        try:
            result_images = call_fal_api(
                str(img_path), api_key, prompt,
                args.format, args.resolution, args.num_images,
            )
            if not result_images:
                print("FAILED (no output)")
                continue

            for j, img_data in enumerate(result_images):
                img_resp = requests.get(img_data["url"], timeout=60)
                img_resp.raise_for_status()
                suffix = "_edited" if len(result_images) == 1 else f"_edited_{j + 1}"
                out_path = img_path.parent / f"{img_path.stem}{suffix}.{args.format}"
                with open(out_path, "wb") as f:
                    f.write(img_resp.content)
                print(f"-> {out_path.name}", end="  " if j < len(result_images) - 1 else "")
            print()

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
