/**
 * Nano Tech Diagrams - Core library for creating and editing tech diagrams
 * with Nano Banana 2 (via Fal AI).
 */

import { readFileSync } from "node:fs";
import { extname } from "node:path";

// --- API Endpoints (Nano Banana 2 baked in) ---

const FAL_SYNC_URL = "https://fal.run/fal-ai/nano-banana-2/edit";
const FAL_QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit";
const FAL_TXT2IMG_SYNC_URL = "https://fal.run/fal-ai/nano-banana-2";
const FAL_TXT2IMG_QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2";

// --- Types ---

export interface StylePreset {
  key: string;
  displayName: string;
  category: string;
  prompt: string;
  defaultAspectRatio: string;
}

export interface DiagramType {
  key: string;
  displayName: string;
  category: string;
  prompt: string;
  defaultAspectRatio: string;
}

export interface FalImage {
  url: string;
  content_type?: string;
  width?: number;
  height?: number;
}

// --- Aspect Ratios ---

export const ASPECT_RATIOS = [
  "auto", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9", "9:21",
] as const;

export type AspectRatio = (typeof ASPECT_RATIOS)[number];

// --- Whiteboard Instructions ---

const WHITEBOARD_INSTRUCTIONS =
  "Remove the physical whiteboard, markers, frame, and any background elements. " +
  "Correct any perspective distortion so the output appears as a perfectly " +
  "straight-on, top-down view regardless of the angle the original photo was taken from. " +
  "Preserve all the original content, text, and diagrams. " +
  "Where handwriting is ambiguous, infer the correct spelling from context rather than " +
  "reproducing the raw strokes literally -- for example, a word that looks like " +
  "'proxknox' should be rendered as 'Proxmox' if that is the obvious intended meaning.";

// --- Style Presets ---

