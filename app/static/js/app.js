document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.querySelector('input[type="file"]');
  if (fileInput) {
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      const hint = document.querySelector(".file-hint");
      if (file && hint) {
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        hint.textContent = `${file.name} · ${sizeMb} MB`;
      }
    });
  }
});
