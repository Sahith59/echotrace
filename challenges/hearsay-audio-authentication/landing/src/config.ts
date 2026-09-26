/// <reference types="vite/client" />

// Where "Open workspace" sends signed-in visitors. The Python backend serves the product at /app/ on the same origin.
export const WORKSPACE_URL: string = import.meta.env.VITE_WORKSPACE_URL ?? '/app/'

// Demo video: put the file at public/demo/echotrace-demo.mp4 and set VITE_DEMO_VIDEO_URL=/demo/echotrace-demo.mp4,
// or set it to a YouTube/Vimeo embed URL. Leave empty to show the placeholder.
export const DEMO_VIDEO_URL: string = import.meta.env.VITE_DEMO_VIDEO_URL ?? ''