export const STYLE_PRESETS: StylePreset[] = [
  // Professional
  { key: "clean_polished", displayName: "Clean & Polished", category: "Professional",
    prompt: "Render as a beautiful and polished graphic featuring clear labels and icons on a clean white background. Content should be legible and well-organized with a clear visual hierarchy. Use clean shapes, consistent line weights, and a professional color palette. The result should be visually attractive and easy to understand.",
    defaultAspectRatio: "auto" },
  { key: "corporate_clean", displayName: "Corporate Clean", category: "Professional",
    prompt: "Render as a clean, minimalist corporate diagram suitable for a professional presentation. Use a restrained color palette of navy blue, grey, and one accent color. Shapes should be clean geometric forms with a modern sans-serif font for all text and simple flat icons where appropriate. The result should look like it came from a polished slide deck -- professional, understated, and immediately readable.",
    defaultAspectRatio: "16:9" },
  { key: "hand_drawn_polished", displayName: "Hand-Drawn Polished", category: "Professional",
    prompt: "Render in a polished hand-drawn style on a clean white or light cream background. Keep an organic, hand-drawn character but refine it -- smoother lines, consistent stroke weight, better spacing, and cleaner handwriting that is still clearly handwritten. Add soft watercolor-style fills or gentle color washes to different sections. The result should feel like a carefully crafted sketch in a designer's notebook -- warm, human, and thoughtfully composed.",
    defaultAspectRatio: "auto" },
  { key: "minimalist_mono", displayName: "Minimalist Mono", category: "Professional",
    prompt: "Render as a stark, minimalist black-and-white diagram on a pure white background. Use only black lines, shapes, and text -- no color, no gradients, no fills. Lines should be clean and uniform weight. Use a simple, elegant sans-serif font. Maximize whitespace and let the structure breathe. The result should be austere and elegant -- like a diagram in an academic paper or a Dieter Rams design specification.",
    defaultAspectRatio: "auto" },
  { key: "ultra_sleek", displayName: "Ultra Sleek", category: "Professional",
    prompt: "Render as an ultra-sleek, refined diagram with elegant precision on a pure white background with generous margins. Use extremely thin, hairline-weight lines in dark grey or black. Shapes should be geometric and perfectly aligned with consistent spacing. Use a single subtle accent color -- a muted teal or steel blue -- sparingly for key elements only. Text should be set in an ultra-light weight, elegant sans-serif font with generous letter spacing. Maximize negative space. The result should feel like it was designed by a Swiss typographer -- razor-sharp and effortlessly sophisticated.",
    defaultAspectRatio: "auto" },
  { key: "blog_hero", displayName: "Blog Hero", category: "Professional",
    prompt: "Render as a polished diagram suitable as a blog post hero image on a soft gradient background that transitions from light blue-grey at the top to white at the bottom. Use a modern, approachable color palette with one strong brand color (a confident blue or teal) and supporting warm greys. Shapes should have subtle rounded corners and light drop shadows for depth. Use a clean, highly readable sans-serif font. Add simple line icons that reinforce each concept. Include generous padding around the entire diagram. The result should be a polished image ready to drop into a blog post -- professional and inviting to click.",
    defaultAspectRatio: "16:9" },

  // Creative
  { key: "colorful_infographic", displayName: "Colorful Infographic", category: "Creative",
    prompt: "Render as a bold, vibrant infographic-style diagram on a clean white background. Use a rich, vibrant color palette with distinct colors for different sections or concepts. Add colorful icons, rounded shapes, and visual hierarchy through size and color contrast. Text should be clear and legible in a friendly, rounded font. The result should feel energetic and engaging -- like a well-designed infographic you'd want to share.",
    defaultAspectRatio: "auto" },
  { key: "comic_book", displayName: "Comic Book", category: "Creative",
    prompt: "Render in a bold comic book illustration style with thick black ink outlines, Ben-Day dot shading patterns, and a vivid primary color palette of red, blue, yellow, and green. Text should appear in comic-style lettering with key labels in speech bubbles or caption boxes. Add dynamic action lines and POW/ZAP-style emphasis marks around important connections. The result should look like a page ripped from a tech-themed graphic novel -- bold, punchy, and impossible to scroll past.",
    defaultAspectRatio: "3:4" },
  { key: "isometric_3d", displayName: "Isometric 3D", category: "Creative",
    prompt: "Render as an isometric 3D-style diagram on a clean white background. Render boxes and containers as isometric 3D blocks with subtle depth and soft shadows. Use a modern, cheerful color palette with distinct colors for different components. Arrows and connectors should follow isometric angles. Labels should float cleanly above their elements. The result should look like a polished isometric tech illustration -- the kind you'd see in a modern SaaS landing page or developer documentation.",
    defaultAspectRatio: "4:3" },
  { key: "neon_sign", displayName: "Neon Sign", category: "Creative",
    prompt: "Render as glowing neon signs mounted on a dark exposed-brick wall background. All lines, shapes, and text should be glowing neon tubes in different colors -- pink, blue, white, and yellow. Each neon element should have a realistic glow effect with soft light bleeding onto the brick wall behind it. Connectors and arrows should be continuous neon tube bends. The result should look like an elaborate neon sign installation in a trendy bar -- atmospheric, eye-catching, and unmistakably cool.",
    defaultAspectRatio: "auto" },
  { key: "pastel_kawaii", displayName: "Pastel Kawaii", category: "Creative",
    prompt: "Render in an adorable pastel-colored kawaii illustration style on a soft pastel pink or lavender background. Use a soft pastel palette -- baby pink, mint green, lavender, peach, and sky blue. Shapes should have rounded, bubbly forms with thick soft outlines. Add tiny decorative elements like stars, sparkles, or small cloud accents. Use a cute, rounded handwriting-style font. The result should be charming and delightful -- like a page from a Japanese stationery notebook that still clearly communicates the diagram.",
    defaultAspectRatio: "auto" },
  { key: "pixel_art", displayName: "Pixel Art", category: "Creative",
    prompt: "Render as a pixel art-styled diagram reminiscent of 16-bit era video games on a clean background. Render all elements using visible, chunky pixels with a limited retro color palette. Shapes should be blocky with aliased edges. Text should use a pixel font. Add small pixel-art icons -- tiny servers, computers, clouds, gears -- next to relevant labels. Use dithering patterns for shading. The result should look like a UI screen from a classic strategy or simulation game -- charming and nostalgic.",
    defaultAspectRatio: "1:1" },
  { key: "stained_glass", displayName: "Stained Glass", category: "Creative",
    prompt: "Render as a stained glass window. Each section should be a pane of translucent colored glass with thick dark lead came lines separating them. Use rich jewel tones -- deep ruby, sapphire blue, emerald green, amber gold -- with light appearing to shine through the glass. Text should be integrated into the glass panes in a gothic or art nouveau lettering style. The result should look like a magnificent stained glass window depicting a technical diagram -- luminous, ornate, and strikingly beautiful.",
    defaultAspectRatio: "3:4" },
  { key: "sticky_notes", displayName: "Sticky Notes", category: "Creative",
    prompt: "Render as a colorful sticky-note style diagram on a light cork-board or soft beige textured background. Each concept, box, or grouping should be a colored sticky note (yellow, pink, blue, green) with a slight shadow and subtle rotation for a natural look. Use a casual handwritten-style font for text on the notes. Arrows and connectors should look like hand-drawn marker lines between the notes. The result should feel like a beautifully organized brainstorming board -- collaborative and approachable.",
    defaultAspectRatio: "4:3" },
  { key: "watercolor", displayName: "Watercolor Artistic", category: "Creative",
    prompt: "Render as a beautiful watercolor-style illustrated diagram on a textured watercolor paper background. Paint each section and shape with soft, translucent watercolor washes in a harmonious palette of warm and cool tones. Lines should have an ink-pen quality -- thin, confident, and slightly organic. Text should be rendered in elegant calligraphic handwriting. The result should look like a page from a beautifully illustrated journal -- artistic, expressive, and unique.",
    defaultAspectRatio: "auto" },

  // Technical
  { key: "blueprint", displayName: "Blueprint", category: "Technical",
    prompt: "Render as an architectural blueprint on a deep blue background. Use white and light blue lines for all shapes, arrows, and connectors. Text should appear in a clean technical drafting font. Add dimension-line styling to connectors and subtle cross-hatch fills where appropriate. The result should look like a precise engineering blueprint -- technical, authoritative, and classic.",
    defaultAspectRatio: "auto" },
  { key: "dark_mode", displayName: "Dark Mode Technical", category: "Technical",
    prompt: "Render as a technical diagram with a dark charcoal or near-black background. Use light-colored text (white or light grey) and neon or high-contrast accent colors like cyan, green, and orange for lines, arrows, and highlights. Use a monospace or technical font for labels. Add subtle grid lines or dot patterns in the background. The result should look like a technical blueprint or engineering schematic -- precise, detailed, and developer-friendly.",
    defaultAspectRatio: "auto" },
  { key: "flat_material", displayName: "Flat Material", category: "Technical",
    prompt: "Render as a flat Material Design-styled diagram on a clean light grey (#FAFAFA) background. Use the Material Design color palette -- primary blues, teals, and deep oranges with clean flat fills and subtle elevation shadows on cards and containers. Round the corners of all shapes. Use a Roboto-style sans-serif font for all text. Icons should be simple outlined material-style icons. The result should look like a screen from a well-designed Android app -- clean, systematic, and modern.",
    defaultAspectRatio: "auto" },
  { key: "github_readme", displayName: "GitHub README", category: "Technical",
    prompt: "Render as a clean diagram optimized for GitHub README files on a pure white background with clean edges and no border. Use GitHub's familiar color palette -- blues (#0969DA), greens (#1A7F37), purples (#8250DF), and neutral greys. Shapes should be clean rounded rectangles with subtle borders. Use a system sans-serif font. Add simple, recognizable developer icons (git branches, terminal prompts, API endpoints, databases). The result should look like a native GitHub diagram that blends seamlessly into a README.",
    defaultAspectRatio: "16:9" },
  { key: "photographic", displayName: "Photographic 3D", category: "Technical",
    prompt: "Render as a photorealistic 3D diagram on a clean surface like a light wooden desk or frosted glass table, shot from directly above. Each box, container, or concept should be a physical object -- glossy acrylic blocks, frosted glass cards, or brushed metal plates with realistic reflections and soft shadows. Arrows and connectors should look like thin metal rods or illuminated fiber-optic strips. Text should appear etched, printed, or embossed on the surfaces. Use studio-quality lighting with soft diffusion. The result should look like a product photograph of a physical scale model.",
    defaultAspectRatio: "4:3" },
  { key: "terminal_hacker", displayName: "Terminal Hacker", category: "Technical",
    prompt: "Render as a retro computer terminal display on a pure black background. Use phosphor green (#00FF00) as the primary color for all text, lines, and shapes. Add a subtle CRT scan-line effect and slight screen curvature glow at the edges. Use a monospace terminal font for all text. Boxes should be drawn with ASCII-style borders. The result should look like output from a 1980s mainframe terminal -- minimal, technical, and unmistakably computer-native.",
    defaultAspectRatio: "4:3" },
  { key: "visionary", displayName: "Visionary Inspirational", category: "Technical",
    prompt: "Render as a grand, visionary-style diagram on a deep space or cosmic gradient background (dark blues and purples with subtle star fields or nebula wisps). Render concepts as glowing nodes connected by luminous pathways of light. Use a palette of gold, white, and ethereal blue. Text should be clean and luminous, as if projected in light. Add subtle lens flare effects and soft radial glows around key concepts. The result should feel epic and aspirational -- like a strategic roadmap presented at a visionary keynote.",
    defaultAspectRatio: "16:9" },

  // Retro & Fun
  { key: "chalkboard", displayName: "Chalkboard", category: "Retro & Fun",
    prompt: "Render as if drawn on a classic green chalkboard with a dark green chalkboard-textured background with subtle chalk dust. Use white and colored chalk (yellow, pink, light blue) for all lines, shapes, and text. The lettering should look like clean chalk handwriting. Add subtle smudge effects and chalk texture to lines. The result should feel like a beautifully organized lecture -- academic, warm, and intellectual.",
    defaultAspectRatio: "16:9" },
  { key: "psychedelic", displayName: "Eccentric Psychedelic", category: "Retro & Fun",
    prompt: "Render in a wild, psychedelic style bursting with color. Use intensely saturated, clashing colors -- electric purples, acid greens, hot magentas, deep oranges -- with swirling gradients and color bleeds between sections. Lines should pulse with energy, varying in thickness and color. Add organic, flowing patterns and mandala-like decorative fills inside shapes. Text should be bold and wavy, distorted slightly but still readable. The background should be a shifting kaleidoscope of color. The result should feel like a 1960s concert poster -- overwhelming, hypnotic, and unforgettable.",
    defaultAspectRatio: "1:1" },
  { key: "mad_genius", displayName: "Mad Genius", category: "Retro & Fun",
    prompt: "Render as a chaotic, sprawling mad-genius-style diagram on a slightly yellowed, aged paper background with coffee stain marks and creased folds. Amplify the chaos -- frantic and varied handwriting sizes, scribbled annotations in margins, multiple underlines, aggressively circled key concepts, arrows that loop and cross over each other. Use red ink for emphatic corrections and blue ink for main content. Scatter small doodles, question marks, and exclamation points in empty spaces. The result should look like the notebook of a brilliant but unhinged mind -- feverish, obsessive, and crackling with intellectual energy.",
    defaultAspectRatio: "auto" },
  { key: "retro_80s", displayName: "Retro 80s Synthwave", category: "Retro & Fun",
    prompt: "Render as a retro 1980s synthwave-styled diagram on a dark purple-to-black gradient background. Use hot pink, electric cyan, and neon yellow for lines, shapes, and text. Add subtle scan-line effects and a retro grid perspective floor fading into the background. Use a bold, blocky retro font for all labels. The result should feel like a tech diagram from an 80s sci-fi movie -- glowing, vibrant, and unmistakably retro-futuristic.",
    defaultAspectRatio: "16:9" },
  { key: "woodcut", displayName: "Woodcut", category: "Retro & Fun",
    prompt: "Render as a medieval woodcut or linocut print on an aged parchment or cream-colored background. Use bold black carved lines with visible wood-grain texture in the strokes. Use cross-hatching for shading and fills. Text should appear in a blackletter or old-style serif typeface. Shapes should have a rough, hand-carved quality. Optionally add a single spot color (a deep red or ochre) for emphasis on key elements. The result should look like a page from an illuminated technical manuscript -- ancient, authoritative, and delightfully absurd as a format for modern tech diagrams.",
    defaultAspectRatio: "auto" },

  // Language
  { key: "bilingual_hebrew", displayName: "Bilingual (Hebrew)", category: "Language",
    prompt: "Render with all existing English labels kept in place, and add Hebrew translations below or beside each label in a slightly smaller font. Hebrew text should read right-to-left and use clear, modern Hebrew typography. Use color coding to visually distinguish the two languages -- for example, dark grey for English and blue for Hebrew. The result should be a clean, professional bilingual diagram that is fully readable in both English and Hebrew. Use a clean white background.",
    defaultAspectRatio: "auto" },
  { key: "translated_hebrew", displayName: "Translated (Hebrew)", category: "Language",
    prompt: "Render with all text labels translated to Hebrew. Preserve all diagram structure, shapes, arrows, and layout -- but replace every English text label with its Hebrew translation. Hebrew text should read right-to-left and use clear, modern Hebrew typography. Ensure translated labels fit naturally within their shapes and containers. Use clean, professional styling with colorful icons and clear visual hierarchy on a clean white background. The result should be a fully Hebrew-language version that reads naturally for a Hebrew speaker.",
    defaultAspectRatio: "auto" },
];

