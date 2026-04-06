#!/usr/bin/env node
/**
 * Nano Tech Diagrams - MCP Server
 *
 * Exposes tools for whiteboard cleanup, image-to-image transformation, and
 * text-to-image diagram generation using Nano Banana 2 (via Fal AI).
 *
 * Reasoning is set to minimal by default. Default resolution is 1K.
 */

import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname } from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import {
  STYLE_PRESETS, DIAGRAM_TYPES, STYLE_BY_KEY, DIAGRAM_TYPE_BY_KEY,
  callFalImg2Img, callFalTxt2Img,
  buildWhiteboardPrompt, buildImg2ImgPrompt, buildTxt2ImgPrompt,
} from "./core.js";

function getApiKey(): string {
  const key = process.env.FAL_KEY || process.env.FAL_AI_API_KEY;
  if (!key) {
    throw new Error(
      "No Fal AI API key found. Set FAL_KEY or FAL_AI_API_KEY environment variable.",
    );
  }
  return key;
}

async function downloadImage(url: string, outPath: string): Promise<void> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Failed to download image: ${resp.status}`);
  const buffer = Buffer.from(await resp.arrayBuffer());
  writeFileSync(outPath, buffer);
}

const server = new McpServer({
  name: "nano-tech-diagrams",
  version: "0.4.0",
});

/**
 * Format a successful generation result. By default returns the fal.media URL
 * (robust across sandboxed environments). If `download_to` is provided, the
 * image is also saved locally and the path is included in the response.
 */
async function formatResult(
  imageUrl: string,
  downloadTo?: string,
): Promise<{ content: Array<{ type: "text"; text: string }> }> {
  const lines = [`Image URL: ${imageUrl}`];
  if (downloadTo) {
    try {
      const dir = dirname(downloadTo);
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
      await downloadImage(imageUrl, downloadTo);
      lines.push(`Saved to: ${downloadTo}`);
    } catch (err) {
      lines.push(`Download failed: ${(err as Error).message}`);
    }
  }
  return { content: [{ type: "text", text: lines.join("\n") }] };
}

// --- list_styles ---

server.tool(
  "list_styles",
  "List all available visual style presets with their keys and categories",
  {},
  async () => {
    const categories = [...new Set(STYLE_PRESETS.map((s) => s.category))];
    const lines: string[] = [];
    for (const cat of categories) {
      lines.push(`\n${cat}:`);
      for (const s of STYLE_PRESETS.filter((p) => p.category === cat)) {
        lines.push(`  ${s.key.padEnd(25)} - ${s.displayName} (default AR: ${s.defaultAspectRatio})`);
      }
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  },
);

// --- list_diagram_types ---

server.tool(
  "list_diagram_types",
  "List all available diagram type presets with their keys and categories",
  {},
  async () => {
    const categories = [...new Set(DIAGRAM_TYPES.map((d) => d.category))];
    const lines: string[] = [];
    for (const cat of categories) {
      lines.push(`\n${cat}:`);
      for (const d of DIAGRAM_TYPES.filter((dt) => dt.category === cat)) {
        lines.push(`  ${d.key.padEnd(25)} - ${d.displayName}`);
      }
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  },
);

// --- whiteboard_cleanup ---

server.tool(
  "whiteboard_cleanup",
  "Clean up a whiteboard photo into a polished diagram using Nano Banana 2",
  {
    image_path: z.string().describe("Path to the whiteboard photo"),
    style: z.string().default("clean_polished").describe("Visual style preset key (use list_styles to see options)"),
    dictionary_words: z.array(z.string()).optional().describe("Words/terms to spell correctly (e.g. ['Kubernetes', 'Proxmox'])"),
    output_format: z.enum(["png", "jpeg", "webp"]).default("png").describe("Output format"),
    resolution: z.enum(["0.5K", "1K", "2K", "4K"]).default("1K").describe("Output resolution (default: 1K)"),
    aspect_ratio: z.string().default("auto").describe("Aspect ratio - auto, 1:1, 4:3, 16:9, 9:16, 3:2, 2:3, 21:9, 9:21"),
    download_to: z.string().optional().describe("Optional local path to also save the image. If omitted, only the fal.media URL is returned."),
  },
  async ({ image_path, style, dictionary_words, output_format, resolution, aspect_ratio, download_to }) => {
    const apiKey = getApiKey();

    const stylePreset = STYLE_BY_KEY.get(style);
    if (!stylePreset) {
      return { content: [{ type: "text", text: `Error: Unknown style '${style}'. Use list_styles to see available options.` }] };
    }

    const prompt = buildWhiteboardPrompt(stylePreset.prompt, dictionary_words);
    const images = await callFalImg2Img(image_path, apiKey, prompt, output_format, resolution, 1, aspect_ratio);

    if (!images.length) {
      return { content: [{ type: "text", text: "Error: No output image returned from API." }] };
    }

    return formatResult(images[0].url, download_to);
  },
);

// --- image_to_image ---

server.tool(
  "image_to_image",
  "Transform an existing image into a tech diagram using Nano Banana 2. At least one of prompt, style, or diagram_type must be provided.",
  {
    image_path: z.string().describe("Path to the input image"),
    prompt: z.string().default("").describe("Freehand description of desired transformation"),
    style: z.string().optional().describe("Visual style preset key (use list_styles to see options)"),
    diagram_type: z.string().optional().describe("Diagram type key (use list_diagram_types to see options)"),
    dictionary_words: z.array(z.string()).optional().describe("Words/terms to spell correctly"),
    output_format: z.enum(["png", "jpeg", "webp"]).default("png").describe("Output format"),
    resolution: z.enum(["0.5K", "1K", "2K", "4K"]).default("1K").describe("Output resolution (default: 1K)"),
    aspect_ratio: z.string().default("auto").describe("Aspect ratio - auto, 1:1, 4:3, 16:9, 9:16, 3:2, 2:3, 21:9, 9:21"),
    download_to: z.string().optional().describe("Optional local path to also save the image. If omitted, only the fal.media URL is returned."),
  },
  async ({ image_path, prompt, style, diagram_type, dictionary_words, output_format, resolution, aspect_ratio, download_to }) => {
    const apiKey = getApiKey();

    if (!prompt && !style && !diagram_type) {
      return { content: [{ type: "text", text: "Error: Provide at least one of: prompt, style, or diagram_type." }] };
    }
    if (style && !STYLE_BY_KEY.has(style)) {
      return { content: [{ type: "text", text: `Error: Unknown style '${style}'. Use list_styles to see options.` }] };
    }
    if (diagram_type && !DIAGRAM_TYPE_BY_KEY.has(diagram_type)) {
      return { content: [{ type: "text", text: `Error: Unknown diagram_type '${diagram_type}'. Use list_diagram_types to see options.` }] };
    }

    const fullPrompt = buildImg2ImgPrompt({
      userPrompt: prompt, styleKey: style, diagramTypeKey: diagram_type,
      dictionaryWords: dictionary_words,
    });

    const images = await callFalImg2Img(image_path, apiKey, fullPrompt, output_format, resolution, 1, aspect_ratio);

    if (!images.length) {
      return { content: [{ type: "text", text: "Error: No output image returned from API." }] };
    }

    return formatResult(images[0].url, download_to);
  },
);

// --- text_to_image ---

server.tool(
  "text_to_image",
  "Generate a tech diagram from a text description (no input image needed) using Nano Banana 2. At least one of prompt, style, or diagram_type must be provided.",
  {
    prompt: z.string().default("").describe("Description of the diagram to generate"),
    style: z.string().optional().describe("Visual style preset key (use list_styles to see options)"),
    diagram_type: z.string().optional().describe("Diagram type key (use list_diagram_types to see options)"),
    download_to: z.string().optional().describe("Optional local path to also save the image. If omitted, only the fal.media URL is returned."),
    output_format: z.enum(["png", "jpeg", "webp"]).default("png").describe("Output format"),
    resolution: z.enum(["0.5K", "1K", "2K", "4K"]).default("1K").describe("Output resolution (default: 1K)"),
    aspect_ratio: z.string().default("auto").describe("Aspect ratio - auto, 1:1, 4:3, 16:9, 9:16, 3:2, 2:3, 21:9, 9:21"),
  },
  async ({ prompt, style, diagram_type, download_to, output_format, resolution, aspect_ratio }) => {
    const apiKey = getApiKey();

    if (!prompt && !style && !diagram_type) {
      return { content: [{ type: "text", text: "Error: Provide at least one of: prompt, style, or diagram_type." }] };
    }
    if (style && !STYLE_BY_KEY.has(style)) {
      return { content: [{ type: "text", text: `Error: Unknown style '${style}'. Use list_styles to see options.` }] };
    }
    if (diagram_type && !DIAGRAM_TYPE_BY_KEY.has(diagram_type)) {
      return { content: [{ type: "text", text: `Error: Unknown diagram_type '${diagram_type}'. Use list_diagram_types to see options.` }] };
    }

    const fullPrompt = buildTxt2ImgPrompt({
      userPrompt: prompt, styleKey: style, diagramTypeKey: diagram_type,
    });

    const images = await callFalTxt2Img(apiKey, fullPrompt, output_format, resolution, 1, aspect_ratio);

    if (!images.length) {
      return { content: [{ type: "text", text: "Error: No output image returned from API." }] };
    }

    return formatResult(images[0].url, download_to);
  },
);

// --- Start server ---

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
