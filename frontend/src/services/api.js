const BASE = import.meta.env.VITE_API_BASE || "";

async function parse(res) {
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* body bukan JSON */
  }
  if (!res.ok) {
    throw new Error((data && data.detail) || `Permintaan gagal (HTTP ${res.status}).`);
  }
  return data;
}

async function request(path, options) {
  try {
    return await parse(await fetch(`${BASE}${path}`, options));
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error("Tidak dapat terhubung ke server. Pastikan backend berjalan.");
    }
    throw err;
  }
}

export const getTemplates = () => request("/api/templates");
export const getHealth = () => request("/api/health");
export const getStatus = (jobId) => request(`/api/status/${jobId}`);

export const generateClip = (payload) =>
  request("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const templateImageUrl = (name) => `${BASE}/api/templates/${name}/image`;
export const templatePreviewUrl = (name) => `${BASE}/api/templates/${name}/preview?v=${encodeURIComponent(name)}`;
export const downloadUrl = (jobId) => `${BASE}/api/download/${jobId}`;
export const previewUrl = (jobId) => `${BASE}/api/download/${jobId}?inline=1`;

// Upload dengan progress nyata (XMLHttpRequest, karena fetch belum punya upload progress).
export function uploadVideo(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/upload`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Upload gagal. Periksa koneksi ke server."));
    xhr.onabort = () => reject(new Error("Upload dibatalkan."));
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* bukan JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new Error((data && data.detail) || `Upload gagal (HTTP ${xhr.status}).`));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

// --- caption
export const getCaption = (jobId) => request(`/api/caption/${jobId}`);
export const regenerateCaption = (jobId, payload) =>
  request(`/api/caption/${jobId}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });

// --- hapus file dari server
export const deleteJob = (jobId) => request(`/api/jobs/${jobId}`, { method: "DELETE" });
export const deleteUpload = (uploadId) => request(`/api/upload/${uploadId}`, { method: "DELETE" });


// Upload musik pengganti (dipakai fitur Ganti Backsound), progress sederhana via XHR.
export function uploadAudio(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/upload-audio`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Upload musik gagal. Periksa koneksi ke server."));
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* bukan JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new Error((data && data.detail) || `Upload musik gagal (HTTP ${xhr.status}).`));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

// --- Template Builder: simpan langsung ke server (config/templates + assets/templates)
export async function saveTemplate(configObj, imageFile, overwrite = false) {
  const form = new FormData();
  form.append("file", imageFile, imageFile.name || "template.png");
  form.append("config", JSON.stringify(configObj));
  const res = await fetch(`${BASE}/api/templates${overwrite ? "?overwrite=true" : ""}`, {
    method: "POST",
    body: form,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* bukan JSON */
  }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `Gagal menyimpan template (HTTP ${res.status}).`);
    err.code = data && data.code;
    throw err;
  }
  return data;
}


// Preview menggunakan renderer Pillow backend yang sama dengan hasil video final.
export async function previewTemplate(configObj, imageFile, episodeText = "Contoh teks utama", titleText = "Judul video", signal) {
  const form = new FormData();
  form.append("file", imageFile, imageFile.name || "template.png");
  form.append("config", JSON.stringify(configObj));
  form.append("episode_text", episodeText);
  form.append("title_text", titleText);
  const res = await fetch(`${BASE}/api/templates/preview`, { method: "POST", body: form, signal });
  if (!res.ok) {
    let detail = `Preview gagal (HTTP ${res.status}).`;
    try { const data = await res.json(); detail = data.detail || detail; } catch {}
    throw new Error(detail);
  }
  return URL.createObjectURL(await res.blob());
}
