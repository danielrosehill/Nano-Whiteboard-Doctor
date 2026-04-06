# Nano Tech Diagrams

A tool for creating and editing tech diagrams using [Fal AI's Nano Banana 2](https://fal.ai/models/fal-ai/nano-banana-2) model. Available as a desktop GUI (Python/PyQt6), CLI, MCP server (Python), and npm package with MCP server (TypeScript).

![Python](https://img.shields.io/badge/python-3.10+-blue)
![npm](https://img.shields.io/badge/npm-nano--tech--diagrams-red)
![License](https://img.shields.io/badge/license-MIT-green)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52)

## Before & After

### Chalkboard Style
![Chalkboard before/after](samples/demo1_before_comparison_chalkboard.png)

### Blueprint Style
![Blueprint before/after](samples/demo2_before_comparison_blueprint.png)

### Pixel Art Style
![Pixel Art before/after](samples/demo3_before_comparison_pixel-art.png)

### Neon Sign Style
![Neon Sign before/after](samples/030426_comparison_neon-sign.png)

### Corporate Clean Style
![Corporate Clean before/after](samples/IMG20260405125048_comparison_corporate-clean.png)

More samples available in the [Sample-Whiteboards](https://github.com/danielrosehill/Sample-Whiteboards) companion repo.

## What It Does

- **Text-to-image**: Generate tech diagrams from text descriptions
- **Image-to-image**: Transform existing images into styled diagrams
- **Whiteboard cleanup**: Clean up whiteboard photos into polished graphics
- **28+ style presets** across 6 categories
- **20 diagram type presets** (network, flowchart, mind map, K8s cluster, etc.)

## MCP Server (npm)

### Install via Claude Code

```bash
claude mcp add nano-tech-diagrams -e FAL_KEY=your-fal-api-key -- npx -y nano-tech-diagrams
```

### Manual JSON config

Add to your Claude Code MCP settings (`~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "nano-tech-diagrams": {
      "command": "npx",
      "args": ["-y", "nano-tech-diagrams"],
      "env": {
        "FAL_KEY": "your-fal-api-key"
      }
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `list_styles` | List all 28+ visual style presets |
| `list_diagram_types` | List all diagram type presets |
| `whiteboard_cleanup` | Clean up a whiteboard photo into a polished diagram |
| `image_to_image` | Transform an image into a styled tech diagram |
| `text_to_image` | Generate a diagram from a text description |

### Defaults

- **Model**: Nano Banana 2 (baked in)
- **Resolution**: 1K
- **Reasoning**: Minimal
- **Output format**: PNG
- **Aspect ratio**: auto (configurable per call)

## Desktop GUI (Python)

### Install from source

```bash
git clone https://github.com/danielrosehill/Nano-Whiteboard-Doctor.git
cd Nano-Whiteboard-Doctor
uv sync
uv run nano-tech-diagrams
```

### Install from .deb

Download the `.deb` from [Releases](https://github.com/danielrosehill/Nano-Whiteboard-Doctor/releases):

```bash
sudo dpkg -i nano-tech-diagrams_0.3.0_all.deb
nano-tech-diagrams
```

### GUI Usage

1. Click **Add Images** or drag and drop whiteboard photos
2. (Optional) **Double-click** an image to add a word dictionary for tricky terms
3. Choose a **Style Preset** from the dropdown (or write a custom prompt)
4. (Optional) Adjust output format, resolution, and aspect ratio
5. Click **Process**
6. **Click any result thumbnail** to view it full-size
7. From the enlarged view, click **Send Back for Touchups** to re-process

![GUI](screenshot/gui.png)

## CLI

```bash
# Text-to-image
nano-tech-diagrams --text "Kubernetes cluster with 3 worker nodes" --style blueprint --diagram-type kubernetes_cluster

# Image-to-image
nano-tech-diagrams photo.jpg --style corporate_clean

# Whiteboard cleanup
nano-tech-diagrams whiteboard.jpg --whiteboard --style clean_polished

# List presets
nano-tech-diagrams --list-styles
nano-tech-diagrams --list-diagram-types
```

## Style Presets

### Professional

| Preset | Description |
|--------|-------------|
| Clean & Polished | Clear labels and icons on a white background -- the default |
| Corporate Clean | Minimalist corporate slide-ready diagram |
| Hand-Drawn Polished | Refined sketch -- designer's notebook feel |
| Minimalist Mono | Black and white, Bauhaus-inspired minimalism |
| Ultra Sleek | Thin lines, Swiss design aesthetic |
| Blog Hero | Gradient background, 16:9 blog featured image |

### Creative

| Preset | Description |
|--------|-------------|
| Colorful Infographic | Bold, vibrant infographic with rich colors |
| Comic Book | Graphic novel panel with ink outlines and Ben-Day dots |
| Isometric 3D | Isometric 3D-style boxes and depth |
| Neon Sign | Glowing neon tubes on a dark brick wall |
| Pastel Kawaii | Soft pastel palette with cute rounded forms |
| Pixel Art | Retro 16-bit pixel art style |
| Stained Glass | Cathedral stained glass with jewel tones |
| Sticky Notes | Colorful sticky notes on a cork board |
| Watercolor Artistic | Watercolor painting on textured paper |

### Technical

| Preset | Description |
|--------|-------------|
| Blueprint | Architectural blueprint on deep blue background |
| Dark Mode Technical | Engineering diagram on dark background |
| Flat Material | Google Material Design flat UI style |
| GitHub README | Markdown-friendly, repo architecture overview |
| Photographic 3D | Photorealistic 3D render with glass and metal |
| Terminal Hacker | Green-on-black phosphor CRT terminal |
| Visionary Inspirational | Cosmic/futurist keynote aesthetic |

### Retro & Fun

| Preset | Description |
|--------|-------------|
| Chalkboard | Classic green chalkboard with chalk texture |
| Eccentric Psychedelic | Wild psychedelic maximum saturation |
| Mad Genius | Chaotic beautiful-mind inventor's notebook |
| Retro 80s Synthwave | Neon 1980s synthwave with grid lines |
| Woodcut | Medieval woodcut/linocut print on parchment |

### Language

| Preset | Description |
|--------|-------------|
| Bilingual Hebrew | English + Hebrew labels side by side |
| Translated Hebrew | Fully translated to Hebrew with RTL layout |

## Diagram Types

| Category | Types |
|----------|-------|
| Infrastructure | Network Diagram, Cloud Architecture, Kubernetes Cluster, Server Rack |
| Software | System Architecture, Microservices Map, API Architecture, Database Schema |
| Process | Flowchart, Decision Tree, Sequence Diagram, State Machine, CI/CD Pipeline |
| Conceptual | Mind Map, Wireframe, Gantt Chart, Comparison Table, Org Chart |

## Configuration

- **API Key**: Set `FAL_KEY` env var, or stored in `~/.config/nano-tech-diagrams/config.json`
- **Output Format**: PNG (default), JPEG, or WebP
- **Resolution**: 0.5K, 1K (default), 2K, or 4K
- **Aspect Ratio**: auto (default), 1:1, 4:3, 3:4, 16:9, 9:16, 3:2, 2:3, 21:9, 9:21

Get a Fal AI API key at [fal.ai](https://fal.ai).

## License

MIT
