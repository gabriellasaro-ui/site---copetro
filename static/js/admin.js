/* Painel de conteudos: so o que precisa de JavaScript.
   Sem scripts inline: a CSP do site nao permite. */
(function () {
  "use strict";

  /* confirmacao antes de excluir */
  Array.prototype.forEach.call(document.querySelectorAll("form[data-confirm]"), function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  /* arrastar para reordenar */
  var lista = document.querySelector("[data-reordenar]");
  if (lista) {
    var arrastando = null;
    lista.addEventListener("dragstart", function (e) {
      arrastando = e.target.closest ? e.target.closest(".adm-item") : null;
      if (!arrastando) return;
      arrastando.classList.add("is-arrastando");
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", arrastando.getAttribute("data-slug")); } catch (x) {}
    });
    lista.addEventListener("dragover", function (e) {
      if (!arrastando) return;
      e.preventDefault();
      var alvo = e.target.closest(".adm-item");
      if (!alvo || alvo === arrastando) return;
      var r = alvo.getBoundingClientRect();
      lista.insertBefore(arrastando, e.clientY < r.top + r.height / 2 ? alvo : alvo.nextSibling);
    });
    lista.addEventListener("dragend", function () {
      if (!arrastando) return;
      arrastando.classList.remove("is-arrastando");
      arrastando = null;
      var slugs = Array.prototype.map.call(lista.querySelectorAll(".adm-item"), function (li) {
        return li.getAttribute("data-slug");
      });
      var corpo = new URLSearchParams();
      corpo.set("csrf", lista.getAttribute("data-csrf"));
      corpo.set("ordem", slugs.join(","));
      fetch(lista.getAttribute("data-reordenar"), {
        method: "POST", body: corpo, credentials: "same-origin"
      }).then(function (r) {
        if (!r.ok) throw new Error();
        window.location.reload();
      }).catch(function () {
        window.alert("Não foi possível salvar a nova ordem. Recarregue a página e tente de novo.");
      });
    });
  }

  /* contador de caracteres */
  Array.prototype.forEach.call(document.querySelectorAll("[data-contador]"), function (campo) {
    var saida = document.querySelector('[data-contador-de="' + campo.id + '"]');
    if (!saida) return;
    function atualizar() {
      saida.textContent = campo.value.length;
      saida.style.color = campo.value.length >= Number(campo.getAttribute("data-contador")) * 0.95
        ? "#b23c17" : "";
    }
    campo.addEventListener("input", atualizar);
    atualizar();
  });

  /* previa da imagem escolhida, antes de enviar */
  var envio = document.querySelector("[data-previa-envio]");
  var previa = document.querySelector("[data-previa-atual]");
  if (envio && previa) {
    var original = previa.getAttribute("src");
    envio.addEventListener("change", function () {
      var arq = envio.files && envio.files[0];
      if (!arq) {
        if (original) { previa.src = original; } else { previa.hidden = true; }
        return;
      }
      if (arq.size > 8 * 1024 * 1024) {
        window.alert("A imagem passa de 8 MB. Escolha um arquivo menor.");
        envio.value = "";
        return;
      }
      var url = URL.createObjectURL(arq);
      previa.src = url;
      previa.hidden = false;
      previa.onload = function () { URL.revokeObjectURL(url); };
    });
  }
})();
