// Reads an uploaded file into something we can show and send: text, or a downscaled image / small PDF as base64.
export type Payload = { filename: string; mime: string; text?: string; imageBase64?: string; previewUrl?: string; kind: "text" | "image" | "pdf" };

const TEXT_EXT = /\.(txt|md|csv|tsv|json|py|js|ts|yaml|yml|xml|log|pseudo)$/i;

export async function readFile(file: File): Promise<Payload> {
  const mime = file.type || "";
  if (mime.startsWith("image/")) {
    const url = URL.createObjectURL(file);
    const img = await new Promise<HTMLImageElement>((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error("Could not read the image.")); i.src = url; });
    const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
    const c = document.createElement("canvas");
    c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
    c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
    const b64 = c.toDataURL("image/jpeg", 0.85).split(",")[1];
    return { filename: file.name, mime: "image/jpeg", imageBase64: b64, previewUrl: url, kind: "image" };
  }
  if (mime === "application/pdf" || /\.pdf$/i.test(file.name)) {
    if (file.size > 3_000_000) throw new Error("PDF is larger than 3 MB; export the page you need as an image instead.");
    const buf = new Uint8Array(await file.arrayBuffer());
    let s = ""; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    return { filename: file.name, mime: "application/pdf", imageBase64: btoa(s), kind: "pdf" };
  }
  if (mime.startsWith("text/") || TEXT_EXT.test(file.name) || mime === "application/json") {
    if (file.size > 200_000) throw new Error("Text file is larger than 200 KB.");
    return { filename: file.name, mime: mime || "text/plain", text: await file.text(), kind: "text" };
  }
  throw new Error("Unsupported file type. Use text, Python, JSON, an image (PNG/JPG) or a small PDF.");
}