// --- Diagram Type Presets ---

export const DIAGRAM_TYPES: DiagramType[] = [
  // Infrastructure
  { key: "network_diagram", displayName: "Network Diagram", category: "Infrastructure",
    prompt: "Create a network architecture diagram showing hosts, routers, switches, firewalls, and connections between them. Use standard networking iconography. Show network segments, subnets, and data flow directions with labeled connections.",
    defaultAspectRatio: "16:9" },
  { key: "cloud_architecture", displayName: "Cloud Architecture", category: "Infrastructure",
    prompt: "Create a cloud infrastructure architecture diagram showing cloud services, regions, availability zones, and their interconnections. Use recognizable cloud service icons (compute, storage, database, networking). Show data flow and service dependencies.",
    defaultAspectRatio: "16:9" },
  { key: "kubernetes_cluster", displayName: "Kubernetes Cluster", category: "Infrastructure",
    prompt: "Create a Kubernetes cluster diagram showing nodes, pods, services, ingress controllers, namespaces, and persistent volumes. Use standard Kubernetes iconography. Show the relationship between deployments, replica sets, and pods.",
    defaultAspectRatio: "16:9" },
  { key: "server_rack", displayName: "Server Rack / Data Center", category: "Infrastructure",
    prompt: "Create a data center or server rack diagram showing physical or logical server layout, storage arrays, network switches, and cabling. Show redundancy paths and failover connections.",
    defaultAspectRatio: "3:4" },

  // Software
  { key: "system_architecture", displayName: "System Architecture", category: "Software",
    prompt: "Create a software system architecture diagram showing major components, services, APIs, databases, and message queues. Show how data flows between components. Distinguish between frontend, backend, and data layers.",
    defaultAspectRatio: "16:9" },
  { key: "microservices", displayName: "Microservices Map", category: "Software",
    prompt: "Create a microservices architecture diagram showing individual services, API gateways, service mesh, message brokers, and databases. Show synchronous and asynchronous communication patterns between services.",
    defaultAspectRatio: "16:9" },
  { key: "api_architecture", displayName: "API Architecture", category: "Software",
    prompt: "Create an API architecture diagram showing endpoints, request/response flows, authentication layers, rate limiting, and backend service connections. Show the API gateway pattern with routing and middleware.",
    defaultAspectRatio: "16:9" },
  { key: "database_schema", displayName: "Database Schema / ER Diagram", category: "Software",
    prompt: "Create an entity-relationship (ER) diagram showing database tables, columns, primary keys, foreign keys, and relationships (one-to-one, one-to-many, many-to-many). Use standard ER notation with crow's foot or UML cardinality.",
    defaultAspectRatio: "4:3" },

  // Process
  { key: "flowchart", displayName: "Flowchart", category: "Process",
    prompt: "Create a flowchart showing a step-by-step process with decision points, actions, and outcomes. Use standard flowchart shapes: rectangles for processes, diamonds for decisions, parallelograms for I/O, and rounded rectangles for start/end. Show clear directional flow with labeled arrows.",
    defaultAspectRatio: "3:4" },
  { key: "decision_tree", displayName: "Decision Tree", category: "Process",
    prompt: "Create a decision tree diagram branching from a root question through multiple decision nodes to leaf outcomes. Each branch should be clearly labeled with the condition or choice. Use consistent spacing and alignment for readability.",
    defaultAspectRatio: "4:3" },
  { key: "sequence_diagram", displayName: "Sequence Diagram", category: "Process",
    prompt: "Create a UML sequence diagram showing interactions between actors and systems over time. Show lifelines, synchronous and asynchronous messages, return values, activation bars, and alt/loop/opt fragments where appropriate.",
    defaultAspectRatio: "3:4" },
  { key: "state_machine", displayName: "State Machine", category: "Process",
    prompt: "Create a state machine diagram showing states as rounded rectangles, transitions as labeled arrows, initial and final states, and guard conditions. Show all possible state transitions with their triggering events.",
    defaultAspectRatio: "4:3" },
  { key: "pipeline", displayName: "CI/CD Pipeline", category: "Process",
    prompt: "Create a CI/CD pipeline diagram showing build, test, and deployment stages. Include source control triggers, build steps, test suites, artifact storage, staging environments, and production deployment with approval gates.",
    defaultAspectRatio: "16:9" },

  // Conceptual
  { key: "mind_map", displayName: "Mind Map", category: "Conceptual",
    prompt: "Create a mind map radiating outward from a central concept. Main branches should represent major themes, with sub-branches for details. Use color coding to distinguish different branches. Keep text concise and use icons where helpful.",
    defaultAspectRatio: "1:1" },
  { key: "wireframe", displayName: "Wireframe / UI Mockup", category: "Conceptual",
    prompt: "Create a wireframe or UI mockup showing page layout, navigation elements, content areas, buttons, forms, and interactive components. Use a low-fidelity grayscale style with placeholder text and simple shapes to represent UI elements.",
    defaultAspectRatio: "9:16" },
  { key: "gantt_chart", displayName: "Gantt Chart / Timeline", category: "Conceptual",
    prompt: "Create a Gantt chart or project timeline showing tasks, durations, dependencies, and milestones along a horizontal time axis. Use colored bars for different task categories and diamond markers for milestones. Show the critical path.",
    defaultAspectRatio: "16:9" },
  { key: "comparison_table", displayName: "Comparison Table / Matrix", category: "Conceptual",
    prompt: "Create a structured comparison table or feature matrix with clear rows and columns, headers, and cell content. Use checkmarks, X marks, or color coding to indicate feature support or status. Include a legend if needed.",
    defaultAspectRatio: "4:3" },
  { key: "org_chart", displayName: "Org Chart / Hierarchy", category: "Conceptual",
    prompt: "Create an organizational chart or hierarchy diagram showing reporting structure with boxes for each role/entity connected by lines showing relationships. Support multiple levels with clear top-down or left-to-right layout.",
    defaultAspectRatio: "16:9" },
];

