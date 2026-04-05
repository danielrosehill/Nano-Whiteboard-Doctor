#!/usr/bin/env python3
"""CLI for Nano Tech Diagrams - create and edit tech diagrams from the command line."""

import argparse
import sys
from pathlib import Path

import requests

from .core import (
    ASPECT_RATIOS, DIAGRAM_TYPE_BY_KEY, DIAGRAM_TYPE_CATEGORIES, DIAGRAM_TYPES,
    IMAGE_EXTS, STYLE_BY_KEY, STYLE_CATEGORIES, STYLE_PRESETS,
    build_img2img_prompt, build_txt2img_prompt, build_whiteboard_prompt,
    call_fal_img2img, call_fal_txt2img, load_config, save_config,
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
    style_keys = [p[0] for p in STYLE_PRESETS]
    dt_keys = [p[0] for p in DIAGRAM_TYPES]

    parser = argparse.ArgumentParser(
        prog="nano-tech-diagrams",
        description="Create and edit tech diagrams using Nano Banana 2 (via Fal AI)",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="Image files or folders to process (launches GUI if none given and no --text)",
    )
    parser.add_argument("--api-key", help="Fal AI API key (saved for future use)")
    parser.add_argument("--style", choices=style_keys, default=None,
                        help="Visual style preset")
    parser.add_argument("--diagram-type", choices=dt_keys, default=None,
                        help="Target diagram type (for img2img and txt2img)")
    parser.add_argument("--format", choices=["png", "jpeg", "webp"], default="png",
                        help="Output format (default: png)")
    parser.add_argument("--resolution", choices=["0.5K", "1K", "2K", "4K"], default="1K",
                        help="Output resolution (default: 1K)")
    parser.add_argument("--aspect-ratio", choices=ASPECT_RATIOS, default=None,
                        help="Aspect ratio (default: auto)")
    parser.add_argument("--num-images", type=int, choices=[1, 2, 3, 4], default=1,
                        help="Number of variant outputs per image (default: 1)")
    parser.add_argument("--prompt", default=None,
                        help="Freehand prompt (combined with --style and --diagram-type)")
    parser.add_argument("--text", default=None,
                        help="Text-to-image mode: describe the diagram to generate")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for text-to-image (default: ~/Pictures/nano-tech-diagrams)")
    parser.add_argument("--output-name", default="generated_diagram",
                        help="Output filename prefix for text-to-image (default: generated_diagram)")
    parser.add_argument("--whiteboard", action="store_true",
                        help="Whiteboard cleanup mode (adds cleanup instructions to prompt)")
    parser.add_argument("--list-styles", action="store_true",
                        help="List available style presets and exit")
    parser.add_argument("--list-diagram-types", action="store_true",
                        help="List available diagram types and exit")
    parser.add_argument("--gui", action="store_true", help="Force launch the GUI")

    args = parser.parse_args()

    if args.list_styles:
        current_cat = None
        for p in STYLE_PRESETS:
            if p[2] != current_cat:
                current_cat = p[2]
                print(f"\n  {current_cat}:")
            print(f"    {p[0]:25s} {p[1]} (default ratio: {p[4]})")
        print()
        return

    if args.list_diagram_types:
        current_cat = None
        for dt in DIAGRAM_TYPES:
            if dt[2] != current_cat:
                current_cat = dt[2]
                print(f"\n  {current_cat}:")
            print(f"    {dt[0]:25s} {dt[1]}")
        print()
        return

    # GUI mode
    if args.gui or (not args.paths and not args.text):
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

    aspect_ratio = args.aspect_ratio or "auto"
    overrides = config.get("prompt_overrides", {})

    # --- Text-to-image mode ---
    if args.text:
        prompt = build_txt2img_prompt(
            user_prompt=args.text,
            style_key=args.style,
            diagram_type_key=args.diagram_type,
            style_overrides=overrides,
        )

        output_dir = Path(args.output_dir) if args.output_dir else Path.home() / "Pictures" / "nano-tech-diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)

        print("Generating diagram...")
        try:
            images = call_fal_txt2img(
                api_key, prompt, args.format, args.resolution,
                args.num_images, aspect_ratio,
            )
            if not images:
                print("FAILED (no output)", file=sys.stderr)
                sys.exit(1)

            for j, img_data in enumerate(images):
                img_resp = requests.get(img_data["url"], timeout=60)
                img_resp.raise_for_status()
                suffix = "" if len(images) == 1 else f"_{j + 1}"
                out_path = output_dir / f"{args.output_name}{suffix}.{args.format}"
                version = 1
                while out_path.exists():
                    version += 1
                    out_path = output_dir / f"{args.output_name}_{version}{suffix}.{args.format}"
                with open(out_path, "wb") as f:
                    f.write(img_resp.content)
                print(f"  -> {out_path}")

        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        print("Done.")
        return

    # --- Image-to-image mode ---
    images = collect_images(args.paths)
    if not images:
        print("No images found in the given paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(images)} image(s)...")

    for i, img_path in enumerate(images, 1):
        print(f"  [{i}/{len(images)}] {img_path.name} ... ", end="", flush=True)
        try:
            if args.whiteboard:
                style_text = None
                if args.style:
                    style_text = overrides.get(args.style, STYLE_BY_KEY[args.style][3])
                else:
                    style_text = STYLE_BY_KEY["clean_polished"][3]
                prompt = build_whiteboard_prompt(style_text)
                if args.prompt:
                    prompt += f" {args.prompt}"
            else:
                prompt = build_img2img_prompt(
                    user_prompt=args.prompt or "",
                    style_key=args.style,
                    diagram_type_key=args.diagram_type,
                    style_overrides=overrides,
                )

            result_images = call_fal_img2img(
                str(img_path), api_key, prompt,
                args.format, args.resolution, args.num_images, aspect_ratio,
            )
            if not result_images:
                print("FAILED (no output)")
                continue

            out_dir = img_path.parent / "processed"
            out_dir.mkdir(exist_ok=True)
            for j, img_data in enumerate(result_images):
                img_resp = requests.get(img_data["url"], timeout=60)
                img_resp.raise_for_status()
                suffix = "_edited" if len(result_images) == 1 else f"_edited_{j + 1}"
                out_path = out_dir / f"{img_path.stem}{suffix}.{args.format}"
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
