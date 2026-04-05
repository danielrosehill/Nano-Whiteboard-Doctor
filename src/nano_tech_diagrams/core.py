"""Nano Tech Diagrams - Core library for creating and editing tech diagrams with Nano Banana 2 (via Fal AI)."""

import base64
import json
import shutil
import time
from pathlib import Path

import requests

# --- Config ---

OLD_CONFIG_DIRS = [
    Path.home() / ".config" / "nano-whiteboard-doctor",
    Path.home() / ".config" / "whiteboard-makeover",
]
CONFIG_DIR = Path.home() / ".config" / "nano-tech-diagrams"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_VERSION = 5

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _migrate_config_dir():
    """One-time migration from previous config directory names."""
    if CONFIG_DIR.exists():
        return
    for old_dir in reversed(OLD_CONFIG_DIRS):
        if old_dir.is_dir():
            shutil.copytree(str(old_dir), str(CONFIG_DIR))
            (old_dir / ".migrated_to_nano_tech_diagrams").touch()
            return


_migrate_config_dir()


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    if cfg.get("config_version", 0) < CONFIG_VERSION:
        cfg.setdefault("color", True)
        cfg.setdefault("handwritten", True)
        cfg.setdefault("prompt_overrides", {})
        cfg["config_version"] = CONFIG_VERSION
        save_config(cfg)
    return cfg


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# --- Aspect Ratios ---

