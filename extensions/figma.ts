import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

function extractFileKey(url: string) {
  const match = url.match(/figma\.com\/(?:file|design)\/([^/?]+)/i);
  return match?.[1];
}

function extractNodeId(url: string) {
  const parsed = new URL(url);
  return parsed.searchParams.get("node-id") ?? undefined;
}

export default function (pi: ExtensionAPI) {
  function getApiKey() {
    const apiKey = process.env.FIGMA_API_KEY;
    if (!apiKey) {
      throw new Error("FIGMA_API_KEY environment variable is required.");
    }
    return apiKey;
  }

  async function figmaRequest(path: string, signal?: AbortSignal) {
    const response = await fetch(`https://api.figma.com/v1${path}`, {
      headers: { "X-Figma-Token": getApiKey() },
      signal,
    });

    if (!response.ok) {
      throw new Error(`Figma API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async function fetchNode(fileKey: string, nodeId: string, signal?: AbortSignal) {
    const data = await figmaRequest(`/files/${fileKey}/nodes?ids=${encodeURIComponent(nodeId)}`, signal);
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
      details: { fileKey, nodeId },
    };
  }

  pi.registerTool({
    name: "figma_get_node",
    label: "Figma Get Node",
    description: "Get the design specifications for a Figma node/component by file key and node ID.",
    parameters: Type.Object({
      file_key: Type.String({ description: "Figma file key from the URL" }),
      node_id: Type.String({ description: "Figma node ID from the URL (e.g. 45:678)" }),
    }),
    async execute(_toolCallId, params, signal) {
      return fetchNode(params.file_key, params.node_id, signal);
    },
  });

  pi.registerTool({
    name: "figma_get_node_from_url",
    label: "Figma Get Node From URL",
    description: "Get Figma node data directly from a full Figma file/design URL.",
    parameters: Type.Object({
      url: Type.String({ description: "Full Figma URL containing a file key and node-id query parameter" }),
    }),
    async execute(_toolCallId, params, signal) {
      const fileKey = extractFileKey(params.url);
      const nodeId = extractNodeId(params.url);
      if (!fileKey || !nodeId) {
        throw new Error("Could not extract file key and node-id from the Figma URL.");
      }
      return fetchNode(fileKey, nodeId, signal);
    },
  });

  pi.registerTool({
    name: "figma_get_file",
    label: "Figma Get File",
    description: "Fetch high-level metadata and document structure for a Figma file.",
    parameters: Type.Object({
      file_key: Type.String({ description: "Figma file key from the URL" }),
      depth: Type.Optional(Type.Number({ description: "Optional traversal depth" })),
    }),
    async execute(_toolCallId, params, signal) {
      const suffix = params.depth !== undefined ? `?depth=${params.depth}` : "";
      const data = await figmaRequest(`/files/${params.file_key}${suffix}`, signal);
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: { fileKey: params.file_key },
      };
    },
  });

  pi.registerTool({
    name: "figma_get_image",
    label: "Figma Get Image",
    description: "Get render URLs for a Figma node or multiple nodes.",
    parameters: Type.Object({
      file_key: Type.String({ description: "Figma file key from the URL" }),
      node_ids: Type.Array(Type.String(), { description: "One or more Figma node IDs" }),
      format: Type.Optional(Type.String({ description: "png, jpg, svg, or pdf" })),
      scale: Type.Optional(Type.Number({ description: "Optional render scale" })),
    }),
    async execute(_toolCallId, params, signal) {
      const search = new URLSearchParams();
      search.set("ids", params.node_ids.join(","));
      if (params.format) search.set("format", params.format);
      if (params.scale !== undefined) search.set("scale", String(params.scale));
      const data = await figmaRequest(`/images/${params.file_key}?${search.toString()}`, signal);
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: { fileKey: params.file_key, nodeIds: params.node_ids },
      };
    },
  });
}
