#!/usr/bin/env python3
"""Nano Tech Diagrams - MCP Server for AI-assisted diagram creation and editing.

Exposes tools for whiteboard cleanup, image-to-image transformation, and
text-to-image diagram generation using Nano Banana 2 (via Fal AI).

Run with: python -m nano_tech_diagrams.mcp_server
Or via MCP config: {"command": "python", "args": ["-m", "nano_tech_diagrams.mcp_server"]}
"""

import base64
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .core import (
    DIAGRAM_TYPE_BY_KEY, DIAGRAM_TYPE_CATEGORIES, DIAGRAM_TYPES,
    STYLE_BY_KEY, STYLE_CATEGORIES, STYLE_PRESETS,
    build_img2img_prompt, build_txt2img_prompt, build_whiteboard_prompt,
    call_fal_img2img, call_fal_txt2img, load_config,
)

mcp = FastMCP(
    "Nano Tech Diagrams",
    description="Create and edit tech diagrams using Nano Banana 2 (via Fal AI)",
)


def _get_api_key() -> str:
    """Get API key from config or environment."""
    import os
    key = os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")
    if key:
        return key
    config = load_config()
    key = config.get("api_key")
    if not key:
        raise ValueError(
            "No Fal AI API key found. Set FAL_KEY environment variable or "
            "configure via the Nano Tech Diagrams GUI/CLI."
        )
    return key


@mcp.tool()
def list_styles() -> str:
    """List all available visual style presets with their keys and categories."""
    lines = []
    for cat in STYLE_CATEGORIES:
        lines.append(f"\n{cat}:")
        for p in STYLE_PRESETS:
            if p[2] == cat:
                lines.append(f"  {p[0]:25s} - {p[1]} (default AR: {p[4]})")
    return "\n".join(lines)


@mcp.tool()
def list_diagram_types() -> str:
    """List all available diagram type presets with their keys and categories."""
    lines = []
    for cat in DIAGRAM_TYPE_CATEGORIES:
        lines.append(f"\n{cat}:")
        for dt in DIAGRAM_TYPES:
            if dt[2] == cat:
                lines.append(f"  {dt[0]:25s} - {dt[1]}")
    return "\n".join(lines)


@mcp.tool()
def whiteboard_cleanup(
    image_path: str,
    style: str = "clean_polished",
    dictionary_words: list[str] | None = None,
    output_format: str = "png",
    aspect_ratio: str = "auto",
) -> str:
    """Clean up a whiteboard photo into a polished diagram.

    Args:
        image_path: Path to the whiteboard photo
        style: Visual style preset key (use list_styles to see options)
        dictionary_words: Words/terms to spell correctly (e.g. ["Kubernetes", "Proxmox"])
        output_format: Output format - png, jpeg, or webp
        aspect_ratio: Aspect ratio - auto, 21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16, 4:1, 1:4, 8:1, 1:8
    """
    api_key = _get_api_key()

    if style not in STYLE_BY_KEY:
        return f"Error: Unknown style '{style}'. Use list_styles() to see available options."

    config = load_config()
    overrides = config.get("prompt_overrides", {})
    style_text = overrides.get(style, STYLE_BY_KEY[style][3])
    prompt = build_whiteboard_prompt(style_text, dictionary_words)

    images = call_fal_img2img(
        image_path, api_key, prompt,
        output_format, "1K", 1, aspect_ratio,
    )

    if not images:
        return "Error: No output image returned from API."

    # Save output
    p = Path(image_path)
    out_dir = p.parent / "processed"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{p.stem}_{style}_edited.{output_format}"

    import requests
    img_resp = requests.get(images[0]["url"], timeout=60)
    img_resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(img_resp.content)

    return f"Saved to: {out_path}"