ASPECT_RATIOS = ["auto", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9", "9:21"]

# --- Whiteboard-specific instructions (prepended only in whiteboard mode) ---

WHITEBOARD_INSTRUCTIONS = (
    "Remove the physical whiteboard, markers, frame, and any background elements. "
    "Correct any perspective distortion so the output appears as a perfectly "
    "straight-on, top-down view regardless of the angle the original photo was taken from. "
    "Preserve all the original content, text, and diagrams. "
    "Where handwriting is ambiguous, infer the correct spelling from context rather than "
    "reproducing the raw strokes literally -- for example, a word that looks like "
    "'proxknox' should be rendered as 'Proxmox' if that is the obvious intended meaning."
)

# --- Style Presets (visual style only, no whiteboard-specific language) ---
# Each tuple: (key, display_name, category, style_prompt, default_aspect_ratio)

STYLE_PRESETS = [
    # --- Professional ---
    ("clean_polished", "Clean & Polished", "Professional",
     "Render as a beautiful and polished graphic featuring clear labels and icons "
     "on a clean white background. Content should be legible and well-organized with "
     "a clear visual hierarchy. Use clean shapes, consistent line weights, and a "
     "professional color palette. The result should be visually attractive and easy "
     "to understand.",
     "auto"),

    ("corporate_clean", "Corporate Clean", "Professional",
     "Render as a clean, minimalist corporate diagram suitable for a professional "
     "presentation. Use a restrained color palette of navy blue, grey, and one accent "
     "color. Shapes should be clean geometric forms with a modern sans-serif font for "
     "all text and simple flat icons where appropriate. The result should look like it "
     "came from a polished slide deck -- professional, understated, and immediately "
     "readable.",
     "16:9"),

    ("hand_drawn_polished", "Hand-Drawn Polished", "Professional",
     "Render in a polished hand-drawn style on a clean white or light cream background. "
     "Keep an organic, hand-drawn character but refine it -- smoother lines, consistent "
     "stroke weight, better spacing, and cleaner handwriting that is still clearly "
     "handwritten. Add soft watercolor-style fills or gentle color washes to different "
     "sections. The result should feel like a carefully crafted sketch in a designer's "
     "notebook -- warm, human, and thoughtfully composed.",
     "auto"),

    ("minimalist_mono", "Minimalist Mono", "Professional",
     "Render as a stark, minimalist black-and-white diagram on a pure white background. "
     "Use only black lines, shapes, and text -- no color, no gradients, no fills. Lines "
     "should be clean and uniform weight. Use a simple, elegant sans-serif font. Maximize "
     "whitespace and let the structure breathe. The result should be austere and elegant "
     "-- like a diagram in an academic paper or a Dieter Rams design specification.",
     "auto"),

    ("ultra_sleek", "Ultra Sleek", "Professional",
     "Render as an ultra-sleek, refined diagram with elegant precision on a pure white "
     "background with generous margins. Use extremely thin, hairline-weight lines in "
     "dark grey or black. Shapes should be geometric and perfectly aligned with consistent "
     "spacing. Use a single subtle accent color -- a muted teal or steel blue -- sparingly "
     "for key elements only. Text should be set in an ultra-light weight, elegant sans-serif "
     "font with generous letter spacing. Maximize negative space. The result should feel "
     "like it was designed by a Swiss typographer -- razor-sharp and effortlessly sophisticated.",
     "auto"),

    ("blog_hero", "Blog Hero", "Professional",
     "Render as a polished diagram suitable as a blog post hero image on a soft gradient "
     "background that transitions from light blue-grey at the top to white at the bottom. "
     "Use a modern, approachable color palette with one strong brand color (a confident "
     "blue or teal) and supporting warm greys. Shapes should have subtle rounded corners "
     "and light drop shadows for depth. Use a clean, highly readable sans-serif font. Add "
     "simple line icons that reinforce each concept. Include generous padding around the "
     "entire diagram. The result should be a polished image ready to drop into a blog post "
     "-- professional and inviting to click.",
     "16:9"),

    # --- Creative ---
    ("colorful_infographic", "Colorful Infographic", "Creative",
     "Render as a bold, vibrant infographic-style diagram on a clean white background. "
     "Use a rich, vibrant color palette with distinct colors for different sections or "
     "concepts. Add colorful icons, rounded shapes, and visual hierarchy through size "
     "and color contrast. Text should be clear and legible in a friendly, rounded font. "
     "The result should feel energetic and engaging -- like a well-designed infographic "
     "you'd want to share.",
     "auto"),

    ("comic_book", "Comic Book", "Creative",
     "Render in a bold comic book illustration style with thick black ink outlines, "
     "Ben-Day dot shading patterns, and a vivid primary color palette of red, blue, "
     "yellow, and green. Text should appear in comic-style lettering with key labels in "
     "speech bubbles or caption boxes. Add dynamic action lines and POW/ZAP-style emphasis "
     "marks around important connections. The result should look like a page ripped from a "
     "tech-themed graphic novel -- bold, punchy, and impossible to scroll past.",
     "3:4"),

    ("isometric_3d", "Isometric 3D", "Creative",
     "Render as an isometric 3D-style diagram on a clean white background. Render boxes "
     "and containers as isometric 3D blocks with subtle depth and soft shadows. Use a "
     "modern, cheerful color palette with distinct colors for different components. Arrows "
     "and connectors should follow isometric angles. Labels should float cleanly above "
     "their elements. The result should look like a polished isometric tech illustration "
     "-- the kind you'd see in a modern SaaS landing page or developer documentation.",
     "4:3"),

    ("neon_sign", "Neon Sign", "Creative",
     "Render as glowing neon signs mounted on a dark exposed-brick wall background. "
     "All lines, shapes, and text should be glowing neon tubes in different colors -- pink, "
     "blue, white, and yellow. Each neon element should have a realistic glow effect with "
     "soft light bleeding onto the brick wall behind it. Connectors and arrows should be "
     "continuous neon tube bends. The result should look like an elaborate neon sign "
     "installation in a trendy bar -- atmospheric, eye-catching, and unmistakably cool.",
     "auto"),

    ("pastel_kawaii", "Pastel Kawaii", "Creative",
     "Render in an adorable pastel-colored kawaii illustration style on a soft pastel pink "
     "or lavender background. Use a soft pastel palette -- baby pink, mint green, lavender, "
     "peach, and sky blue. Shapes should have rounded, bubbly forms with thick soft outlines. "
     "Add tiny decorative elements like stars, sparkles, or small cloud accents. Use a cute, "
     "rounded handwriting-style font. The result should be charming and delightful -- like a "
     "page from a Japanese stationery notebook that still clearly communicates the diagram.",
     "auto"),

    ("pixel_art", "Pixel Art", "Creative",
     "Render as a pixel art-styled diagram reminiscent of 16-bit era video games on a clean "
     "background. Render all elements using visible, chunky pixels with a limited retro "
     "color palette. Shapes should be blocky with aliased edges. Text should use a pixel "
     "font. Add small pixel-art icons -- tiny servers, computers, clouds, gears -- next to "
     "relevant labels. Use dithering patterns for shading. The result should look like a UI "
     "screen from a classic strategy or simulation game -- charming and nostalgic.",
     "1:1"),

    ("stained_glass", "Stained Glass", "Creative",
     "Render as a stained glass window. Each section should be a pane of translucent "
     "colored glass with thick dark lead came lines separating them. Use rich jewel tones "
     "-- deep ruby, sapphire blue, emerald green, amber gold -- with light appearing to "
     "shine through the glass. Text should be integrated into the glass panes in a gothic "
     "or art nouveau lettering style. The result should look like a magnificent stained "
     "glass window depicting a technical diagram -- luminous, ornate, and strikingly beautiful.",
     "3:4"),

    ("sticky_notes", "Sticky Notes", "Creative",
     "Render as a colorful sticky-note style diagram on a light cork-board or soft beige "
     "textured background. Each concept, box, or grouping should be a colored sticky note "
     "(yellow, pink, blue, green) with a slight shadow and subtle rotation for a natural "
     "look. Use a casual handwritten-style font for text on the notes. Arrows and connectors "
     "should look like hand-drawn marker lines between the notes. The result should feel "
     "like a beautifully organized brainstorming board -- collaborative and approachable.",
     "4:3"),

    ("watercolor", "Watercolor Artistic", "Creative",
     "Render as a beautiful watercolor-style illustrated diagram on a textured watercolor "
     "paper background. Paint each section and shape with soft, translucent watercolor "
     "washes in a harmonious palette of warm and cool tones. Lines should have an ink-pen "
     "quality -- thin, confident, and slightly organic. Text should be rendered in elegant "
     "calligraphic handwriting. The result should look like a page from a beautifully "
     "illustrated journal -- artistic, expressive, and unique.",
     "auto"),

    # --- Technical ---
    ("blueprint", "Blueprint", "Technical",
     "Render as an architectural blueprint on a deep blue background. Use white and light "
     "blue lines for all shapes, arrows, and connectors. Text should appear in a clean "
     "technical drafting font. Add dimension-line styling to connectors and subtle "
     "cross-hatch fills where appropriate. The result should look like a precise "
     "engineering blueprint -- technical, authoritative, and classic.",
     "auto"),

    ("dark_mode", "Dark Mode Technical", "Technical",
     "Render as a technical diagram with a dark charcoal or near-black background. Use "
     "light-colored text (white or light grey) and neon or high-contrast accent colors "
     "like cyan, green, and orange for lines, arrows, and highlights. Use a monospace or "
     "technical font for labels. Add subtle grid lines or dot patterns in the background. "
     "The result should look like a technical blueprint or engineering schematic -- precise, "
     "detailed, and developer-friendly.",
     "auto"),

    ("flat_material", "Flat Material", "Technical",
     "Render as a flat Material Design-styled diagram on a clean light grey (#FAFAFA) "
     "background. Use the Material Design color palette -- primary blues, teals, and deep "
     "oranges with clean flat fills and subtle elevation shadows on cards and containers. "
     "Round the corners of all shapes. Use a Roboto-style sans-serif font for all text. "
     "Icons should be simple outlined material-style icons. The result should look like a "
     "screen from a well-designed Android app -- clean, systematic, and modern.",
     "auto"),

    ("github_readme", "GitHub README", "Technical",
     "Render as a clean diagram optimized for GitHub README files on a pure white background "
     "with clean edges and no border. Use GitHub's familiar color palette -- blues (#0969DA), "
     "greens (#1A7F37), purples (#8250DF), and neutral greys. Shapes should be clean rounded "
     "rectangles with subtle borders. Use a system sans-serif font. Add simple, recognizable "
     "developer icons (git branches, terminal prompts, API endpoints, databases). The result "
     "should look like a native GitHub diagram that blends seamlessly into a README.",
     "16:9"),

    ("photographic", "Photographic 3D", "Technical",
     "Render as a photorealistic 3D diagram on a clean surface like a light wooden desk or "
     "frosted glass table, shot from directly above. Each box, container, or concept should "
     "be a physical object -- glossy acrylic blocks, frosted glass cards, or brushed metal "
     "plates with realistic reflections and soft shadows. Arrows and connectors should look "
     "like thin metal rods or illuminated fiber-optic strips. Text should appear etched, "
     "printed, or embossed on the surfaces. Use studio-quality lighting with soft diffusion. "
     "The result should look like a product photograph of a physical scale model.",
     "4:3"),

    ("terminal_hacker", "Terminal Hacker", "Technical",
     "Render as a retro computer terminal display on a pure black background. Use phosphor "
     "green (#00FF00) as the primary color for all text, lines, and shapes. Add a subtle "
     "CRT scan-line effect and slight screen curvature glow at the edges. Use a monospace "
     "terminal font for all text. Boxes should be drawn with ASCII-style borders. The result "
     "should look like output from a 1980s mainframe terminal -- minimal, technical, and "
     "unmistakably computer-native.",
     "4:3"),

    ("visionary", "Visionary Inspirational", "Technical",
     "Render as a grand, visionary-style diagram on a deep space or cosmic gradient "
     "background (dark blues and purples with subtle star fields or nebula wisps). Render "
     "concepts as glowing nodes connected by luminous pathways of light. Use a palette of "
     "gold, white, and ethereal blue. Text should be clean and luminous, as if projected "
     "in light. Add subtle lens flare effects and soft radial glows around key concepts. "
     "The result should feel epic and aspirational -- like a strategic roadmap presented "
     "at a visionary keynote.",
     "16:9"),

    # --- Retro & Fun ---
    ("chalkboard", "Chalkboard", "Retro & Fun",
     "Render as if drawn on a classic green chalkboard with a dark green chalkboard-textured "
     "background with subtle chalk dust. Use white and colored chalk (yellow, pink, light "
     "blue) for all lines, shapes, and text. The lettering should look like clean chalk "
     "handwriting. Add subtle smudge effects and chalk texture to lines. The result should "
     "feel like a beautifully organized lecture -- academic, warm, and intellectual.",
     "16:9"),

    ("psychedelic", "Eccentric Psychedelic", "Retro & Fun",
     "Render in a wild, psychedelic style bursting with color. Use intensely saturated, "
     "clashing colors -- electric purples, acid greens, hot magentas, deep oranges -- with "
     "swirling gradients and color bleeds between sections. Lines should pulse with energy, "
     "varying in thickness and color. Add organic, flowing patterns and mandala-like "
     "decorative fills inside shapes. Text should be bold and wavy, distorted slightly but "
     "still readable. The background should be a shifting kaleidoscope of color. The result "
     "should feel like a 1960s concert poster -- overwhelming, hypnotic, and unforgettable.",
     "1:1"),

    ("mad_genius", "Mad Genius", "Retro & Fun",
     "Render as a chaotic, sprawling mad-genius-style diagram on a slightly yellowed, aged "
     "paper background with coffee stain marks and creased folds. Amplify the chaos -- "
     "frantic and varied handwriting sizes, scribbled annotations in margins, multiple "
     "underlines, aggressively circled key concepts, arrows that loop and cross over each "
     "other. Use red ink for emphatic corrections and blue ink for main content. Scatter "
     "small doodles, question marks, and exclamation points in empty spaces. The result "
     "should look like the notebook of a brilliant but unhinged mind -- feverish, obsessive, "
     "and crackling with intellectual energy.",
     "auto"),

    ("retro_80s", "Retro 80s Synthwave", "Retro & Fun",
     "Render as a retro 1980s synthwave-styled diagram on a dark purple-to-black gradient "
     "background. Use hot pink, electric cyan, and neon yellow for lines, shapes, and text. "
     "Add subtle scan-line effects and a retro grid perspective floor fading into the "
     "background. Use a bold, blocky retro font for all labels. The result should feel like "
     "a tech diagram from an 80s sci-fi movie -- glowing, vibrant, and unmistakably "
     "retro-futuristic.",
     "16:9"),

    ("woodcut", "Woodcut", "Retro & Fun",
     "Render as a medieval woodcut or linocut print on an aged parchment or cream-colored "
     "background. Use bold black carved lines with visible wood-grain texture in the strokes. "
     "Use cross-hatching for shading and fills. Text should appear in a blackletter or "
     "old-style serif typeface. Shapes should have a rough, hand-carved quality. Optionally "
     "add a single spot color (a deep red or ochre) for emphasis on key elements. The result "
     "should look like a page from an illuminated technical manuscript -- ancient, "
     "authoritative, and delightfully absurd as a format for modern tech diagrams.",
     "auto"),

    # --- Language ---
    ("bilingual_hebrew", "Bilingual (Hebrew)", "Language",
     "Render with all existing English labels kept in place, and add Hebrew translations "
     "below or beside each label in a slightly smaller font. Hebrew text should read "
     "right-to-left and use clear, modern Hebrew typography. Use color coding to visually "
     "distinguish the two languages -- for example, dark grey for English and blue for "
     "Hebrew. The result should be a clean, professional bilingual diagram that is fully "
     "readable in both English and Hebrew. Use a clean white background.",
     "auto"),

    ("translated_hebrew", "Translated (Hebrew)", "Language",
     "Render with all text labels translated to Hebrew. Preserve all diagram structure, "
     "shapes, arrows, and layout -- but replace every English text label with its Hebrew "
     "translation. Hebrew text should read right-to-left and use clear, modern Hebrew "
     "typography. Ensure translated labels fit naturally within their shapes and containers. "
     "Use clean, professional styling with colorful icons and clear visual hierarchy on a "
     "clean white background. The result should be a fully Hebrew-language version that "
     "reads naturally for a Hebrew speaker.",
     "auto"),
]

# --- Diagram Type Presets (what kind of diagram to create/transform into) ---
# Each tuple: (key, display_name, category, type_prompt, default_aspect_ratio)

DIAGRAM_TYPES = [
    # --- Infrastructure & Networking ---
    ("network_diagram", "Network Diagram", "Infrastructure",
     "Create a network architecture diagram showing hosts, routers, switches, firewalls, "
     "and connections between them. Use standard networking iconography. Show network "
     "segments, subnets, and data flow directions with labeled connections.",
     "16:9"),

    ("cloud_architecture", "Cloud Architecture", "Infrastructure",
     "Create a cloud infrastructure architecture diagram showing cloud services, regions, "
     "availability zones, and their interconnections. Use recognizable cloud service icons "
     "(compute, storage, database, networking). Show data flow and service dependencies.",
     "16:9"),

    ("kubernetes_cluster", "Kubernetes Cluster", "Infrastructure",
     "Create a Kubernetes cluster diagram showing nodes, pods, services, ingress "
     "controllers, namespaces, and persistent volumes. Use standard Kubernetes iconography. "
     "Show the relationship between deployments, replica sets, and pods.",
     "16:9"),

    ("server_rack", "Server Rack / Data Center", "Infrastructure",
     "Create a data center or server rack diagram showing physical or logical server "
     "layout, storage arrays, network switches, and cabling. Show redundancy paths "
     "and failover connections.",
     "3:4"),

    # --- Software & Systems ---
    ("system_architecture", "System Architecture", "Software",
     "Create a software system architecture diagram showing major components, services, "
     "APIs, databases, and message queues. Show how data flows between components. "
     "Distinguish between frontend, backend, and data layers.",
     "16:9"),

    ("microservices", "Microservices Map", "Software",
     "Create a microservices architecture diagram showing individual services, API "
     "gateways, service mesh, message brokers, and databases. Show synchronous and "
     "asynchronous communication patterns between services.",
     "16:9"),

    ("api_architecture", "API Architecture", "Software",
     "Create an API architecture diagram showing endpoints, request/response flows, "
     "authentication layers, rate limiting, and backend service connections. Show the "
     "API gateway pattern with routing and middleware.",
     "16:9"),

    ("database_schema", "Database Schema / ER Diagram", "Software",
     "Create an entity-relationship (ER) diagram showing database tables, columns, "
     "primary keys, foreign keys, and relationships (one-to-one, one-to-many, "
     "many-to-many). Use standard ER notation with crow's foot or UML cardinality.",
     "4:3"),

    # --- Process & Logic ---
    ("flowchart", "Flowchart", "Process",
     "Create a flowchart showing a step-by-step process with decision points, actions, "
     "and outcomes. Use standard flowchart shapes: rectangles for processes, diamonds "
     "for decisions, parallelograms for I/O, and rounded rectangles for start/end. "
     "Show clear directional flow with labeled arrows.",
     "3:4"),

    ("decision_tree", "Decision Tree", "Process",
     "Create a decision tree diagram branching from a root question through multiple "
     "decision nodes to leaf outcomes. Each branch should be clearly labeled with the "
     "condition or choice. Use consistent spacing and alignment for readability.",
     "4:3"),

    ("sequence_diagram", "Sequence Diagram", "Process",
     "Create a UML sequence diagram showing interactions between actors and systems "
     "over time. Show lifelines, synchronous and asynchronous messages, return values, "
     "activation bars, and alt/loop/opt fragments where appropriate.",
     "3:4"),

    ("state_machine", "State Machine", "Process",
     "Create a state machine diagram showing states as rounded rectangles, transitions "
     "as labeled arrows, initial and final states, and guard conditions. Show all "
     "possible state transitions with their triggering events.",
     "4:3"),

    ("pipeline", "CI/CD Pipeline", "Process",
     "Create a CI/CD pipeline diagram showing build, test, and deployment stages. "
     "Include source control triggers, build steps, test suites, artifact storage, "
     "staging environments, and production deployment with approval gates.",
     "16:9"),

    # --- Planning & Conceptual ---
    ("mind_map", "Mind Map", "Conceptual",
     "Create a mind map radiating outward from a central concept. Main branches should "
     "represent major themes, with sub-branches for details. Use color coding to "
     "distinguish different branches. Keep text concise and use icons where helpful.",
     "1:1"),

    ("wireframe", "Wireframe / UI Mockup", "Conceptual",
     "Create a wireframe or UI mockup showing page layout, navigation elements, content "
     "areas, buttons, forms, and interactive components. Use a low-fidelity grayscale "
     "style with placeholder text and simple shapes to represent UI elements.",
     "9:16"),

    ("gantt_chart", "Gantt Chart / Timeline", "Conceptual",
     "Create a Gantt chart or project timeline showing tasks, durations, dependencies, "
     "and milestones along a horizontal time axis. Use colored bars for different task "
     "categories and diamond markers for milestones. Show the critical path.",
     "16:9"),

    ("comparison_table", "Comparison Table / Matrix", "Conceptual",
     "Create a structured comparison table or feature matrix with clear rows and columns, "
     "headers, and cell content. Use checkmarks, X marks, or color coding to indicate "
     "feature support or status. Include a legend if needed.",
     "4:3"),

    ("org_chart", "Org Chart / Hierarchy", "Conceptual",
     "Create an organizational chart or hierarchy diagram showing reporting structure "
     "with boxes for each role/entity connected by lines showing relationships. "
     "Support multiple levels with clear top-down or left-to-right layout.",
     "16:9"),
]

# Build lookup helpers
STYLE_BY_KEY = {p[0]: p for p in STYLE_PRESETS}
DIAGRAM_TYPE_BY_KEY = {p[0]: p for p in DIAGRAM_TYPES}

STYLE_CATEGORIES = []
_seen_cats = set()
for p in STYLE_PRESETS:
    if p[2] not in _seen_cats:
        STYLE_CATEGORIES.append(p[2])
        _seen_cats.add(p[2])

DIAGRAM_TYPE_CATEGORIES = []
_seen_dt_cats = set()
for p in DIAGRAM_TYPES:
    if p[2] not in _seen_dt_cats:
        DIAGRAM_TYPE_CATEGORIES.append(p[2])
        _seen_dt_cats.add(p[2])

# --- API ---

FAL_SYNC_URL = "https://fal.run/fal-ai/nano-banana-2/edit"
FAL_QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"
FAL_TXT2IMG_SYNC_URL = "https://fal.run/fal-ai/nano-banana-2"
FAL_TXT2IMG_QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2"


def image_to_data_url(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "bmp": "image/bmp"}.get(ext.lstrip("."), "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def _call_fal(sync_url, queue_url, headers, payload):
    """Call Fal API with sync-first, queue-fallback pattern."""
    resp = requests.post(sync_url, headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    result = resp.json()

    if "images" in result and result["images"]:
        return result["images"]

    request_id = result.get("request_id")
    if not request_id:
        return []

    result_url = f"{queue_url}/requests/{request_id}"
    status_url = f"{queue_url}/requests/{request_id}/status"

    for _ in range(120):
        time.sleep(2)
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        status = status_resp.json()
        if status.get("status") == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            return result_resp.json().get("images", [])
        if status.get("status") in ("FAILED", "CANCELLED"):
            return []

    return []


def call_fal_img2img(img_path: str, api_key: str, prompt: str,
                     output_format: str = "png", resolution: str = "1K",
                     num_images: int = 1, aspect_ratio: str = "auto") -> list[dict]:
    """Call Fal API for image-to-image (edit) tasks."""
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    data_url = image_to_data_url(img_path)
    payload = {
        "prompt": prompt,
        "image_urls": [data_url],
        "output_format": output_format,
        "resolution": resolution,
        "num_images": num_images,
    }
    if aspect_ratio and aspect_ratio != "auto":
        payload["aspect_ratio"] = aspect_ratio

    return _call_fal(FAL_SYNC_URL, FAL_QUEUE_URL, headers, payload)


def call_fal_txt2img(api_key: str, prompt: str,
                     output_format: str = "png", resolution: str = "1K",
                     num_images: int = 1, aspect_ratio: str = "auto") -> list[dict]:
    """Call Fal API for text-to-image generation (no input image)."""
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "output_format": output_format,
        "resolution": resolution,
        "num_images": num_images,
    }
    if aspect_ratio and aspect_ratio != "auto":
        payload["aspect_ratio"] = aspect_ratio

    return _call_fal(FAL_TXT2IMG_SYNC_URL, FAL_TXT2IMG_QUEUE_URL, headers, payload)


# --- Prompt Construction ---

def build_whiteboard_prompt(style_prompt: str, dictionary_words: list[str] | None = None) -> str:
    """Build a complete prompt for whiteboard cleanup mode."""
    prompt = (
        f"Take this whiteboard photograph and transform it into a polished diagram. "
        f"{WHITEBOARD_INSTRUCTIONS} {style_prompt}"
    )
    if dictionary_words:
        word_list = ", ".join(dictionary_words)
        prompt += (
            f"\n\nThe following specific terms appear in this whiteboard and "
            f"should be spelled exactly as listed: {word_list}"
        )
    return prompt


def build_img2img_prompt(
    user_prompt: str = "",
    style_key: str | None = None,
    diagram_type_key: str | None = None,
    style_overrides: dict | None = None,
    dictionary_words: list[str] | None = None,
) -> str:
    """Build a prompt for image-to-image mode.

    Concatenation: [diagram type context] + [user prompt] + [style]
    At least one of user_prompt, style_key, or diagram_type_key should be provided.
    """
    parts = []

    if diagram_type_key and diagram_type_key in DIAGRAM_TYPE_BY_KEY:
        dt = DIAGRAM_TYPE_BY_KEY[diagram_type_key]
        parts.append(f"Transform this image into: {dt[3]}")

    if user_prompt.strip():
        parts.append(user_prompt.strip())

    if style_key and style_key in STYLE_BY_KEY:
        style_text = style_overrides.get(style_key, STYLE_BY_KEY[style_key][3]) if style_overrides else STYLE_BY_KEY[style_key][3]
        parts.append(f"Visual style: {style_text}")

    prompt = " ".join(parts) if parts else "Transform this image into a clean, polished diagram."

    if dictionary_words:
        word_list = ", ".join(dictionary_words)
        prompt += (
            f"\n\nThe following specific terms appear in this image and "
            f"should be spelled exactly as listed: {word_list}"
        )
    return prompt


def build_txt2img_prompt(
    user_prompt: str = "",
    style_key: str | None = None,
    diagram_type_key: str | None = None,
    style_overrides: dict | None = None,
) -> str:
    """Build a prompt for text-to-image mode.

    Concatenation: [diagram type context] + [user prompt] + [style]
    At least one of user_prompt, style_key, or diagram_type_key should be provided.
    """
    parts = []

    if diagram_type_key and diagram_type_key in DIAGRAM_TYPE_BY_KEY:
        dt = DIAGRAM_TYPE_BY_KEY[diagram_type_key]
        parts.append(dt[3])

    if user_prompt.strip():
        parts.append(user_prompt.strip())

    if style_key and style_key in STYLE_BY_KEY:
        style_text = style_overrides.get(style_key, STYLE_BY_KEY[style_key][3]) if style_overrides else STYLE_BY_KEY[style_key][3]
        parts.append(f"Visual style: {style_text}")

    return " ".join(parts) if parts else "Create a clean, polished tech diagram."