// --- Lookup helpers ---

export const STYLE_BY_KEY = new Map(STYLE_PRESETS.map((s) => [s.key, s]));
export const DIAGRAM_TYPE_BY_KEY = new Map(DIAGRAM_TYPES.map((d) => [d.key, d]));

// --- Image helpers ---

function imageToDataUrl(filePath: string): string {
  const ext = extname(filePath).toLowerCase().replace(".", "");
  const mimeMap: Record<string, string> = {
    jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png",
    webp: "image/webp", bmp: "image/bmp",
  };
  const mime = mimeMap[ext] || "image/png";
  const b64 = readFileSync(filePath).toString("base64");
  return `data:${mime};base64,${b64}`;
}

// --- Fal API ---

async function callFal(
  syncUrl: string, queueUrl: string, headers: Record<string, string>,
  payload: Record<string, unknown>,
): Promise<FalImage[]> {
  const resp = await fetch(syncUrl, {
    method: "POST", headers, body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Fal API error ${resp.status}: ${text}`);
  }
  const result = await resp.json() as Record<string, unknown>;

  if (Array.isArray(result.images) && result.images.length > 0) {
    return result.images as FalImage[];
  }

  const requestId = result.request_id as string | undefined;
  if (!requestId) return [];

  const resultUrl = `${queueUrl}/requests/${requestId}`;
  const statusUrl = `${queueUrl}/requests/${requestId}/status`;

  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const statusResp = await fetch(statusUrl, { headers });
    if (!statusResp.ok) continue;
    const status = await statusResp.json() as Record<string, unknown>;
    if (status.status === "COMPLETED") {
      const resultResp = await fetch(resultUrl, { headers });
      if (!resultResp.ok) continue;
      const data = await resultResp.json() as Record<string, unknown>;
      return (data.images as FalImage[]) || [];
    }
    if (status.status === "FAILED" || status.status === "CANCELLED") return [];
  }
  return [];
}

export async function callFalImg2Img(
  imagePath: string, apiKey: string, prompt: string,
  outputFormat = "png", resolution = "1K", numImages = 1, aspectRatio = "auto",
): Promise<FalImage[]> {
  const headers = { Authorization: `Key ${apiKey}`, "Content-Type": "application/json" };
  const dataUrl = imageToDataUrl(imagePath);
  const payload: Record<string, unknown> = {
    prompt, image_urls: [dataUrl], output_format: outputFormat,
    resolution, num_images: numImages,
  };
  if (aspectRatio && aspectRatio !== "auto") payload.aspect_ratio = aspectRatio;
  return callFal(FAL_SYNC_URL, FAL_QUEUE_URL, headers, payload);
}

export async function callFalTxt2Img(
  apiKey: string, prompt: string,
  outputFormat = "png", resolution = "1K", numImages = 1, aspectRatio = "auto",
): Promise<FalImage[]> {
  const headers = { Authorization: `Key ${apiKey}`, "Content-Type": "application/json" };
  const payload: Record<string, unknown> = {
    prompt, output_format: outputFormat, resolution, num_images: numImages,
  };
  if (aspectRatio && aspectRatio !== "auto") payload.aspect_ratio = aspectRatio;
  return callFal(FAL_TXT2IMG_SYNC_URL, FAL_TXT2IMG_QUEUE_URL, headers, payload);
}

// --- Prompt Construction ---

export function buildWhiteboardPrompt(stylePrompt: string, dictionaryWords?: string[]): string {
  let prompt = `Take this whiteboard photograph and transform it into a polished diagram. ${WHITEBOARD_INSTRUCTIONS} ${stylePrompt}`;
  if (dictionaryWords?.length) {
    prompt += `\n\nThe following specific terms appear in this whiteboard and should be spelled exactly as listed: ${dictionaryWords.join(", ")}`;
  }
  return prompt;
}

export function buildImg2ImgPrompt(opts: {
  userPrompt?: string; styleKey?: string; diagramTypeKey?: string;
  dictionaryWords?: string[];
}): string {
  const parts: string[] = [];

  if (opts.diagramTypeKey) {
    const dt = DIAGRAM_TYPE_BY_KEY.get(opts.diagramTypeKey);
    if (dt) parts.push(`Transform this image into: ${dt.prompt}`);
  }
  if (opts.userPrompt?.trim()) parts.push(opts.userPrompt.trim());
  if (opts.styleKey) {
    const style = STYLE_BY_KEY.get(opts.styleKey);
    if (style) parts.push(`Visual style: ${style.prompt}`);
  }

  let prompt = parts.length ? parts.join(" ") : "Transform this image into a clean, polished diagram.";

  if (opts.dictionaryWords?.length) {
    prompt += `\n\nThe following specific terms appear in this image and should be spelled exactly as listed: ${opts.dictionaryWords.join(", ")}`;
  }
  return prompt;
}

export function buildTxt2ImgPrompt(opts: {
  userPrompt?: string; styleKey?: string; diagramTypeKey?: string;
}): string {
  const parts: string[] = [];

  if (opts.diagramTypeKey) {
    const dt = DIAGRAM_TYPE_BY_KEY.get(opts.diagramTypeKey);
    if (dt) parts.push(dt.prompt);
  }
  if (opts.userPrompt?.trim()) parts.push(opts.userPrompt.trim());
  if (opts.styleKey) {
    const style = STYLE_BY_KEY.get(opts.styleKey);
    if (style) parts.push(`Visual style: ${style.prompt}`);
  }

  return parts.length ? parts.join(" ") : "Create a clean, polished tech diagram.";
}
