/**
 * Nano Tech Diagrams - Public API
 *
 * Library for creating and editing tech diagrams using Nano Banana 2 (via Fal AI).
 * Supports text-to-image, image-to-image, whiteboard cleanup, and 28+ style presets.
 */

export {
  // Types
  type StylePreset,
  type DiagramType,
  type FalImage,
  type AspectRatio,

  // Constants
  STYLE_PRESETS,
  DIAGRAM_TYPES,
  STYLE_BY_KEY,
  DIAGRAM_TYPE_BY_KEY,
  ASPECT_RATIOS,

  // API functions
  callFalImg2Img,
  callFalTxt2Img,

  // Prompt builders
  buildWhiteboardPrompt,
  buildImg2ImgPrompt,
  buildTxt2ImgPrompt,
} from "./core.js";
