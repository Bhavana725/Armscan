function getHTML() {
    return document.documentElement.outerHTML;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "GET_HTML") {
        sendResponse({ html: getHTML() });
    }
});
