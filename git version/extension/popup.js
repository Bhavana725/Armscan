let latestProcessed = null;

document.getElementById("scanBtn").addEventListener("click", async () => {

    const resultDiv = document.getElementById("result");
    const downloadBtn = document.getElementById("downloadBtn");

    resultDiv.innerHTML = "Scanning...";
    downloadBtn.style.display = "none";

    let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    try {
        // Inject script
        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["content.js"]
        });

        const response = await chrome.tabs.sendMessage(tab.id, {
            action: "GET_HTML"
        });

        if (!response || !response.html) {
            throw new Error("Content extraction failed");
        }

        const res = await fetch("http://127.0.0.1:8000/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                html: response.html,
                url: tab.url
            })
        });

        const data = await res.json();

        latestProcessed = data.processed; // 🔥 store for download

        // -------- RENDER UI --------

        let html = "";

        if (!data.top_matches.length) {
            resultDiv.innerHTML = "No matches found";
            return;
        }

        const top = data.top_matches[0];

        // 🔥 Overall Risk
        let risk = "LOW";
        if (top.confidence > 0.7) risk = "HIGH";
        else if (top.confidence > 0.5) risk = "MEDIUM";

        html += `<div class="card">
                    <div class="risk">Overall Risk: ${risk}</div>
                 </div>`;

        // 🔥 Top Match Highlight
        html += `<div class="card highlight">
                    <b>Top Match</b><br>
                    ID: ${top.id}<br>
                    Score: ${(top.confidence*100).toFixed(2)}%<br>
                    Verdict: ${top.verdict}
                 </div>`;

        // 🔥 Other Matches
        html += `<div class="card">
                    <b>Other Matches</b><br>`;

        data.top_matches.slice(1).forEach(m => {
            html += `<div class="small">
                        ${m.id} | ${(m.confidence*100).toFixed(1)}% | ${m.verdict}
                     </div>`;
        });

        html += `</div>`;

        resultDiv.innerHTML = html;

        downloadBtn.style.display = "block";

    } catch (err) {
        console.error(err);
        resultDiv.innerHTML = "Error: " + err.message;
    }
});


// 🔥 DOWNLOAD JSON
document.getElementById("downloadBtn").addEventListener("click", () => {

    if (!latestProcessed) return;

    const blob = new Blob(
        [JSON.stringify(latestProcessed, null, 2)],
        { type: "application/json" }
    );

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "armos_processed.json";
    a.click();
});
