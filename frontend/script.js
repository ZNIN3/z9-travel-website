const tabs = [...document.querySelectorAll(".booking-tab")];
const panels = [...document.querySelectorAll(".form-panel")];
const searchForm = document.querySelector("#search-form");
const formMessage = document.querySelector("#form-message");
const menuToggle = document.querySelector(".menu-toggle");
const mainNav = document.querySelector(".main-nav");
const siteHeader = document.querySelector(".site-header");
const destinationDialog = document.querySelector("#destination-dialog");
const dialogDestinationName = document.querySelector("#dialog-destination-name");
const themeToggle = document.querySelector("#theme-toggle");
let selectedDestination = "";

document.querySelector("#copyright-year").textContent = new Date().getFullYear();

function updateHeaderScrollState() {
  siteHeader.classList.toggle("is-scrolled", window.scrollY > 24);
}

updateHeaderScrollState();
window.addEventListener("scroll", updateHeaderScrollState, { passive: true });

function setTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.dataset.theme = isDark ? "dark" : "light";
  themeToggle.setAttribute("aria-pressed", String(isDark));
  themeToggle.setAttribute("aria-label", `Switch to ${isDark ? "light" : "dark"} mode`);
}

let savedTheme = "light";
try {
  const storedTheme =
    localStorage.getItem("z9-travel-theme") ||
    localStorage.getItem("wanderlink-theme") ||
    localStorage.getItem("theme");
  savedTheme = storedTheme === "dark" ? "dark" : "light";
} catch {
  // The theme remains usable for this page even when browser storage is unavailable.
}
setTheme(savedTheme);

themeToggle.addEventListener("click", () => {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setTheme(nextTheme);
  try {
    localStorage.setItem("z9-travel-theme", nextTheme);
  } catch {
    // Keep the selected theme for the current page if browser storage is unavailable.
  }
});

function activateTab(tabName) {
  tabs.forEach((tab) => {
    const isActive = tab.dataset.tab === tabName;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
    tab.tabIndex = isActive ? 0 : -1;
  });

  panels.forEach((panel) => {
    const isActive = panel.dataset.panel === tabName;
    panel.hidden = !isActive;
    panel.classList.toggle("is-visible", isActive);
    panel.querySelectorAll("input, select").forEach((input) => {
      input.disabled = !isActive;
    });
  });

  formMessage.textContent = "";
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = index;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    tabs[nextIndex].focus();
    activateTab(tabs[nextIndex].dataset.tab);
  });
});

document.querySelectorAll(".destination-image[data-destination]").forEach((card) => {
  card.addEventListener("click", (event) => {
    event.preventDefault();
    selectedDestination = card.dataset.destination;
    dialogDestinationName.textContent = selectedDestination;
    destinationDialog.showModal();
  });
});

document.querySelector(".dialog-close").addEventListener("click", () => destinationDialog.close());
document.querySelector(".dialog-later").addEventListener("click", () => destinationDialog.close());

document.querySelector("#continue-to-booking").addEventListener("click", () => {
  activateTab("flights");
  const destinationField = document.querySelector('[name="flight-to"]');
  destinationField.value = selectedDestination;
  destinationDialog.close();
  document.querySelector("#booking").scrollIntoView({ behavior: "smooth", block: "center" });
  destinationField.focus({ preventScroll: true });
});

document.querySelectorAll("[data-open-tab]").forEach((link) => {
  link.addEventListener("click", () => {
    activateTab(link.dataset.openTab);
    mainNav.classList.remove("is-open");
    menuToggle.setAttribute("aria-expanded", "false");
    siteHeader.classList.remove("is-menu-open");
  });
});

menuToggle.addEventListener("click", () => {
  const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!isOpen));
  mainNav.classList.toggle("is-open", !isOpen);
  siteHeader.classList.toggle("is-menu-open", !isOpen);
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const activePanel = panels.find((panel) => !panel.hidden);
  const invalidField = activePanel.querySelector(":invalid");

  if (invalidField) {
    invalidField.focus();
    invalidField.reportValidity();
    return;
  }

  const tabName = activePanel.dataset.panel;
  const messages = {
    flights: "Your flight search is ready — let's find you a great fare.",
    hotels: "Your stay search is ready — let's find your perfect place.",
    buses: "Your bus search is ready — let's find your next connection.",
  };
  formMessage.textContent = messages[tabName];
});

document.querySelector("#newsletter-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  form.querySelector(".newsletter-message").textContent = "You’re on the list. See you out there!";
  form.reset();
});
