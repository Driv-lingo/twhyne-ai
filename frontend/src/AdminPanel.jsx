import React, { useEffect, useState } from "react";

export default function AdminPanel() {
  const [nodepacks, setNodepacks] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch("/admin/nodepacks")
      .then((res) => res.json())
      .then((data) => setNodepacks(data.nodepacks || []));
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    setUploading(true);
    setStatus("");
    const formData = new FormData();
    formData.append("bundle", e.target.bundle.files[0]);
    try {
      const res = await fetch("/admin/import", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setStatus(data.status || data.error || "");
      setUploading(false);
    } catch (err) {
      setStatus("Error uploading bundle");
      setUploading(false);
    }
  };

  return (
    <div className="admin-panel">
      <h2>NodePack Admin Panel</h2>
      <form onSubmit={handleUpload} style={{ marginBottom: 24 }}>
        <input type="file" name="bundle" accept=".tar.gz" required disabled={uploading} />
        <button type="submit" disabled={uploading}>Import NodePack</button>
        {status && <div style={{ marginTop: 8 }}>{status}</div>}
      </form>
      <h3>Installed NodePacks</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Node ID</th>
            <th>Manifest</th>
          </tr>
        </thead>
        <tbody>
          {nodepacks.map((pack) => (
            <tr key={pack.node_id}>
              <td>{pack.node_id}</td>
              <td>
                <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                  {JSON.stringify(pack.manifest, null, 2)}
                </pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
