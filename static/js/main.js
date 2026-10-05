/* COPETRO — interacoes de interface */
(function () {
  "use strict";

  // Marca que o JS esta ativo: o CSS so esconde os elementos de revelacao
  // sob html.js, entao sem JS o conteudo aparece normalmente.
  document.documentElement.classList.add("js");

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Menu mobile ---------- */
  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.querySelector("[data-nav]");

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
      // tira o botao do VLibras da frente enquanto o menu cobre a tela
      document.body.classList.toggle("menu-aberto", open);
    });
  }

  /* ---------- Submenus ---------- */
  var dropdowns = Array.prototype.slice.call(document.querySelectorAll("[data-dropdown]"));

  function closeDropdowns(except) {
    dropdowns.forEach(function (item) {
      if (item === except) return;
      item.classList.remove("is-open");
      var btn = item.querySelector("[data-dropdown-trigger]");
      if (btn) btn.setAttribute("aria-expanded", "false");
    });
  }

  dropdowns.forEach(function (item) {
    var trigger = item.querySelector("[data-dropdown-trigger]");
    if (!trigger) return;

    trigger.addEventListener("click", function (e) {
      e.preventDefault();
      var open = !item.classList.contains("is-open");
      closeDropdowns(item);
      item.classList.toggle("is-open", open);
      trigger.setAttribute("aria-expanded", String(open));
    });
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest("[data-dropdown]")) closeDropdowns(null);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;

    // Quem usa teclado precisa continuar de onde parou: ao fechar um submenu ou o
    // menu mobile pelo Esc, o foco volta ao botao que o abriu. Sem isso ele cairia
    // dentro de um elemento que acabou de sumir e o foco iria para o topo da pagina.
    var aberto = dropdowns.filter(function (d) { return d.classList.contains("is-open"); })[0];
    var focoDentro = aberto && aberto.contains(document.activeElement);
    var botaoAberto = aberto && aberto.querySelector("[data-dropdown-trigger]");

    closeDropdowns(null);
    if (focoDentro && botaoAberto) botaoAberto.focus();

    if (nav && nav.classList.contains("is-open")) {
      var focoNoMenu = nav.contains(document.activeElement) || document.activeElement === toggle;
      nav.classList.remove("is-open");
      document.body.classList.remove("menu-aberto");
      if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
        if (focoNoMenu) toggle.focus();
      }
    }
  });

  /* ---------- Acordeoes ---------- */
  Array.prototype.forEach.call(
    document.querySelectorAll("[data-accordion-trigger]"),
    function (trigger) {
      trigger.addEventListener("click", function () {
        var panel = document.getElementById(trigger.getAttribute("aria-controls"));
        if (!panel) return;
        var open = trigger.getAttribute("aria-expanded") === "true";
        trigger.setAttribute("aria-expanded", String(!open));
        panel.classList.toggle("is-open", !open);
      });
    }
  );

  /* ---------- Revelacao ao rolar ----------
     Varredura propria em vez de IntersectionObserver: o IO pode nao disparar
     quando a pagina salta muito rapido (ancora, scroll programatico, restauracao
     de posicao), deixando o bloco invisivel para sempre. Aqui todo elemento cujo
     topo ja passou do limiar e revelado, independente de ter sido "visto". */
  var pending = Array.prototype.slice.call(
    document.querySelectorAll("[data-reveal], [data-reveal-stagger]")
  );

  function revealAll() {
    pending.forEach(function (el) { el.classList.add("is-visible"); });
    pending = [];
  }

  if (reduceMotion) {
    revealAll();
  } else {
    var ticking = false;

    function sweep() {
      ticking = false;
      if (!pending.length) return;
      var limit = window.innerHeight * 0.92;
      // le todas as posicoes ANTES de alterar qualquer classe: ler e escrever
      // alternadamente forca o navegador a recalcular o layout a cada elemento
      var tops = pending.map(function (el) { return el.getBoundingClientRect().top; });
      var restantes = [];
      pending.forEach(function (el, i) {
        if (tops[i] >= limit) restantes.push(el);
        else el.classList.add("is-visible");
      });
      pending = restantes;
      if (!pending.length) {
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
      }
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(sweep);
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    sweep();
    // rede de seguranca: se algo travar, o conteudo nunca fica escondido
    window.addEventListener("load", sweep);
    setTimeout(revealAll, 6000);
  }

  /* ---------- Numeros que contam ao entrar na tela ---------- */
  var counters = document.querySelectorAll("[data-count]");

  function runCounter(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    var suffix = el.getAttribute("data-count-suffix") || "";
    var duration = 1400;
    var start = null;

    function step(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / duration, 1);
      // easeOutCubic: rapido no inicio, assenta no fim
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString("pt-BR") + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function setFinal(el) {
    var t = parseFloat(el.getAttribute("data-count"));
    el.textContent = t.toLocaleString("pt-BR") + (el.getAttribute("data-count-suffix") || "");
  }

  if (counters.length) {
    if (reduceMotion) {
      Array.prototype.forEach.call(counters, setFinal);
    } else {
      // mesma varredura da revelacao: o numero nunca fica preso no valor inicial
      var waiting = Array.prototype.slice.call(counters);
      var countTicking = false;

      function countSweep() {
        countTicking = false;
        if (!waiting.length) return;
        var limit = window.innerHeight * 0.9;
        var topos = waiting.map(function (el) { return el.getBoundingClientRect().top; });
        var faltam = [];
        waiting.forEach(function (el, i) {
          if (topos[i] >= limit) faltam.push(el);
          else runCounter(el);
        });
        waiting = faltam;
        if (!waiting.length) window.removeEventListener("scroll", onCountScroll);
      }

      function onCountScroll() {
        if (countTicking) return;
        countTicking = true;
        requestAnimationFrame(countSweep);
      }

      window.addEventListener("scroll", onCountScroll, { passive: true });
      countSweep();
      setTimeout(function () {
        waiting.forEach(setFinal);
        waiting = [];
      }, 6000);
    }
  }

  /* ---------- Simulador de emprestimo em duas etapas ----------
     Etapa 1 qualifica o interessado, etapa 2 mostra a simulacao ja com os
     valores que ele pediu. O envio so acontece no clique, abrindo o WhatsApp
     com a mensagem pronta: nada sai do navegador sozinho. */
  var sim = document.querySelector("[data-simulator]");

  if (sim) {
    var amount = sim.querySelector("[data-sim-amount]");
    var months = sim.querySelector("[data-sim-months]");
    var amountOut = sim.querySelector("[data-sim-amount-out]");
    var monthsOut = sim.querySelector("[data-sim-months-out]");
    var installmentOut = sim.querySelector("[data-sim-installment]");
    var totalOut = sim.querySelector("[data-sim-total]");

    // Taxa apenas ilustrativa: substituir pela taxa vigente da Copetro.
    var monthlyRate = parseFloat(sim.getAttribute("data-rate")) || 0.0149;
    var numero = (sim.getAttribute("data-whatsapp") || "").replace(/\D/g, "");

    var brl = new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 2
    });

    function paintRange(input) {
      var min = Number(input.min), max = Number(input.max);
      var pct = ((Number(input.value) - min) / (max - min)) * 100;
      input.style.background =
        "linear-gradient(90deg, var(--green-600) " + pct + "%, var(--line) " + pct + "%)";
    }

    function update() {
      var principal = Number(amount.value);
      var n = Number(months.value);

      // Price (parcelas fixas): PMT = PV * i / (1 - (1 + i)^-n)
      var installment = monthlyRate === 0
        ? principal / n
        : (principal * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -n));

      amountOut.textContent = brl.format(principal);
      monthsOut.textContent = n + "x";
      installmentOut.textContent = brl.format(installment);
      if (totalOut) totalOut.textContent = brl.format(installment * n);

      paintRange(amount);
      paintRange(months);
    }

    amount.addEventListener("input", update);
    months.addEventListener("input", update);
    update();

    /* ----- navegacao entre as etapas ----- */
    var etapa1 = sim.querySelector('[data-etapa="1"]');
    var etapa2 = sim.querySelector('[data-etapa="2"]');
    var voltar = sim.querySelector("[data-etapa-voltar]");
    var leadForm = sim.querySelector("[data-lead-form]");
    var leadStatus = sim.querySelector("[data-lead-status]");
    var envioStatus = sim.querySelector("[data-envio-status]");
    var ola = sim.querySelector("[data-sim-ola]");

    function campo(id) { return sim.querySelector("#" + id); }

    function mostrar(n) {
      if (!etapa1 || !etapa2) return;
      etapa1.hidden = n !== 1;
      etapa2.hidden = n !== 2;
      var topo = sim.getBoundingClientRect().top + window.scrollY - 110;
      window.scrollTo({ top: topo, behavior: reduceMotion ? "auto" : "smooth" });
    }

    if (voltar) voltar.addEventListener("click", function () { mostrar(1); });

    function erro(campoEl, msg) {
      if (leadStatus) {
        leadStatus.textContent = msg;
        leadStatus.style.color = "#b23c17";
      }
      if (campoEl) campoEl.focus();
      return false;
    }

    function validar() {
      var nome = campo("lead-nome"), tel = campo("lead-tel");
      var assoc = campo("lead-assoc"), fim = campo("lead-fim");
      var valor = campo("lead-valor"), ok = campo("lead-ok");

      if (!nome.value.trim()) return erro(nome, "Informe o seu nome completo.");
      if (digitos(tel.value).length < 10)
        return erro(tel, "Informe um telefone com DDD.");
      if (!assoc.value) return erro(assoc, "Diga se você já é associado.");
      if (!fim.value) return erro(fim, "Escolha a finalidade do crédito.");

      var v = Number(valor.value);
      if (!v) return erro(valor, "Informe o valor desejado.");
      if (v < 1000 || v > 60000)
        return erro(valor, "O valor deve ficar entre R$ 1.000 e R$ 60.000.");

      if (!ok.checked) return erro(ok, "É preciso autorizar o contato para seguir.");
      return true;
    }

    if (leadForm) {
      leadForm.addEventListener("submit", function (e) {
        e.preventDefault();
        if (!validar()) return;

        if (leadStatus) { leadStatus.textContent = ""; leadStatus.style.color = ""; }

        // leva para a simulacao o que a pessoa pediu
        amount.value = Math.min(60000, Math.max(1000,
          Math.round(Number(campo("lead-valor").value) / 500) * 500));
        months.value = campo("lead-prazo").value;
        update();

        if (ola) {
          var primeiro = campo("lead-nome").value.trim().split(" ")[0];
          ola.textContent = primeiro
            ? primeiro + ", ajuste o valor e o prazo se quiser. Quando estiver bom, envie para a Copetro."
            : "Ajuste o valor e o prazo se quiser. Quando estiver bom, envie para a Copetro.";
        }
        mostrar(2);
      });
    }

    /* ----- envio pelo WhatsApp ----- */
    var enviar = sim.querySelector("[data-enviar-whats]");
    if (enviar) {
      enviar.addEventListener("click", function () {
        if (!numero) {
          if (envioStatus) {
            envioStatus.textContent = "Canal de WhatsApp ainda não configurado. "
              + "Fale com a Copetro pelos canais de atendimento.";
            envioStatus.style.color = "#b23c17";
          }
          return;
        }

        function valor(id) {
          var el = campo(id);
          return el && el.value ? el.value.trim() : "";
        }

        var linhas = [
          "Olá! Fiz uma simulação no site da Copetro e gostaria de uma proposta.",
          "",
          "*Simulação*",
          "Valor: " + amountOut.textContent,
          "Prazo: " + monthsOut.textContent,
          "Parcela estimada: " + installmentOut.textContent
        ];
        if (totalOut) linhas.push("Total estimado: " + totalOut.textContent);

        linhas.push("", "*Meus dados*");
        linhas.push("Nome: " + valor("lead-nome"));
        linhas.push("Telefone: " + valor("lead-tel"));
        if (valor("lead-email")) linhas.push("E-mail: " + valor("lead-email"));
        linhas.push("Associado: " + valor("lead-assoc"));
        if (valor("lead-vinculo")) linhas.push("Vínculo: " + valor("lead-vinculo"));
        linhas.push("Finalidade: " + valor("lead-fim"));
        if (valor("lead-renda")) linhas.push("Renda aproximada: " + valor("lead-renda"));
        if (valor("lead-horario")) linhas.push("Melhor horário: " + valor("lead-horario"));

        if (envioStatus) {
          envioStatus.textContent = "Abrindo o WhatsApp com a sua simulação...";
          envioStatus.style.color = "";
        }
        window.open("https://wa.me/" + numero + "?text=" + encodeURIComponent(linhas.join("\n")),
                    "_blank", "noopener");
      });
    }
  }

  /* ---------- Formularios que seguem para o WhatsApp ----------
     Qualquer <form data-whats-form> e montado automaticamente: o rotulo de
     cada campo vira o titulo da linha na mensagem. Campos vazios sao omitidos.
     O envio so acontece no clique e abre o WhatsApp com o texto pronto, entao
     a pessoa ve tudo antes de mandar. */
  var whatsNumero = (document.body.getAttribute("data-whatsapp") || "").replace(/\D/g, "");

  function rotuloDoCampo(campo, form) {
    var id = campo.id;
    var lbl = id ? form.querySelector('label[for="' + id + '"]') : null;
    if (!lbl && campo.closest) {
      var pai = campo.closest(".form-field");
      if (pai) lbl = pai.querySelector("label");
    }
    var txt = lbl ? lbl.textContent : (campo.name || "");
    return txt.replace(/\*/g, "").replace(/\s+/g, " ").trim();
  }

  Array.prototype.forEach.call(
    document.querySelectorAll("form[data-whats-form]"),
    function (form) {
      var status = form.querySelector("[data-form-status]");

      function aviso(msg, campo) {
        if (status) {
          status.textContent = msg;
          status.style.color = "#b23c17";
        }
        if (campo) campo.focus();
      }

      form.addEventListener("submit", function (e) {
        e.preventDefault();

        var campos = Array.prototype.slice.call(
          form.querySelectorAll("input[name], select[name], textarea[name]")
        );

        for (var i = 0; i < campos.length; i++) {
          var c = campos[i];

          if (c.type === "checkbox") {
            if (c.required && !c.checked)
              return aviso("É preciso autorizar o contato para enviar.", c);
            continue;
          }

          var v = (c.value || "").trim();

          // obrigatorio e vazio
          if (c.required && !v)
            return aviso("Preencha o campo " + rotuloDoCampo(c, form).toLowerCase() + ".", c);

          // formato: vale tambem para campo opcional que foi preenchido
          if (!v) continue;
          if (c.type === "tel" && digitos(v).length < 10)
            return aviso("Informe um telefone com DDD.", c);
          if (c.type === "email" && !/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(v))
            return aviso("Confira o endereço de e-mail.", c);
        }

        if (!whatsNumero) {
          return aviso("Canal de WhatsApp ainda não configurado. "
                     + "Fale com a Copetro pelos canais de atendimento.");
        }

        var titulo = form.getAttribute("data-whats-titulo") || "Mensagem pelo site";
        var linhas = ["*" + titulo + "*", ""];

        campos.forEach(function (c) {
          if (c.type === "checkbox" || c.type === "password") return;
          var v = (c.value || "").trim();
          if (!v) return;
          linhas.push(rotuloDoCampo(c, form) + ": " + v);
        });

        if (status) {
          status.textContent = "Abrindo o WhatsApp com a sua mensagem...";
          status.style.color = "";
        }
        window.open("https://wa.me/" + whatsNumero + "?text=" + encodeURIComponent(linhas.join("\n")),
                    "_blank", "noopener");
      });
    }
  );

  /* ---------- Formularios sem back-end ainda ----------
     Sobrou o acesso da Area do Associado, que pede senha: credencial nao vai
     para o WhatsApp. Ele fica bloqueado ate existir o portal de verdade. */
  Array.prototype.forEach.call(
    document.querySelectorAll("form[data-form-pending]"),
    function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var status = form.querySelector("[data-form-status]");
        if (status) {
          status.textContent = "A Área do Associado ainda não está disponível.";
          status.style.color = "#b23c17";
        }
      });
    }
  );

  /* ---------- Consentimento de cookies (LGPD) ----------
     A escolha fica em localStorage. Cookies nao essenciais so devem ser
     carregados depois de consentimento explicito — veja onConsent() abaixo. */
  var KEY = "copetro:consentimento";
  var banner = document.querySelector("[data-cookie-banner]");

  function readConsent() {
    try {
      return JSON.parse(localStorage.getItem(KEY));
    } catch (e) {
      return null;
    }
  }

  function saveConsent(value) {
    value.data = new Date().toISOString();
    value.versao = 1;
    try {
      localStorage.setItem(KEY, JSON.stringify(value));
    } catch (e) {
      /* modo privativo ou storage bloqueado: segue sem persistir */
    }
    onConsent(value);
  }

  // Ponto de integracao: dispare aqui as tags que dependem de consentimento
  // (Google Analytics, Meta Pixel, etc). Nada e carregado sem opt-in.
  function onConsent(c) {
    document.dispatchEvent(new CustomEvent("copetro:consentimento", { detail: c }));
  }

  if (banner) {
    var prefs = banner.querySelector("[data-cookie-prefs]");
    var saved = readConsent();

    if (!saved) {
      // atrasa um instante para nao competir com o carregamento da pagina
      setTimeout(function () { banner.classList.add("is-open"); }, 900);
    } else {
      onConsent(saved);
    }

    function close() { banner.classList.remove("is-open"); }

    var btnAll = banner.querySelector("[data-cookie-accept]");
    var btnNec = banner.querySelector("[data-cookie-reject]");
    var btnCfg = banner.querySelector("[data-cookie-configure]");
    var btnSave = banner.querySelector("[data-cookie-save]");

    if (btnAll) btnAll.addEventListener("click", function () {
      saveConsent({ necessarios: true, desempenho: true, marketing: true });
      close();
    });

    if (btnNec) btnNec.addEventListener("click", function () {
      saveConsent({ necessarios: true, desempenho: false, marketing: false });
      close();
    });

    if (btnCfg) btnCfg.addEventListener("click", function () {
      var open = prefs.classList.toggle("is-open");
      btnCfg.setAttribute("aria-expanded", String(open));
    });

    if (btnSave) btnSave.addEventListener("click", function () {
      saveConsent({
        necessarios: true,
        desempenho: banner.querySelector("#cookie-desempenho").checked,
        marketing: banner.querySelector("#cookie-marketing").checked
      });
      close();
    });
  }

  // Link "gerenciar cookies" (rodape e politica) reabre o banner
  Array.prototype.forEach.call(
    document.querySelectorAll("[data-cookie-open]"),
    function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        if (!banner) return;
        banner.classList.add("is-open");
        banner.scrollIntoView({ block: "nearest" });
      });
    }
  );

  /* ---------- Formatacao de telefone, CPF e e-mail ----------
     A mascara so organiza o que a pessoa digita: o valor continua acessivel
     e a validacao do back-end nao deve confiar nela. */
  function digitos(v) { return (v || "").replace(/\D/g, ""); }

  function formatarTelefone(v) {
    var d = digitos(v).slice(0, 11);
    if (d.length <= 2) return d.length ? "(" + d : "";
    if (d.length <= 6) return "(" + d.slice(0, 2) + ") " + d.slice(2);
    if (d.length <= 10)
      return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
  }

  function formatarCPF(v) {
    var d = digitos(v).slice(0, 11);
    if (d.length <= 3) return d;
    if (d.length <= 6) return d.slice(0, 3) + "." + d.slice(3);
    if (d.length <= 9) return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
    return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
  }

  function aplicarMascara(campo, formatar) {
    function ao() {
      // mantem o cursor no fim quando a pessoa esta digitando no fim
      var noFim = campo.selectionStart === campo.value.length;
      var antes = campo.value;
      var depois = formatar(antes);
      if (depois === antes) return;
      campo.value = depois;
      if (noFim) {
        try { campo.setSelectionRange(depois.length, depois.length); } catch (e) {}
      }
    }
    campo.addEventListener("input", ao);
    campo.addEventListener("blur", ao);
    if (campo.value) ao();
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('input[type="tel"]'),
    function (c) { aplicarMascara(c, formatarTelefone); }
  );
  Array.prototype.forEach.call(
    document.querySelectorAll('input[inputmode="numeric"][id$="cpf"], #cpf, #ouv-cpf'),
    function (c) { aplicarMascara(c, formatarCPF); }
  );

  /* aviso de e-mail invalido ao sair do campo */
  var EMAIL_OK = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;
  Array.prototype.forEach.call(
    document.querySelectorAll('input[type="email"]'),
    function (campo) {
      var aviso = document.createElement("span");
      aviso.className = "campo-erro";
      aviso.hidden = true;
      aviso.setAttribute("role", "status");
      if (campo.parentNode) campo.parentNode.appendChild(aviso);

      function checar() {
        var v = campo.value.trim();
        var ruim = v.length > 0 && !EMAIL_OK.test(v);
        aviso.hidden = !ruim;
        aviso.textContent = ruim ? "E-mail parece incompleto. Confira o endereço." : "";
        campo.classList.toggle("is-invalido", ruim);
        campo.setAttribute("aria-invalid", ruim ? "true" : "false");
      }
      campo.addEventListener("blur", checar);
      campo.addEventListener("input", function () {
        if (campo.classList.contains("is-invalido")) checar();
      });
    }
  );

  /* ---------- Carrossel ----------
     A rolagem e nativa (scroll-snap), entao no celular o arraste ja funciona
     sem JS. Aqui so entram as setas e os pontos. */
  Array.prototype.forEach.call(document.querySelectorAll("[data-carrossel]"), function (car) {
    var trilho = car.querySelector("[data-carrossel-trilho]");
    var ant = car.querySelector("[data-carrossel-ant]");
    var prox = car.querySelector("[data-carrossel-prox]");
    var pontos = car.querySelector("[data-carrossel-pontos]");
    if (!trilho) return;

    var itens = Array.prototype.slice.call(trilho.children);
    if (!itens.length) return;

    function passo() {
      if (itens.length < 2) return trilho.clientWidth;
      return itens[1].offsetLeft - itens[0].offsetLeft;
    }

    function porTela() {
      return Math.max(1, Math.round(trilho.clientWidth / passo()));
    }

    function paginas() {
      return Math.max(1, itens.length - porTela() + 1);
    }

    function atual() {
      return Math.round(trilho.scrollLeft / passo());
    }

    // pontos
    var botoes = [];
    function montarPontos() {
      if (!pontos) return;
      pontos.innerHTML = "";
      botoes = [];
      var n = paginas();
      if (n < 2) return;
      for (var i = 0; i < n; i++) {
        (function (idx) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "carrossel__ponto";
          b.setAttribute("aria-label", "Ir para o item " + (idx + 1));
          b.addEventListener("click", function () {
            trilho.scrollTo({ left: idx * passo() });
          });
          pontos.appendChild(b);
          botoes.push(b);
        })(i);
      }
    }

    function sincronizar() {
      var i = atual();
      var max = paginas() - 1;
      if (ant) ant.disabled = i <= 0;
      if (prox) prox.disabled = i >= max;
      botoes.forEach(function (b, idx) {
        b.classList.toggle("is-ativo", idx === i);
        if (idx === i) b.setAttribute("aria-current", "true");
        else b.removeAttribute("aria-current");
      });
    }

    if (ant) ant.addEventListener("click", function () {
      trilho.scrollBy({ left: -passo() });
    });
    if (prox) prox.addEventListener("click", function () {
      trilho.scrollBy({ left: passo() });
    });

    var pendente = false;
    trilho.addEventListener("scroll", function () {
      if (pendente) return;
      pendente = true;
      requestAnimationFrame(function () { pendente = false; sincronizar(); });
    }, { passive: true });

    window.addEventListener("resize", function () { montarPontos(); sincronizar(); });
    montarPontos();
    sincronizar();
  });

  /* ---------- Painel de busca ---------- */
  var painel = document.querySelector("[data-search-panel]");
  var abrirBusca = document.querySelector("[data-search-open]");
  var fecharBusca = document.querySelector("[data-search-close]");
  var campoBusca = document.querySelector("[data-search-input]");

  function alternarBusca(abrir) {
    if (!painel) return;
    painel.hidden = !abrir;
    if (abrirBusca) abrirBusca.setAttribute("aria-expanded", String(abrir));
    if (abrir && campoBusca) campoBusca.focus();
    else if (abrirBusca) abrirBusca.focus();
  }

  if (abrirBusca) abrirBusca.addEventListener("click", function () {
    alternarBusca(painel.hidden);
  });
  if (fecharBusca) fecharBusca.addEventListener("click", function () { alternarBusca(false); });

  document.addEventListener("keydown", function (e) {
    if (!painel) return;
    // "/" abre a busca, desde que o foco nao esteja em um campo
    var digitando = /^(input|textarea|select)$/i.test((e.target.tagName || ""));
    if (e.key === "/" && !digitando && painel.hidden) {
      e.preventDefault();
      alternarBusca(true);
    } else if (e.key === "Escape" && !painel.hidden) {
      alternarBusca(false);
    }
  });

  /* ---------- Sombra no header apos rolar ---------- */
  var header = document.querySelector(".header");
  if (header) {
    var stuckTicking = false;
    function marcaHeader() {
      stuckTicking = false;
      header.classList.toggle("is-stuck", window.scrollY > 8);
    }
    window.addEventListener("scroll", function () {
      if (stuckTicking) return;
      stuckTicking = true;
      requestAnimationFrame(marcaHeader);
    }, { passive: true });
    marcaHeader();
  }

  /* ---------- VLibras ----------
     A inicializacao mora aqui, e nao num <script> inline no HTML, porque a CSP
     do site nao permite scripts inline. */
  window.addEventListener("load", function () {
    if (window.VLibras) new window.VLibras.Widget("https://vlibras.gov.br/app");
  });

  /* ---------- Marca o ano corrente no rodape ---------- */
  var year = document.querySelector("[data-year]");
  if (year) year.textContent = new Date().getFullYear();
})();
