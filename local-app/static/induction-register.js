(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const token = location.pathname.split("/").filter(Boolean)[2] || "";
  let schema = null;

  const showNotice = (message) => {
    const notice = $("#notice");
    notice.textContent = message;
    notice.classList.toggle("hidden", !message);
    if (message) notice.scrollIntoView({behavior: "smooth", block: "center"});
  };

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      ...options,
      headers: {"Content-Type": "application/json", ...(options.headers || {})},
    });
    const body = response.headers.get("Content-Type")?.includes("json") ? await response.json() : {};
    if (!response.ok) throw new Error(body.error || "The request could not be completed.");
    return body;
  };

  const optionMarkup = (items, valueKey = "id", labelKey = "name") =>
    items.map((item) => `<option value="${String(item[valueKey]).replaceAll('"', "&quot;")}">${String(item[labelKey])}</option>`).join("");

  const renderTraining = () => {
    $("#training-records").innerHTML = schema.training_questions.map((question, index) => `
      <article class="training-row" data-training="${question.id}">
        <header>
          <h3>${index + 1}. ${question.question}</h3>
          <fieldset class="yes-no" aria-label="${question.question}">
            <label><input type="radio" name="training_${question.id}" value="yes"> Yes</label>
            <label><input type="radio" name="training_${question.id}" value="no"> No</label>
          </fieldset>
        </header>
        <div class="training-details hidden">
          <label><span>Expiry date <b>*</b></span><input type="date" data-training-expiry="${question.id}"></label>
          <label class="file-field"><span>Photo <b>*</b></span><input type="file" data-training-photo="${question.id}" accept="image/png,image/jpeg" multiple><small>PNG or JPEG · maximum 10 MB each</small></label>
        </div>
      </article>
    `).join("");
    $$("[data-training] input[type=radio]").forEach((radio) => radio.addEventListener("change", () => {
      const row = radio.closest("[data-training]");
      const yes = radio.value === "yes" && radio.checked;
      const details = $(".training-details", row);
      details.classList.toggle("hidden", !yes);
      $("[data-training-expiry]", row).required = yes;
      $("[data-training-photo]", row).required = yes;
      if (!yes) {
        $("[data-training-expiry]", row).value = "";
        $("[data-training-photo]", row).value = "";
      }
    }));
  };

  const renderSchema = () => {
    document.title = `${schema.selected_site.name} induction · Kompliance`;
    $("#page-title").textContent = schema.induction.title;
    $("#page-context").textContent = `${schema.company} · Worker registration`;
    $("#site-name").textContent = schema.selected_site.name;
    const callingCodes = schema.calling_codes.map((code) => ({id: code, name: code}));
    $$("select[name$='country_code']").forEach((select) => {
      select.innerHTML = optionMarkup(callingCodes);
      select.value = "+353";
    });
    $("#role-options").innerHTML = schema.roles.map((role) => `<label><input type="checkbox" name="roles" value="${role.id}"> ${role.name}</label>`).join("");
    $("#subcontractors").innerHTML = optionMarkup(schema.subcontractors);
    renderTraining();
    $("#loading").classList.add("hidden");
    $("#registration-form").classList.remove("hidden");
    window.KomplianceI18n?.apply();
  };

  const toggleSafePass = () => {
    const yes = $("input[name='safe_pass_answer']:checked")?.value === "yes";
    $("#safe-pass-fields").classList.toggle("hidden", !yes);
    ["safe_pass_name", "safe_pass_title", "safe_pass_valid_from", "safe_pass_expiry_date", "safe_pass_photo"].forEach((name) => {
      const field = $(`[name='${name}']`);
      field.required = yes;
      if (!yes) field.value = "";
    });
  };

  const validateFiles = (files) => {
    for (const file of files) {
      if (file.size > 10 * 1024 * 1024) throw new Error(`${file.name} exceeds the 10 MB limit.`);
      if (!["image/png", "image/jpeg"].includes(file.type)) throw new Error(`${file.name} must be a PNG or JPEG image.`);
    }
  };

  const registrationPayload = (form) => {
    const trainingRecords = schema.training_questions.map((question) => ({
      question_id: question.id,
      answer: $(`input[name='training_${question.id}']:checked`, form)?.value || "",
      expiry_date: $(`[data-training-expiry='${question.id}']`, form).value,
    }));
    const safePassAnswer = $("input[name='safe_pass_answer']:checked", form)?.value || "";
    return {
      name: form.elements.name.value,
      email: form.elements.email.value,
      worker_id: form.elements.worker_id.value,
      country_code: form.elements.country_code.value,
      phone_number: form.elements.phone_number.value,
      emergency_country_code: form.elements.emergency_country_code.value,
      emergency_phone_number: form.elements.emergency_phone_number.value,
      emergency_contact_name: form.elements.emergency_contact_name.value,
      emergency_contact_address: form.elements.emergency_contact_address.value,
      roles: $$("input[name='roles']:checked", form).map((field) => field.value),
      subcontractors: [...form.elements.subcontractors.selectedOptions].map((option) => option.value),
      medical_details: form.elements.medical_details.value,
      training_records: trainingRecords,
      safe_pass: {
        answer: safePassAnswer,
        name: form.elements.safe_pass_name.value,
        title: form.elements.safe_pass_title.value,
        valid_from: form.elements.safe_pass_valid_from.value,
        expiry_date: form.elements.safe_pass_expiry_date.value,
      },
      safety_confirmation: form.elements.safety_confirmation.checked,
      language: window.KomplianceI18n?.getLanguage() || "en-IE",
    };
  };

  const evidenceFiles = (form) => {
    const evidence = [];
    [...form.elements.photo.files].forEach((file) => evidence.push({fieldKey: "worker_photo", file}));
    schema.training_questions.forEach((question) => {
      if ($(`input[name='training_${question.id}']:checked`, form)?.value === "yes") {
        $$(`[data-training-photo='${question.id}']`, form)[0].files &&
          [...$(`[data-training-photo='${question.id}']`, form).files].forEach((file) => evidence.push({fieldKey: `training:${question.id}:photo`, file}));
      }
    });
    if ($("input[name='safe_pass_answer']:checked", form)?.value === "yes") {
      [...form.elements.safe_pass_photo.files].forEach((file) => evidence.push({fieldKey: "safe_pass:photo", file}));
    }
    validateFiles(evidence.map((item) => item.file));
    return evidence;
  };

  const uploadEvidence = async (registration, evidence, button) => {
    for (let index = 0; index < evidence.length; index += 1) {
      const item = evidence[index];
      button.textContent = `Uploading evidence ${index + 1} of ${evidence.length}…`;
      const response = await fetch(`/api/public/induction/${encodeURIComponent(token)}/registrations/${registration.id}/evidence`, {
        method: "POST",
        headers: {
          "Content-Type": item.file.type,
          "X-Upload-Token": registration.upload_token,
          "X-Field-Key": item.fieldKey,
          "X-File-Name": encodeURIComponent(item.file.name),
        },
        body: item.file,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Could not upload ${item.file.name}.`);
    }
  };

  $("#registration-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    showNotice("");
    if (!form.reportValidity()) return;
    if (!$$("input[name='roles']:checked", form).length) {
      showNotice("Select at least one role.");
      return;
    }
    if (!form.elements.subcontractors.selectedOptions.length) {
      showNotice("Select a subcontractor or No Subcontractor.");
      return;
    }
    const button = $("#submit-button");
    button.disabled = true;
    const originalLabel = button.textContent;
    try {
      const evidence = evidenceFiles(form);
      button.textContent = "Registering…";
      const registration = await api(`/api/public/induction/${encodeURIComponent(token)}/registrations`, {
        method: "POST",
        body: JSON.stringify(registrationPayload(form)),
      });
      await uploadEvidence(registration, evidence, button);
      button.textContent = "Submitting…";
      const completed = await api(`/api/public/induction/${encodeURIComponent(token)}/registrations/${registration.id}/complete`, {
        method: "POST",
        headers: {"X-Upload-Token": registration.upload_token},
        body: JSON.stringify({}),
      });
      form.classList.add("hidden");
      $("#registration-reference").textContent = completed.reference;
      $("#success").classList.remove("hidden");
      $("#success").scrollIntoView({behavior: "smooth", block: "center"});
    } catch (error) {
      showNotice(error.message);
      button.disabled = false;
      button.textContent = originalLabel;
    }
  });

  $$("input[name='safe_pass_answer']").forEach((radio) => radio.addEventListener("change", toggleSafePass));

  api(`/api/public/induction/${encodeURIComponent(token)}`)
    .then((value) => {
      schema = value;
      renderSchema();
    })
    .catch((error) => {
      $("#loading").classList.add("hidden");
      showNotice(error.message || "This induction link is unavailable.");
    });
})();
