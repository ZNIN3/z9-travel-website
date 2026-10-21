const tabs = [...document.querySelectorAll(".auth-switch-tab")];
const views = [...document.querySelectorAll(".auth-view")];
const message = document.querySelector("#auth-message");

function activateView(viewId, focusTab = false) {
  tabs.forEach((tab) => {
    const isSelected = tab.getAttribute("aria-controls") === viewId;
    tab.classList.toggle("is-active", isSelected);
    tab.setAttribute("aria-selected", String(isSelected));
    tab.tabIndex = isSelected ? 0 : -1;
    if (isSelected && focusTab) tab.focus();
  });

  views.forEach((view) => {
    view.hidden = view.id !== viewId;
  });
  message.textContent = "";
}

if (window.location.hash === "#signup-view") {
  activateView("signup-view");
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateView(tab.getAttribute("aria-controls")));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = index;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    activateView(tabs[nextIndex].getAttribute("aria-controls"), true);
  });
});

document.querySelectorAll(".password-toggle").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    const input = toggle.closest(".password-input").querySelector("input");
    const willShow = input.type === "password";
    input.type = willShow ? "text" : "password";
    toggle.setAttribute("aria-pressed", String(willShow));
    toggle.setAttribute("aria-label", `${willShow ? "Hide" : "Show"} password`);
  });
});

document.querySelectorAll(".auth-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    message.textContent = "Authentication is not connected yet. Please try again when account services are available.";
  });
});

document.querySelector("[data-forgot-password]").addEventListener("click", (event) => {
  event.preventDefault();
  message.textContent = "Password reset is not connected yet. Please contact Z9 Travel support for help.";
});

document.querySelectorAll(".social-auth-button").forEach((button) => {
  button.addEventListener("click", () => {
    message.textContent = `${button.dataset.provider} sign-in is not connected yet.`;
  });
});