@mcp.tool()
def image_to_image(
    image_path: str,
    prompt: str = "",
    style: str | None = None,
    diagram_type: str | None = None,
    dictionary_words: list[str] | None = None,
    output_format: str = "png",
    aspect_ratio: str = "auto",
) -> str:
    """Transform an existing image into a tech diagram.

    At least one of prompt, style, or diagram_type must be provided.

    Args:
        image_path: Path to the input image
        prompt: Freehand description of desired transformation
        style: Visual style preset key (use list_styles to see options)
        diagram_type: Diagram type key (use list_diagram_types to see options)
        dictionary_words: Words/terms to spell correctly
        output_format: Output format - png, jpeg, or webp
        aspect_ratio: Aspect ratio - auto, 21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16, 4:1, 1:4, 8:1, 1:8
    """
    api_key = _get_api_key()

    if not prompt and not style and not diagram_type:
        return "Error: Provide at least one of: prompt, style, or diagram_type."

    if style and style not in STYLE_BY_KEY:
        return f"Error: Unknown style '{style}'. Use list_styles() to see available options."
    if diagram_type and diagram_type not in DIAGRAM_TYPE_BY_KEY:
        return f"Error: Unknown diagram_type '{diagram_type}'. Use list_diagram_types() to see options."

    config = load_config()
    overrides = config.get("prompt_overrides", {})

    full_prompt = build_img2img_prompt(
        user_prompt=prompt,
        style_key=style,
        diagram_type_key=diagram_type,
        style_overrides=overrides,
        dictionary_words=dictionary_words,
    )

    images = call_fal_img2img(
        image_path, api_key, full_prompt,
        output_format, "1K", 1, aspect_ratio,
    )

    if not images:
        return "Error: No output image returned from API."

    p = Path(image_path)
    out_dir = p.parent / "processed"
    out_dir.mkdir(exist_ok=True)

    suffix_parts = []
    if diagram_type:
        suffix_parts.append(diagram_type)
    if style:
        suffix_parts.append(style)
    suffix = f"_{'_'.join(suffix_parts)}_edited" if suffix_parts else "_edited"
    out_path = out_dir / f"{p.stem}{suffix}.{output_format}"

    import requests
    img_resp = requests.get(images[0]["url"], timeout=60)
    img_resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(img_resp.content)

    return f"Saved to: {out_path}"


@mcp.tool()
def text_to_image(
    prompt: str = "",
    style: str | None = None,
    diagram_type: str | None = None,
    output_dir: str | None = None,
    output_name: str = "generated_diagram",
    output_format: str = "png",
    aspect_ratio: str = "auto",
) -> str:
    """Generate a tech diagram from a text description (no input image needed).

    At least one of prompt, style, or diagram_type must be provided.

    Args:
        prompt: Description of the diagram to generate
        style: Visual style preset key (use list_styles to see options)
        diagram_type: Diagram type key (use list_diagram_types to see options)
        output_dir: Directory to save output (default: ~/Pictures/nano-tech-diagrams)
        output_name: Filename prefix for the output
        output_format: Output format - png, jpeg, or webp
        aspect_ratio: Aspect ratio - auto, 21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16, 4:1, 1:4, 8:1, 1:8
    """
    api_key = _get_api_key()

    if not prompt and not style and not diagram_type:
        return "Error: Provide at least one of: prompt, style, or diagram_type."

    if style and style not in STYLE_BY_KEY:
        return f"Error: Unknown style '{style}'. Use list_styles() to see available options."
    if diagram_type and diagram_type not in DIAGRAM_TYPE_BY_KEY:
        return f"Error: Unknown diagram_type '{diagram_type}'. Use list_diagram_types() to see options."

    config = load_config()
    overrides = config.get("prompt_overrides", {})

    full_prompt = build_txt2img_prompt(
        user_prompt=prompt,
        style_key=style,
        diagram_type_key=diagram_type,
        style_overrides=overrides,
    )

    images = call_fal_txt2img(
        api_key, full_prompt,
        output_format, "1K", 1, aspect_ratio,
    )

    if not images:
        return "Error: No output image returned from API."

    out_dir = Path(output_dir) if output_dir else Path.home() / "Pictures" / "nano-tech-diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{output_name}.{output_format}"
    version = 1
    while out_path.exists():
        version += 1
        out_path = out_dir / f"{output_name}_{version}.{output_format}"

    import requests
    img_resp = requests.get(images[0]["url"], timeout=60)
    img_resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(img_resp.content)

    return f"Saved to: {out_path}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
