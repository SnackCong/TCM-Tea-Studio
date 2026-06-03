async function login(username, password) {
  const response = await fetch("/api/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "登录失败");
  return data;
}

document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#loginMessage");
  message.textContent = "";
  try {
    await login(
      document.querySelector("#loginUsername").value.trim(),
      document.querySelector("#loginPassword").value,
    );
    window.location.assign("/app");
  } catch (error) {
    message.textContent = error.message;
    document.querySelector("#loginPassword").value = "";
  }
});

const params = new URLSearchParams(window.location.search);
const initialMessage = params.get("message");
if (initialMessage) {
  document.querySelector("#loginMessage").textContent = initialMessage;
}
