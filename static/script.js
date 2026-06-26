const menuToggle = document.querySelector(".menu-toggle");
const navLinks = document.querySelector("#navLinks");

menuToggle.addEventListener("click", () => {
  const isOpen = navLinks.classList.toggle("is-open");
  menuToggle.setAttribute("aria-expanded", String(isOpen));
});

navLinks.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    navLinks.classList.remove("is-open");
    menuToggle.setAttribute("aria-expanded", "false");
  });
});

document.querySelector("#year").textContent = new Date().getFullYear();

const contactForm = document.querySelector("#contactForm");
const formMessage = document.querySelector("#formMessage");

contactForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const submitButton = contactForm.querySelector("button[type='submit']");
  const formData = new FormData(contactForm);

  formMessage.textContent = "";
  formMessage.className = "form-message";
  submitButton.disabled = true;
  submitButton.textContent = "Enviando...";

  try {
    const response = await fetch(contactForm.action, {
      method: "POST",
      body: formData,
      headers: {
        Accept: "application/json",
      },
    });

    const result = await response.json();
    formMessage.textContent = result.mensagem || "Recebemos sua mensagem.";
    formMessage.classList.add(response.ok ? "is-success" : "is-error");

    if (response.ok) {
      contactForm.reset();
    }
  } catch (error) {
    formMessage.textContent = "Nao foi possivel enviar sua mensagem agora. Tente novamente em instantes.";
    formMessage.classList.add("is-error");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Enviar mensagem";
  }
});
